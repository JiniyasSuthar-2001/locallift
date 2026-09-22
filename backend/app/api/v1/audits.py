from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user
from app.core.audit_logger import log_user_action
from app.models.user import User
from app.models.project import Project, Website, Location
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.models.local_seo import Citation, Review, Competitor
from app.models.ranking import Keyword
from app.models.audit import SEOAudit, SEOIssue, WebsitePage, IssueSeverity, IssueStatus, AuditJob, AuditJobStatus
from app.schemas.audit import SEOAuditOut, SEOIssueOut, WebsitePageOut, CrawlRequest, AuditJobOut
from app.services.crawler import WebsiteCrawler, SSRFValidator, URLNormalizer
from app.services.seo_auditor import SEOAuditor
from app.config import settings
import logging
import traceback

logger = logging.getLogger("locallift.audits")

router = APIRouter(prefix="/audits", tags=["Audits & Crawler"])

import time
from app.services.crawl_storage import CrawlStorage

async def run_crawler_and_audit_task(
    job_id: int,
    project_id: int,
    start_url: str,
    crawl_options: Dict[str, Any]
):
    async with AsyncSessionLocal() as session:
        job_res = await session.execute(select(AuditJob).where(AuditJob.id == job_id))
        job = job_res.scalars().first()
        if not job:
            logger.error(f"AuditJob {job_id} not found in database for background execution.")
            return

        try:
            job.status = AuditJobStatus.RUNNING
            job.crawler_status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.current_stage = "Initializing crawler engine & validating target host"
            job.progress = 5.0
            await session.commit()

            last_db_update = time.time()
            last_stage = job.current_stage

            async def progress_callback(metrics: Dict[str, Any]):
                nonlocal last_db_update, last_stage
                now = time.time()
                stage = metrics.get("stage", "crawling")
                current_stage_msg = metrics.get("current_stage", "Crawling pages...")
                
                # Throttle database persistence to min 500ms or stage transition
                if (now - last_db_update < 0.5) and (current_stage_msg == last_stage):
                    return

                last_db_update = now
                last_stage = current_stage_msg

                async with AsyncSessionLocal() as cb_session:
                    res = await cb_session.execute(select(AuditJob).where(AuditJob.id == job_id))
                    j = res.scalars().first()
                    if j:
                        # Check for cancellation
                        if j.status == AuditJobStatus.CANCEL_REQUESTED:
                            j.status = AuditJobStatus.CANCELLED
                            j.crawler_status = "cancelled"
                            j.current_stage = "Crawl cancelled by user request"
                            await cb_session.commit()
                            return

                        j.pages_discovered = metrics.get("pages_discovered", 0)
                        j.pages_crawled = metrics.get("pages_crawled", 0)
                        j.pages_processed = metrics.get("pages_processed", 0)
                        j.pages_failed = metrics.get("pages_failed", 0)
                        j.pages_blocked = metrics.get("pages_blocked", 0)
                        j.links_discovered = metrics.get("links_discovered", 0)
                        j.links_checked = metrics.get("links_checked", 0)
                        j.broken_links_found = metrics.get("broken_links_found", 0)
                        j.sitemap_urls_discovered = metrics.get("sitemap_urls_discovered", 0)
                        j.robots_blocked_count = metrics.get("robots_blocked_count", 0)
                        j.ssrf_blocked_count = metrics.get("ssrf_blocked_count", 0)
                        
                        j.current_stage = current_stage_msg
                        j.progress = metrics.get("progress", j.progress)
                        
                        j.broken_link_check_status = metrics.get("broken_link_check_status", "not_started")
                        j.broken_link_check_error = metrics.get("broken_link_check_error")
                        j.links_skipped = metrics.get("links_skipped", 0)
                        j.runtime_limit_reached = metrics.get("runtime_limit_reached", False)
                        j.redirect_limit_reached = metrics.get("redirect_limit_reached", False)
                        j.browser_rendering_unavailable = metrics.get("browser_rendering_unavailable", False)
                        
                        # Map explicit status
                        if stage == "fetching_robots":
                            j.status = AuditJobStatus.FETCHING_ROBOTS
                        elif stage == "reading_sitemaps":
                            j.status = AuditJobStatus.READING_SITEMAPS
                        elif stage == "crawling":
                            j.status = AuditJobStatus.CRAWLING
                        elif stage == "checking_links":
                            j.status = AuditJobStatus.CHECKING_LINKS
                        elif stage == "saving":
                            j.status = AuditJobStatus.SAVING
                        
                        await cb_session.commit()

            def cancellation_check() -> bool:
                # Synchronous check for fast cancellation polling
                return job.status == AuditJobStatus.CANCEL_REQUESTED

            crawler = WebsiteCrawler(
                start_url=start_url,
                max_pages=crawl_options.get("max_pages", 25),
                respect_robots=crawl_options.get("respect_robots", True),
                crawl_delay_ms=crawl_options.get("crawl_delay_ms", 200),
                follow_redirects=crawl_options.get("follow_redirects", True),
                allow_local_dev=crawl_options.get("allow_local_dev", False),
                include_patterns=crawl_options.get("include_patterns"),
                exclude_patterns=crawl_options.get("exclude_patterns"),
                max_depth=crawl_options.get("max_depth", 5),
                enable_js_rendering=crawl_options.get("enable_js_rendering", False),
                check_external_links=crawl_options.get("check_external_links", True),
                max_external_links=crawl_options.get("max_external_links", 50),
                progress_callback=progress_callback,
                cancellation_check=cancellation_check
            )

            # Store exact options snapshot
            job.options_snapshot = crawler.get_options_snapshot()
            await session.commit()

            pages_data = await crawler.crawl()

            # Check if job was cancelled during crawl
            if job.status == AuditJobStatus.CANCEL_REQUESTED:
                job.status = AuditJobStatus.CANCELLED
                job.crawler_status = "cancelled"
                job.current_stage = "Crawl cancelled by user request"
                await session.commit()
                return

            # Mark saving stage
            job.status = AuditJobStatus.SAVING
            job.current_stage = "Persisting page records & executing Local SEO auditor rules"
            job.progress = 92.0
            job.pages_processed = len(pages_data)
            await session.commit()

            # Find or create website record
            web_res = await session.execute(select(Website).where(Website.project_id == project_id))
            website = web_res.scalars().first()
            if not website:
                website = Website(project_id=project_id, url=start_url, status="ready")
                session.add(website)
                await session.flush()

            website.status = "completed"
            website.pages_crawled = len(pages_data)
            website.last_crawled_at = datetime.now(timezone.utc)

            # Clear old page records
            old_pages_res = await session.execute(select(WebsitePage).where(WebsitePage.website_id == website.id))
            for old_p in old_pages_res.scalars().all():
                await session.delete(old_p)
            await session.flush()

            # Save newly crawled pages
            for p in pages_data:
                page_obj = WebsitePage(
                    website_id=website.id,
                    url=p.get("url"),
                    status_code=p.get("status_code", 200),
                    title=p.get("title"),
                    meta_description=p.get("meta_description"),
                    h1=p.get("h1"),
                    h2_list=p.get("h2_list", []),
                    word_count=p.get("word_count", 0),
                    canonical_url=p.get("canonical_url"),
                    is_indexable=p.get("is_indexable", True),
                    load_time_ms=p.get("load_time_ms", 0),
                    schema_types=p.get("schema_types", []),
                    images_count=p.get("images_count", 0),
                    missing_alt_count=p.get("missing_alt_count", 0),
                    internal_links_count=p.get("internal_links_count", 0),
                    external_links_count=p.get("external_links_count", 0),
                    broken_links=p.get("broken_links", []),
                    issues_detected=p.get("issues_detected", [])
                )
                session.add(page_obj)

            # Load Project & Location context
            proj_res = await session.execute(
                select(Project).options(selectinload(Project.locations)).where(Project.id == project_id)
            )
            proj = proj_res.scalars().first()
            
            project_context = None
            if proj:
                loc = proj.locations[0] if proj.locations else None
                project_context = {
                    "name": proj.name,
                    "domain": proj.domain,
                    "city": loc.city if loc else None,
                    "phone": loc.phone if loc else None,
                    "address": loc.address if loc else None
                }

            # Load GBP context
            acc_res = await session.execute(
                select(GoogleAccount).where(GoogleAccount.project_id == project_id)
            )
            google_account = acc_res.scalars().first()
            if not google_account and proj:
                from app.services.google.connections_service import GoogleConnectionsService
                gbp_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "business_profile", session)
                if gbp_conn and gbp_conn.status in ("connected", "expired") and gbp_conn.access_token:
                    google_account = GoogleAccount(
                        project_id=project_id,
                        account_email=gbp_conn.account_email or f"user-{project_id}@google.com",
                        access_token=gbp_conn.access_token,
                        refresh_token=gbp_conn.refresh_token,
                        token_expiry=gbp_conn.token_expiry,
                        scopes=gbp_conn.scopes or [],
                        is_connected=True
                    )
                    session.add(google_account)
                    await session.flush()

            gbp_context = None
            if google_account:
                gbp_res = await session.execute(
                    select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == google_account.id)
                )
                gbp = gbp_res.scalars().first()
                if gbp:
                    gbp_context = {
                        "connected": True,
                        "business_name": gbp.business_name,
                        "phone": gbp.phone,
                        "address": gbp.address,
                        "website_url": gbp.website_url,
                        "primary_category": gbp.primary_category
                    }

            # Load Citations context
            cit_res = await session.execute(select(Citation).where(Citation.project_id == project_id))
            citations = cit_res.scalars().all()
            citation_context = [
                {"source_name": c.source_name, "status": c.status, "nap_status": c.nap_status}
                for c in citations
            ]

            # Load Reviews context
            rev_res = await session.execute(select(Review).where(Review.project_id == project_id))
            reviews = rev_res.scalars().all()
            unanswered = [r for r in reviews if r.response_status == "unanswered"]
            avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0
            review_context = {
                "total_reviews": len(reviews),
                "average_rating": round(avg_rating, 1),
                "unanswered_count": len(unanswered)
            }

            # Load Keywords context
            kw_res = await session.execute(select(Keyword).where(Keyword.project_id == project_id))
            keywords = kw_res.scalars().all()
            keyword_context = [{"keyword": k.keyword, "rank": k.current_rank} for k in keywords]

            # Execute SEOAuditor rules
            audit_result = SEOAuditor.audit_pages(
                pages_data,
                project_context=project_context,
                gbp_context=gbp_context,
                citation_context=citation_context,
                review_context=review_context,
                keyword_context=keyword_context
            )

            # Save Local SEO Audit Record
            audit = SEOAudit(
                project_id=project_id,
                audit_type="local_website",
                overall_score=audit_result["score"],
                pages_analyzed=len(pages_data),
                critical_issues=audit_result["critical"],
                warnings=audit_result["warnings"],
                opportunities=audit_result["opportunities"],
                passed_checks=audit_result["passed"],
                summary=f"Crawled {len(pages_data)} pages. Evaluated Schema.org LocalBusiness JSON-LD, NAP consistency, GBP alignment, citations, and suburban coverage."
            )
            session.add(audit)
            await session.flush()

            # Attach canonical metadata inside details JSON
            canonical_payload = {
                **audit_result,
                "project_id": project_id,
                "crawl_id": audit.id,
                "domain": proj.domain if proj else start_url,
                "crawl_timestamp": audit.created_at.isoformat() if audit.created_at else datetime.now(timezone.utc).isoformat()
            }
            audit.details = canonical_payload
            await session.commit()

            # Save Issues while PRESERVING existing issue identity
            existing_issues_res = await session.execute(
                select(SEOIssue).where(SEOIssue.project_id == project_id)
            )
            existing_issues_map = {
                (i.category, i.title, i.affected_url): i for i in existing_issues_res.scalars().all()
            }

            for iss in audit_result["issues"]:
                key = (iss["category"], iss["title"], iss["affected_url"])
                if key in existing_issues_map:
                    # Update existing opportunity details without changing ID or status
                    ex_iss = existing_issues_map[key]
                    ex_iss.audit_id = audit.id
                    ex_iss.severity = IssueSeverity(iss["severity"])
                    ex_iss.evidence = iss["evidence"]
                    ex_iss.why_it_matters = iss["why_it_matters"]
                    ex_iss.recommended_solution = iss["recommended_solution"]
                    ex_iss.action_type = iss["action_type"]
                else:
                    issue_obj = SEOIssue(
                        audit_id=audit.id,
                        project_id=project_id,
                        category=iss["category"],
                        severity=IssueSeverity(iss["severity"]),
                        title=iss["title"],
                        evidence=iss["evidence"],
                        why_it_matters=iss["why_it_matters"],
                        recommended_solution=iss["recommended_solution"],
                        action_type=iss["action_type"],
                        affected_url=iss["affected_url"],
                        status=IssueStatus.OPEN
                    )
                    session.add(issue_obj)

            # Update Project Scores
            if proj:
                pillars = audit_result.get("pillar_scores", {})
                proj.health_score = audit_result["score"]
                proj.technical_score = pillars.get("crawl_health")
                proj.onpage_score = pillars.get("onpage_content")
                proj.local_score = pillars.get("schema_structured_data")
                if pillars.get("gbp_alignment") is not None:
                    proj.gbp_score = pillars["gbp_alignment"]
                if pillars.get("citations_nap") is not None:
                    proj.citations_score = pillars["citations_nap"]
                if pillars.get("reviews_reputation") is not None:
                    proj.reviews_score = pillars["reviews_reputation"]

            # Save transactional artifacts using CrawlStorage
            storage_ok, storage_msg = CrawlStorage.save_crawl_session_artifacts(
                project_id=project_id,
                session_id=job.id,
                metadata=job.options_snapshot,
                pages=pages_data,
                issues=audit_result["issues"],
                internal_links=crawler.link_graph,
                external_links=[l for l in crawler.link_graph if not l["is_internal"]],
                broken_links=crawler.broken_links,
                link_records=crawler.link_records,
                summary=canonical_payload
            )

            job.broken_link_check_status = crawler.broken_link_check_status
            job.broken_link_check_error = crawler.broken_link_check_error
            job.links_skipped = crawler.links_skipped_count
            job.runtime_limit_reached = crawler.runtime_limit_reached
            job.redirect_limit_reached = crawler.redirect_limit_reached
            job.browser_rendering_unavailable = crawler.browser_rendering_unavailable

            if not storage_ok:
                logger.error(f"Storage write error for job {job_id}: {storage_msg}")
                job.status = AuditJobStatus.COMPLETED_WITH_ERRORS
                job.current_stage = f"Crawl finished but storage warning: {storage_msg}"
            else:
                if crawler.pages_failed_count > 0 or crawler.runtime_limit_reached or crawler.broken_link_check_status == "completed_with_errors":
                    job.status = AuditJobStatus.COMPLETED_WITH_ERRORS
                    job.current_stage = f"Crawl completed with diagnostic limits or page errors"
                else:
                    job.status = AuditJobStatus.COMPLETED
                    job.current_stage = "Local Website Audit & Link Graph analysis completed successfully"

            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:
            err_msg = str(exc)
            err_tb = traceback.format_exc()
            logger.error(f"AuditJob {job_id} failed catastrophically: {err_msg}\n{err_tb}")
            
            job.status = AuditJobStatus.FAILED
            job.current_stage = f"Crawl failed: {err_msg[:100]}"
            job.error_message = err_msg
            job.failed_at = datetime.now(timezone.utc)

            web_res = await session.execute(select(Website).where(Website.project_id == project_id))
            website = web_res.scalars().first()
            if website:
                website.status = "failed"

            await session.commit()

