from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project, Website, Location
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.models.local_seo import Citation, Review, Competitor
from app.models.ranking import Keyword
from app.models.audit import SEOAudit, SEOIssue, WebsitePage, IssueSeverity, IssueStatus
from app.schemas.audit import SEOAuditOut, SEOIssueOut, WebsitePageOut, CrawlRequest
from app.services.crawler import WebsiteCrawler
from app.services.seo_auditor import SEOAuditor

router = APIRouter(prefix="/audits", tags=["Audits & Crawler"])

async def run_crawler_and_audit_task(project_id: int, start_url: str, max_pages: int = 15):
    crawler = WebsiteCrawler(start_url=start_url, max_pages=max_pages)
    pages_data = await crawler.crawl()

    async with AsyncSessionLocal() as session:
        # Find or create website
        web_res = await session.execute(select(Website).where(Website.project_id == project_id))
        website = web_res.scalars().first()
        if not website:
            website = Website(project_id=project_id, url=start_url, status="ready")
            session.add(website)
            await session.flush()

        website.status = "completed"
        website.pages_crawled = len(pages_data)
        website.last_crawled_at = datetime.now(timezone.utc)

        # Clear old pages for clean re-audit
        old_pages_res = await session.execute(select(WebsitePage).where(WebsitePage.website_id == website.id))
        for old_p in old_pages_res.scalars().all():
            await session.delete(old_p)
        await session.flush()

        # Save new crawled pages
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

        # Load GBP context via GoogleAccount
        acc_res = await session.execute(
            select(GoogleAccount).where(GoogleAccount.project_id == project_id)
        )
        google_account = acc_res.scalars().first()
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

        # Run Local SEO Rule Engine
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

        # Save Issues
        for iss in audit_result["issues"]:
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
            proj.technical_score = pillars.get("crawl_health", audit_result["score"])
            proj.onpage_score = pillars.get("onpage_content", audit_result["score"])
            proj.local_score = pillars.get("schema_structured_data", audit_result["score"])
            proj.gbp_score = pillars.get("gbp_alignment", 70)
            proj.citations_score = pillars.get("citations_nap", 75)
            proj.reviews_score = pillars.get("reviews_reputation", 80)

        await session.commit()

@router.post("/crawl/{project_id}")
async def trigger_crawl(
    project_id: int,
    crawl_in: CrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    proj = proj_res.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    background_tasks.add_task(
        run_crawler_and_audit_task,
        project_id=project_id,
        start_url=crawl_in.url,
        max_pages=crawl_in.max_pages or 15
    )

    return {"message": "Local Website Crawl & Local SEO Audit task queued", "status": "queued"}

@router.get("/{project_id}/latest", response_model=Optional[SEOAuditOut])
async def get_latest_audit(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SEOAudit)
        .options(selectinload(SEOAudit.issues))
        .where(SEOAudit.project_id == project_id)
        .order_by(SEOAudit.id.desc())
    )
    return result.scalars().first()

@router.get("/{project_id}/issues", response_model=List[SEOIssueOut])
async def list_project_issues(
    project_id: int,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(SEOIssue).where(SEOIssue.project_id == project_id)
    if category:
        query = query.where(SEOIssue.category == category)
    if severity:
        query = query.where(SEOIssue.severity == IssueSeverity(severity))
    if status_filter:
        query = query.where(SEOIssue.status == IssueStatus(status_filter))

    result = await db.execute(query.order_by(SEOIssue.id.desc()))
    return result.scalars().all()

@router.get("/{project_id}/pages", response_model=List[WebsitePageOut])
@router.get("/pages/{project_id}", response_model=List[WebsitePageOut])
async def list_crawled_pages(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    web_res = await db.execute(select(Website).where(Website.project_id == project_id))
    website = web_res.scalars().first()
    if not website:
        return []

    result = await db.execute(
        select(WebsitePage).where(WebsitePage.website_id == website.id).order_by(WebsitePage.id.asc())
    )
    return result.scalars().all()

@router.get("/issues/{project_id}", response_model=List[SEOIssueOut])
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
async def get_diagnostic_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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

    # 3. Google Business Profile via GoogleAccount
    acc_res = await db.execute(
        select(GoogleAccount).where(GoogleAccount.project_id == project_id)
    )
    google_acc = acc_res.scalars().first()
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
            "citations_mismatches": len([c for c in cit_mismatches if c.name and clean_str(c.name) != clean_str(web_name)]),
            "is_aligned": name_aligned if gbp else True
        },
        "phone": {
            "website": web_phone,
            "gbp": gbp_phone,
            "citations_mismatches": len([c for c in cit_mismatches if c.phone and clean_phone(c.phone) != clean_phone(web_phone)]),
            "is_aligned": phone_aligned if gbp else True
        },
        "address": {
            "website": web_addr,
            "gbp": gbp_addr,
            "citations_mismatches": len([c for c in cit_mismatches if c.address and clean_str(c.address) != clean_str(web_addr)]),
            "is_aligned": addr_aligned if gbp else True
        },
        "website_url": {
            "website": f"https://{web_domain}" if web_domain else None,
            "gbp": gbp_url,
            "is_aligned": url_aligned if gbp else True
        }
    }

    # Pillar Scores
    pillar_scores = {
        "crawl_health": project.technical_score or (latest_audit.overall_score if latest_audit else 75),
        "onpage_content": project.onpage_score or 72,
        "schema_structured_data": project.local_score or 65,
        "gbp_alignment": project.gbp_score or (85 if (gbp and name_aligned and phone_aligned) else 50),
        "citations_nap": project.citations_score or (80 if not cit_mismatches else 60),
        "reviews_reputation": project.reviews_score or (85 if not unanswered_reviews else 65)
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

    return {
        "project_id": project_id,
        "overall_score": latest_audit.overall_score if latest_audit else (project.health_score or 72),
        "pages_analyzed": latest_audit.pages_analyzed if latest_audit else 0,
        "critical_issues": latest_audit.critical_issues if latest_audit else 0,
        "warnings": latest_audit.warnings if latest_audit else 0,
        "opportunities": latest_audit.opportunities if latest_audit else 0,
        "passed_checks": latest_audit.passed_checks if latest_audit else 0,
        "pillar_scores": pillar_scores,
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
            "active": len([c for c in citations if c.status == "active"])
        },
        "reviews_status": {
            "total": len(reviews),
            "average_rating": avg_rating,
            "unanswered": len(unanswered_reviews)
        },
        "issues": issues_out
    }