from app.core.deps import get_current_user, verify_project_access

@router.post("/crawl/{project_id}")
async def trigger_crawl(
    request: Request,
    project_id: int,
    crawl_in: CrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj = await verify_project_access(project_id, current_user, db)
    target_url = crawl_in.url or f"https://{proj.domain}"
    
    # Enforce Security & Local Dev restrictions
    if crawl_in.allow_local_dev and settings.ENVIRONMENT.strip().lower() == "production":
        raise HTTPException(
            status_code=400,
            detail="SECURITY_VIOLATION: allow_local_dev option is disabled in production environments."
        )

    # Normalize & Validate SSRF on entry
    norm_url = URLNormalizer.normalize(target_url)
    if not norm_url:
        raise HTTPException(status_code=400, detail="INVALID_URL: Target URL could not be normalized.")
    
    is_safe, ssrf_msg, _ = SSRFValidator.validate_url(norm_url, allow_local_dev=crawl_in.allow_local_dev)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"SSRF_SECURITY_VIOLATION: {ssrf_msg}")

    log_user_action(
        request, "RUN_AUDIT",
        user_id=current_user.id,
        organization_id=proj.organization_id,
        project_id=project_id,
        url=norm_url
    )

    crawl_options = {
        "url": norm_url,
        "max_pages": crawl_in.max_pages or 25,
        "respect_robots": crawl_in.respect_robots if crawl_in.respect_robots is not None else True,
        "crawl_delay_ms": crawl_in.crawl_delay_ms if crawl_in.crawl_delay_ms is not None else 200,
        "follow_redirects": crawl_in.follow_redirects if crawl_in.follow_redirects is not None else True,
        "allow_local_dev": bool(crawl_in.allow_local_dev),
        "include_patterns": crawl_in.include_patterns or [],
        "exclude_patterns": crawl_in.exclude_patterns or [],
        "max_depth": crawl_in.max_depth or 5,
        "enable_js_rendering": bool(crawl_in.enable_js_rendering),
        "check_external_links": crawl_in.check_external_links if crawl_in.check_external_links is not None else True,
        "max_external_links": crawl_in.max_external_links or 50,
    }

    # Create persistent AuditJob record with snapshot options
    job = AuditJob(
        project_id=project_id,
        organization_id=proj.organization_id,
        job_type="website_audit",
        status=AuditJobStatus.QUEUED,
        crawler_status="queued",
        progress=0.0,
        current_stage="Audit job queued for background execution",
        start_url=norm_url,
        options_snapshot=crawl_options
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        run_crawler_and_audit_task,
        job_id=job.id,
        project_id=project_id,
        start_url=norm_url,
        crawl_options=crawl_options
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Local Website Crawl & Local SEO Audit task queued",
        "created_at": job.created_at.isoformat()
    }

@router.post("/jobs/{job_id}/cancel")
@router.post("/cancel/{job_id}")
async def cancel_audit_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Audit job not found")
    await verify_project_access(job.project_id, current_user, db)
    
    if job.status in (AuditJobStatus.COMPLETED, AuditJobStatus.FAILED, AuditJobStatus.CANCELLED):
        return {"job_id": job_id, "status": job.status.value, "message": "Job is already finished"}

    job.status = AuditJobStatus.CANCEL_REQUESTED
    job.current_stage = "Cancellation requested by user..."
    await db.commit()
    return {"job_id": job_id, "status": "cancel_requested", "message": "Cancellation request submitted"}

@router.get("/jobs/{job_id}", response_model=AuditJobOut)
async def get_audit_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Audit job not found")
    await verify_project_access(job.project_id, current_user, db)
    return job

@router.get("/{project_id}/jobs", response_model=List[AuditJobOut])
@router.get("/projects/{project_id}/jobs", response_model=List[AuditJobOut])
async def list_project_audit_jobs(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    res = await db.execute(
        select(AuditJob).where(AuditJob.project_id == project_id).order_by(AuditJob.id.desc()).limit(10)
    )
    return res.scalars().all()


@router.get("/{project_id}/latest", response_model=Optional[SEOAuditOut])
async def get_latest_audit(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(SEOAudit)
        .options(selectinload(SEOAudit.issues))
        .where(SEOAudit.project_id == project_id)
        .order_by(SEOAudit.id.desc())
    )
    return result.scalars().first()

@router.get("/{project_id}/canonical")
@router.get("/canonical/{project_id}")
async def get_canonical_audit(
    project_id: int,
    crawl_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)
    query = select(SEOAudit).where(SEOAudit.project_id == project_id)
    if crawl_id:
        query = query.where(SEOAudit.id == crawl_id)
    query = query.order_by(SEOAudit.id.desc())
    
    result = await db.execute(query)
    latest_audit = result.scalars().first()

    if latest_audit and latest_audit.details:
        details = dict(latest_audit.details)
        details["project_id"] = project_id
        details["crawl_id"] = latest_audit.id
        details["domain"] = project.domain
        details["crawl_timestamp"] = latest_audit.created_at.isoformat() if latest_audit.created_at else None
        details["health_score"] = latest_audit.overall_score
        details["score_available"] = latest_audit.pages_analyzed > 0
        return details

    # Fallback if audit exists but details JSON column not yet populated
    if latest_audit:
        web_res = await db.execute(select(Website).where(Website.project_id == project_id))
        website = web_res.scalars().first()
        pages_res = await db.execute(select(WebsitePage).where(WebsitePage.website_id == website.id)) if website else None
        pages = pages_res.scalars().all() if pages_res else []
        pages_data = [
            {
                "url": p.url,
                "status_code": p.status_code,
                "title": p.title,
                "meta_description": p.meta_description,
                "h1": p.h1,
                "word_count": p.word_count,
                "canonical_url": p.canonical_url,
                "schema_types": p.schema_types or [],
                "json_ld_schemas": [],
                "missing_alt_count": p.missing_alt_count
            }
            for p in pages
        ]
        audit_res = SEOAuditor.audit_pages(pages_data, project_context={"domain": project.domain, "name": project.name})
        audit_res["project_id"] = project_id
        audit_res["crawl_id"] = latest_audit.id
        audit_res["domain"] = project.domain
        audit_res["crawl_timestamp"] = latest_audit.created_at.isoformat() if latest_audit.created_at else None
        audit_res["health_score"] = latest_audit.overall_score
        audit_res["score_available"] = latest_audit.pages_analyzed > 0
        return audit_res

    # Empty state when no crawl exists
    return {
        "project_id": project_id,
        "crawl_id": None,
        "domain": project.domain,
        "crawl_timestamp": None,
        "analyzed_pages": 0,
        "evaluated_rules": 0,
        "total_evaluated_checks": 0,
        "health_score": None,
        "score_available": False,
        "rule_definitions": [],
        "rule_execution_results": [],
        "category_breakdown": {},
        "schema_summary": {
            "pages_scanned": 0,
            "pages_with_schema": 0,
            "pages_without_schema": 0,
            "total_schema_instances": 0,
            "unique_schema_types": 0,
            "complete_entities": 0,
            "incomplete_entities": 0,
            "potential_mismatches": 0,
            "detected_types": []
        },
        "schema_evidence": [],
        "robots_summary": {
            "robots_url": f"https://{project.domain}/robots.txt",
            "http_status": 404,
            "fetch_status": "No Crawl Performed",
            "user_agent_groups": 0,
            "allow_rules": 0,
            "disallow_rules": 0,
            "sitemaps": [],
            "seed_url_result": "Not Evaluated"
        },
        "robots_evidence": ["No completed crawl available for this project."],
        "scoring_formula": "Composite score = weighted sum of evaluated pillars (Crawl Health 20%, Content 20%, Schema 25%, GBP 15%, Citations 10%, Reviews 10%).",
        "scoring_weights": SEOAuditor.CONFIGURED_WEIGHTS
    }

@router.get("/{project_id}/issues", response_model=List[SEOIssueOut])
async def list_project_issues(
    project_id: int,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    query = select(SEOIssue).where(SEOIssue.project_id == project_id)
    if category and category.lower() != "all":
        if category.lower() in ["local seo", "local"]:
            query = query.where(
                (SEOIssue.category == "Local SEO") |
                (SEOIssue.category.ilike("%Local%")) |
                (SEOIssue.category == "Schema & Structured Data") |
                (SEOIssue.category == "Google Business Profile")
            )
        else:
            query = query.where(SEOIssue.category.ilike(f"%{category}%"))
    if severity and severity.lower() != "all":
        try:
            query = query.where(SEOIssue.severity == IssueSeverity(severity.lower()))
        except ValueError:
            pass
    if status_filter and status_filter.lower() != "all":
        try:
            query = query.where(SEOIssue.status == IssueStatus(status_filter.lower()))
        except ValueError:
            pass

    result = await db.execute(query.order_by(SEOIssue.id.desc()))
    return result.scalars().all()

@router.get("/{project_id}/pages", response_model=List[WebsitePageOut])
@router.get("/pages/{project_id}", response_model=List[WebsitePageOut])
async def list_crawled_pages(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    web_res = await db.execute(select(Website).where(Website.project_id == project_id))
    website = web_res.scalars().first()
    if not website:
        return []

    result = await db.execute(
        select(WebsitePage).where(WebsitePage.website_id == website.id).order_by(WebsitePage.id.asc())
    )
    return result.scalars().all()

@router.get("/issues/{project_id}", response_model=List[SEOIssueOut])
@router.get("/website/{project_id}/issues", response_model=List[SEOIssueOut])
async def list_project_issues_alias(
    project_id: int,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await list_project_issues(
        project_id=project_id,
        category=category,
        severity=severity,
        status_filter=status_filter,
        current_user=current_user,
        db=db
    )

@router.get("/{project_id}/diagnostic-summary")
@router.get("/summary/{project_id}")
@router.get("/diagnostic-summary/{project_id}")
@router.get("/website/{project_id}/summary")
async def get_diagnostic_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    # 1. Project & Location
    proj_res = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.id == project_id)
    )
    project = proj_res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    location = project.locations[0] if project.locations else None

    # 2. Latest Audit
    audit_res = await db.execute(
        select(SEOAudit)
        .options(selectinload(SEOAudit.issues))
        .where(SEOAudit.project_id == project_id)
        .order_by(SEOAudit.id.desc())
    )
    latest_audit = audit_res.scalars().first()

    # 3. Google Business Profile via GoogleAccount or GoogleConnection
    acc_res = await db.execute(
        select(GoogleAccount).where(GoogleAccount.project_id == project_id)
    )
    google_acc = acc_res.scalars().first()
    if not google_acc:
        from app.services.google.connections_service import GoogleConnectionsService
        gbp_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)
        if gbp_conn and gbp_conn.status in ("connected", "expired") and gbp_conn.access_token:
            google_acc = GoogleAccount(
                project_id=project_id,
                account_email=gbp_conn.account_email or f"user-{project_id}@google.com",
                access_token=gbp_conn.access_token,
                refresh_token=gbp_conn.refresh_token,
                token_expiry=gbp_conn.token_expiry,
                scopes=gbp_conn.scopes or [],
                is_connected=True
            )
            db.add(google_acc)
            await db.flush()

    gbp = None
    if google_acc:
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == google_acc.id)
        )
        gbp = gbp_res.scalars().first()

    # 4. Citations
    cit_res = await db.execute(select(Citation).where(Citation.project_id == project_id))
    citations = cit_res.scalars().all()
    cit_mismatches = [c for c in citations if c.nap_status == "mismatch" or c.status == "incorrect"]

    # 5. Reviews
    rev_res = await db.execute(select(Review).where(Review.project_id == project_id))
    reviews = rev_res.scalars().all()
    unanswered_reviews = [r for r in reviews if r.response_status == "unanswered"]
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0.0

    # 6. Build Discrepancy Matrix (Website vs GBP vs Citations)
    web_name = project.name
    web_phone = location.phone if location else None
    web_addr = location.address if location else None
    web_domain = project.domain

    gbp_name = gbp.business_name if gbp else None
    gbp_phone = gbp.phone if gbp else None
    gbp_addr = gbp.address if gbp else None
    gbp_url = gbp.website_url if gbp else None

    def clean_str(s):
        return s.strip().lower() if s else ""

    def clean_phone(p):
        import re
        return re.sub(r"[^\d+]", "", p) if p else ""

    name_aligned = bool(gbp_name and clean_str(web_name) == clean_str(gbp_name))
    phone_aligned = bool(gbp_phone and clean_phone(web_phone) == clean_phone(gbp_phone))
    addr_aligned = bool(gbp_addr and clean_str(web_addr) == clean_str(gbp_addr))
    url_aligned = bool(gbp_url and web_domain and clean_str(web_domain) in clean_str(gbp_url))

    discrepancy_matrix = {
        "business_name": {
            "website": web_name,
            "gbp": gbp_name,
            "citations_mismatches": len([c for c in cit_mismatches if c.found_name and clean_str(c.found_name) != clean_str(web_name)]),
            "is_aligned": name_aligned if gbp else None
        },
        "phone": {
            "website": web_phone,
            "gbp": gbp_phone,
            "citations_mismatches": len([c for c in cit_mismatches if c.found_phone and clean_phone(c.found_phone) != clean_phone(web_phone)]),
            "is_aligned": phone_aligned if gbp else None
        },
        "address": {
            "website": web_addr,
            "gbp": gbp_addr,
            "citations_mismatches": len([c for c in cit_mismatches if c.found_address and clean_str(c.found_address) != clean_str(web_addr)]),
            "is_aligned": addr_aligned if gbp else None
        },
        "website_url": {
            "website": f"https://{web_domain}" if web_domain else None,
            "gbp": gbp_url,
            "is_aligned": url_aligned if gbp else None
        }
    }

    # Calculate honest component scores when project level overrides are not stored
    gbp_calc_score = None
    if gbp:
        alignment_fields = [name_aligned, phone_aligned, addr_aligned, url_aligned]
        gbp_calc_score = round((sum(1 for f in alignment_fields if f) / len(alignment_fields)) * 100)

    cit_calc_score = None
    if citations:
        matching_cits = max(0, len(citations) - len(cit_mismatches))
        cit_calc_score = round((matching_cits / len(citations)) * 100)

    # Pillar Scores - honest evaluation, None if data source is absent
    pillar_scores = {
        "crawl_health": latest_audit.overall_score if latest_audit else project.technical_score,
        "onpage_content": project.onpage_score,
        "schema_structured_data": project.local_score,
        "gbp_alignment": project.gbp_score if project.gbp_score is not None else gbp_calc_score,
        "citations_nap": project.citations_score if project.citations_score is not None else cit_calc_score,
        "reviews_reputation": project.reviews_score if project.reviews_score is not None else (round(avg_rating * 20) if reviews else None)
    }

    issues_out = []
    if latest_audit and latest_audit.issues:
        for i in latest_audit.issues:
            issues_out.append({
                "id": i.id,
                "category": i.category,
                "severity": i.severity.value if hasattr(i.severity, "value") else str(i.severity),
                "title": i.title,
                "evidence": i.evidence,
                "why_it_matters": i.why_it_matters,
                "recommended_solution": i.recommended_solution,
                "action_type": i.action_type,
                "affected_url": i.affected_url,
                "status": i.status.value if hasattr(i.status, "value") else str(i.status)
            })

    pillar_weights = SEOAuditor.get_pillar_weights_formatted()
    scoring_methodology = SEOAuditor.get_scoring_methodology()

    return {
        "project_id": project_id,
        "overall_score": latest_audit.overall_score if latest_audit else project.health_score,
        "pages_analyzed": latest_audit.pages_analyzed if latest_audit else 0,
        "critical_issues": latest_audit.critical_issues if latest_audit else 0,
        "warnings": latest_audit.warnings if latest_audit else 0,
        "opportunities": latest_audit.opportunities if latest_audit else 0,
        "passed_checks": latest_audit.passed_checks if latest_audit else 0,
        "pillar_scores": pillar_scores,
        "pillar_weights": pillar_weights,
        "scoring_methodology": scoring_methodology,
        "discrepancy_matrix": discrepancy_matrix,
        "gbp_status": {
            "connected": bool(gbp),
            "profile_name": gbp.business_name if gbp else None,
            "phone": gbp.phone if gbp else None,
            "address": gbp.address if gbp else None
        },
        "citations_status": {
            "total": len(citations),
            "mismatches": len(cit_mismatches),
            "active": len([c for c in citations if c.status in ["active", "listed"]])
        },
        "reviews_status": {
            "total": len(reviews),
            "average_rating": avg_rating,
            "unanswered": len(unanswered_reviews)
        },
        "issues": issues_out
    }

