"""
LocalLift — 20-Category Local SEO Audit Framework Engine

Defines the hierarchical audit framework:
AuditFramework -> AuditCategory -> AuditCheck -> Weight -> Finding -> Category Score -> Overall Score

All findings carry provenance, traceable evidence, and status (PASS, PARTIAL, FAIL, NOT_VERIFIED, NOT_APPLICABLE, ERROR).
No fabricated scores: categories without evidence return NOT_VERIFIED and are excluded from score inflation.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.audit import LocalAuditRun, LocalAuditFinding, SEOAudit, WebsitePage, AuditJob, AuditJobStatus
from app.models.project import Project, Website
from app.models.local_seo import (
    BusinessProfile, Citation, Review, Competitor, SchemaRecord,
    VerificationStatus, FindingStatus
)
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.models.ranking import GeoGridScan
from app.services.local_seo.business_profile_service import BusinessProfileService
from app.services.local_seo.nap_service import NAPComparisonService

logger = logging.getLogger("locallift.audit_framework")


# 20 Standard Local SEO Audit Categories with default weights (summing to 100)
AUDIT_FRAMEWORK_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "google_business_profile": {"name": "Google Business Profile", "weight": 10.0},
    "categories_taxonomy": {"name": "Categories & Taxonomy", "weight": 5.0},
    "reviews_reputation": {"name": "Reviews & Reputation", "weight": 8.0},
    "nap_consistency": {"name": "NAP Consistency", "weight": 8.0},
    "local_onpage_seo": {"name": "Local On-Page SEO", "weight": 8.0},
    "proximity_location": {"name": "Proximity & Service Area", "weight": 6.0},
    "citations_directories": {"name": "Citations & Directories", "weight": 6.0},
    "local_backlinks": {"name": "Local Backlinks", "weight": 4.0},
    "review_responses": {"name": "Review Response Rate", "weight": 4.0},
    "gbp_media": {"name": "GBP Photos & Media", "weight": 4.0},
    "local_landing_pages": {"name": "Local Landing Pages", "weight": 5.0},
    "gbp_activity": {"name": "GBP Posts & Activity", "weight": 3.0},
    "website_authority": {"name": "Website Authority", "weight": 4.0},
    "internal_linking": {"name": "Internal Linking & Siloing", "weight": 3.0},
    "technical_seo": {"name": "Technical SEO & Mobile", "weight": 5.0},
    "schema_localbusiness": {"name": "LocalBusiness Schema", "weight": 7.0},
    "local_content": {"name": "Local Content & Relevance", "weight": 4.0},
    "social_brand_signals": {"name": "Social & Brand Signals", "weight": 2.0},
    "user_engagement": {"name": "User Experience & Engagement", "weight": 2.0},
    "competitor_market_analysis": {"name": "Competitor Market Analysis", "weight": 2.0}
}

DEFAULT_CATEGORY_WEIGHTS: Dict[str, float] = {
    k: v["weight"] for k, v in AUDIT_FRAMEWORK_CATEGORIES.items()
}


class LocalSEOAuditFramework:
    """
    Authoritative evaluation engine across all 20 Local SEO categories.
    """

    @classmethod
    async def ensure_fresh_technical_crawl(
        cls,
        project_id: int,
        db: AsyncSession,
        freshness_hours: int = 24,
        force_crawl: bool = False,
        crawl_snapshot_id: Optional[int] = None
    ) -> Tuple[Optional[SEOAudit], Optional[AuditJob], Optional[str]]:
        """
        Determines whether a usable technical crawl exists for the project.
        - If crawl_snapshot_id is provided: directly fetches and reuses that specific crawl snapshot (never starts a new crawl).
        - If fresh usable crawl exists: returns (latest_crawl_audit, latest_job, None)
        - If no usable crawl exists or stale and not snapshot: executes crawler, awaits completion, persists records, returns fresh data
        - If crawl fails: returns (None, latest_job, error_message)
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch project info
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            return None, None, "Project not found"

        # If specific crawl snapshot ID is provided (e.g. from Central Intelligence Scan), resolve it directly
        if crawl_snapshot_id:
            job_res = await db.execute(
                select(AuditJob).where(AuditJob.id == crawl_snapshot_id, AuditJob.project_id == project_id)
            )
            specific_job = job_res.scalars().first()

            audit_res = await db.execute(
                select(SEOAudit)
                .options(selectinload(SEOAudit.issues))
                .where(SEOAudit.project_id == project_id)
                .order_by(SEOAudit.id.desc())
            )
            specific_audit = audit_res.scalars().first()

            if specific_job and specific_job.status in (AuditJobStatus.FAILED, AuditJobStatus.CANCELLED):
                return None, specific_job, specific_job.error_message or "Technical crawl failed during execution"

            return specific_audit, specific_job, None

        # 2. Check existing SEOAudit and AuditJob
        audit_res = await db.execute(
            select(SEOAudit)
            .options(selectinload(SEOAudit.issues))
            .where(SEOAudit.project_id == project_id)
            .order_by(SEOAudit.id.desc())
        )
        latest_crawl_audit = audit_res.scalars().first()

        job_res = await db.execute(
            select(AuditJob)
            .where(AuditJob.project_id == project_id, AuditJob.job_type == "website_audit")
            .order_by(AuditJob.id.desc())
        )
        latest_job = job_res.scalars().first()

        # Check if fresh and valid
        is_fresh = False
        if not force_crawl and latest_crawl_audit and (latest_crawl_audit.pages_analyzed or 0) > 0 and latest_crawl_audit.overall_score is not None:
            if latest_job and latest_job.status in (AuditJobStatus.COMPLETED, AuditJobStatus.COMPLETED_WITH_ERRORS):
                audit_time = latest_crawl_audit.created_at or latest_job.completed_at
                if audit_time:
                    if audit_time.tzinfo is None:
                        audit_time = audit_time.replace(tzinfo=timezone.utc)
                    age_hours = (now - audit_time).total_seconds() / 3600.0
                    if age_hours <= freshness_hours:
                        is_fresh = True
            elif not latest_job:
                audit_time = latest_crawl_audit.created_at
                if audit_time:
                    if audit_time.tzinfo is None:
                        audit_time = audit_time.replace(tzinfo=timezone.utc)
                    age_hours = (now - audit_time).total_seconds() / 3600.0
                    if age_hours <= freshness_hours:
                        is_fresh = True

        if is_fresh:
            logger.info(f"[LOCAL_AUDIT_FRAMEWORK] Reusing valid fresh crawl audit #{latest_crawl_audit.id} for project {project_id}")
            return latest_crawl_audit, latest_job, None

        # If not forcing crawl and the latest job failed recently, report the failure truthfully rather than looping indefinitely
        if not force_crawl and latest_job and latest_job.status in (AuditJobStatus.FAILED, AuditJobStatus.CANCELLED):
            job_time = latest_job.failed_at or latest_job.completed_at or latest_job.created_at
            if job_time:
                if job_time.tzinfo is None:
                    job_time = job_time.replace(tzinfo=timezone.utc)
                age_hours = (now - job_time).total_seconds() / 3600.0
                if age_hours <= freshness_hours:
                    logger.info(f"[LOCAL_AUDIT_FRAMEWORK] Recent failed crawl job #{latest_job.id} for project {project_id}: {latest_job.error_message}")
                    return None, latest_job, latest_job.error_message or "Technical crawl failed during execution"

        # 3. Target URL determination
        target_domain = project.domain or ""
        if not target_domain:
            web_res = await db.execute(select(Website).where(Website.project_id == project_id))
            web = web_res.scalars().first()
            if web and web.url:
                target_domain = web.url

        if not target_domain:
            logger.warning(f"[LOCAL_AUDIT_FRAMEWORK] Project {project_id} has no domain/website configured for crawl.")
            return latest_crawl_audit, latest_job, "No target website URL configured for this project"

        start_url = target_domain if target_domain.startswith("http") else f"https://{target_domain}"
        logger.info(f"[LOCAL_AUDIT_FRAMEWORK] Initiating technical crawl for project {project_id} at {start_url}")

        crawl_opts = {
            "url": start_url,
            "max_pages": 20,
            "respect_robots": True,
            "crawl_delay_ms": 150,
            "follow_redirects": True,
            "allow_local_dev": True,
            "max_depth": 3,
            "check_external_links": True,
            "max_external_links": 30
        }

        # Create AuditJob
        audit_job = AuditJob(
            project_id=project_id,
            organization_id=project.organization_id,
            job_type="website_audit",
            status=AuditJobStatus.QUEUED,
            crawler_status="queued",
            progress=0.0,
            current_stage="Local SEO Audit initiating technical crawl",
            start_url=start_url,
            options_snapshot=crawl_opts
        )
        db.add(audit_job)
        await db.commit()
        await db.refresh(audit_job)
        job_id = audit_job.id

        try:
            from app.api.v1.audits import run_crawler_and_audit_task
            await run_crawler_and_audit_task(
                job_id=job_id,
                project_id=project_id,
                start_url=start_url,
                crawl_options=crawl_opts
            )

            # Reload fresh records
            fresh_audit_res = await db.execute(
                select(SEOAudit)
                .options(selectinload(SEOAudit.issues))
                .where(SEOAudit.project_id == project_id)
                .order_by(SEOAudit.id.desc())
            )
            fresh_audit = fresh_audit_res.scalars().first()

            fresh_job_res = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
            fresh_job = fresh_job_res.scalars().first()

            if fresh_job and fresh_job.status == AuditJobStatus.FAILED:
                return None, fresh_job, fresh_job.error_message or "Technical crawl failed"

            if fresh_job and (fresh_job.pages_crawled or 0) == 0 and (fresh_job.pages_failed or 0) > 0:
                return None, fresh_job, fresh_job.error_message or fresh_job.current_stage or "Technical crawl could not connect to target host"

            return fresh_audit, fresh_job, None

        except Exception as crawl_err:
            err_msg = str(crawl_err)
            logger.error(f"[LOCAL_AUDIT_FRAMEWORK] Technical crawl execution error: {err_msg}")
            
            fail_job_res = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
            fail_job = fail_job_res.scalars().first()
            if fail_job:
                fail_job.status = AuditJobStatus.FAILED
                fail_job.error_message = err_msg
                fail_job.failed_at = datetime.now(timezone.utc)
                await db.commit()

            return None, fail_job, err_msg

    @classmethod
    async def run_audit(
        cls,
        project_id: int,
        db: AsyncSession,
        framework_version: str = "local_seo_v1",
        freshness_hours: int = 24,
        force_crawl: bool = False,
        crawl_snapshot_id: Optional[int] = None
    ) -> LocalAuditRun:
        """
        Executes a complete Local SEO audit for the specified project.
        Creates and persists LocalAuditRun and all LocalAuditFinding entries with forensic evidence.
        """
        started_at = datetime.now(timezone.utc)
        now = started_at
        profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)

        # 1. Fetch available data sources
        # Citations
        cit_res = await db.execute(select(Citation).where(Citation.project_id == project_id))
        citations = cit_res.scalars().all()

        # Reviews
        rev_res = await db.execute(select(Review).where(Review.project_id == project_id))
        reviews = rev_res.scalars().all()

        # Competitors
        comp_res = await db.execute(select(Competitor).where(Competitor.project_id == project_id))
        competitors = comp_res.scalars().all()

        # Schema Records
        sch_res = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
        schema_records = sch_res.scalars().all()

        # Technical/Crawl Audit (Ensuring fresh execution or using supplied snapshot)
        latest_crawl_audit, latest_job, crawler_error = await cls.ensure_fresh_technical_crawl(
            project_id=project_id,
            db=db,
            freshness_hours=freshness_hours,
            force_crawl=force_crawl,
            crawl_snapshot_id=crawl_snapshot_id
        )

        # Crawled Pages
        pages_res = await db.execute(
            select(WebsitePage)
            .join(Website, WebsitePage.website_id == Website.id)
            .where(Website.project_id == project_id)
        )
        crawled_pages = pages_res.scalars().all()

        # Fetch Project for domain context
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()

        # 1. Fetch exact project-bound Google Business Profile
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
        )
        gbp = gbp_res.scalars().first()

        # GeoGrid Latest
        grid_res = await db.execute(
            select(GeoGridScan)
            .where(GeoGridScan.project_id == project_id)
            .order_by(GeoGridScan.id.desc())
        )
        latest_grid = grid_res.scalars().first()

        # NAP Check
        nap_data = await NAPComparisonService.compare_project_nap(project_id, db)

        # 2. Evaluate each of the 20 Categories
        findings: List[Dict[str, Any]] = []

        # Category 1: Google Business Profile
        if gbp:
            status = FindingStatus.PASS.value if gbp.is_verified else FindingStatus.PARTIAL.value
            sync_time = gbp.last_synced_at.strftime("%d %b %Y, %H:%M") if gbp.last_synced_at else "Initial sync"
            findings.append({
                "category": "google_business_profile",
                "check_key": "gbp_claimed_verified",
                "title": "Google Business Profile Verification Status",
                "status": status,
                "severity": "info" if gbp.is_verified else "warning",
                "evidence": f"Bound GBP profile '{gbp.business_name}' is {'verified' if gbp.is_verified else 'unverified/unclaimed'}. (Data last synchronized: {sync_time})",
                "source": "Connected Google Business Profile",
                "source_url": gbp.website_url,
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Maintain verified ownership and monitor profile status regularly."
            })
        else:
            findings.append({
                "category": "google_business_profile",
                "check_key": "gbp_connection",
                "title": "Google Business Profile Connection",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "Google Business Profile is not connected for this project.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Connect your Google Business Profile to verify ownership and synchronize listing attributes."
            })

        # Category 2: Categories Taxonomy
        effective_category = (gbp.primary_category if gbp and gbp.primary_category else None) or profile.primary_category
        cat_source = "Connected Google Business Profile" if (gbp and gbp.primary_category) else "Project Data"
        if effective_category and effective_category != "Local Business":
            add_cats = f" (Additional categories: {', '.join(gbp.additional_categories)})" if (gbp and gbp.additional_categories) else ""
            findings.append({
                "category": "categories_taxonomy",
                "check_key": "primary_category_selected",
                "title": "Specific Primary Business Category Configured",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": f"Primary category configured as '{effective_category}'{add_cats}.",
                "source": cat_source,
                "verification_status": VerificationStatus.VERIFIED.value if gbp else VerificationStatus.USER_PROVIDED.value,
                "confidence": "HIGH",
                "recommendation": "Ensure primary category accurately reflects your core high-intent commercial service."
            })
        else:
            findings.append({
                "category": "categories_taxonomy",
                "check_key": "primary_category_selected",
                "title": "Specific Primary Business Category Missing",
                "status": FindingStatus.FAIL.value,
                "severity": "critical",
                "evidence": "Primary category is either unassigned or set to generic 'Local Business'.",
                "source": cat_source,
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Select an exact Google/Schema primary category for this business."
            })

        # Category 3: Reviews & Reputation
        if reviews:
            avg_rating = sum(r.rating for r in reviews) / len(reviews)
            status = FindingStatus.PASS.value if avg_rating >= 4.5 else (FindingStatus.PARTIAL.value if avg_rating >= 3.8 else FindingStatus.FAIL.value)
            rev_source = "Connected Google Business Profile" if (gbp and any(r.source == "Google" for r in reviews)) else "Review Sync Engine"
            findings.append({
                "category": "reviews_reputation",
                "check_key": "review_rating_threshold",
                "title": "Customer Review Rating Score",
                "status": status,
                "severity": "info" if avg_rating >= 4.5 else "warning",
                "evidence": f"{len(reviews)} reviews recorded with average rating of {round(avg_rating, 2)}★.",
                "source": rev_source,
                "verification_status": VerificationStatus.OBSERVED.value,
                "confidence": "HIGH",
                "recommendation": "Maintain proactive review generation to keep rating above 4.5★."
            })
        else:
            findings.append({
                "category": "reviews_reputation",
                "check_key": "review_presence",
                "title": "Customer Review Volume",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "No customer reviews synchronized or recorded for this project.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Synchronize Google and directory reviews to establish reputation metrics."
            })

        # Category 4: NAP Consistency
        if nap_data["total_sources_checked"] > 0:
            nap_score = nap_data["nap_score"] or 0
            status = FindingStatus.PASS.value if nap_score >= 90 else (FindingStatus.PARTIAL.value if nap_score >= 70 else FindingStatus.FAIL.value)
            nap_source = "Connected Google Business Profile" if gbp else "NAP Comparison Engine"
            findings.append({
                "category": "nap_consistency",
                "check_key": "nap_uniformity",
                "title": "Name, Address, and Phone Consistency",
                "status": status,
                "severity": "info" if nap_score >= 90 else "critical",
                "evidence": f"Checked {nap_data['total_sources_checked']} sources: {nap_data['consistent_sources']} consistent, {nap_data['mismatch_sources']} mismatches ({nap_score}% alignment).",
                "source": nap_source,
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Correct directory discrepancies where phone, address, or business name diverge."
            })
        else:
            findings.append({
                "category": "nap_consistency",
                "check_key": "nap_sources",
                "title": "NAP Verification Sources",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "No directory citations or GBP profiles available to verify NAP consistency.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Add citations or connect GBP to enable automated NAP verification."
            })

        # Category 5: Local On-Page SEO
        if crawled_pages:
            pages_with_geo = [p for p in crawled_pages if profile.city and p.title and profile.city.lower() in p.title.lower()]
            status = FindingStatus.PASS.value if len(pages_with_geo) > 0 else FindingStatus.FAIL.value
            findings.append({
                "category": "local_onpage_seo",
                "check_key": "geo_keyword_in_title",
                "title": "City / Geo Targeting in Page Title",
                "status": status,
                "severity": "info" if status == FindingStatus.PASS.value else "warning",
                "evidence": f"{len(pages_with_geo)} of {len(crawled_pages)} crawled pages include target city '{profile.city}' in the title tag.",
                "source": "Website Crawl",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": f"Include target city '{profile.city or 'Service Area'}' and primary service keyword in prominent page titles."
            })
        else:
            findings.append({
                "category": "local_onpage_seo",
                "check_key": "crawl_pages_analyzed",
                "title": "Website On-Page Signals",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Website has not yet been crawled for this project.",
                "source": "Website Crawl",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Launch a website audit crawl to inspect on-page metadata, headings, and geo-relevance."
            })

        # Category 6: Proximity & Location Signals
        has_gbp_coords = gbp is not None and gbp.latitude is not None and gbp.longitude is not None
        has_coords = has_gbp_coords or (profile.latitude is not None and profile.longitude is not None)
        active_lat = gbp.latitude if has_gbp_coords else profile.latitude
        active_lng = gbp.longitude if has_gbp_coords else profile.longitude
        findings.append({
            "category": "proximity_location",
            "check_key": "geo_coordinates_bound",
            "title": "Geographic Latitude & Longitude Coordinates",
            "status": FindingStatus.PASS.value if has_coords else FindingStatus.FAIL.value,
            "severity": "info" if has_coords else "critical",
            "evidence": f"Canonical coordinates: {active_lat}, {active_lng}" if has_coords else "No geographic coordinates configured.",
            "source": "Connected Google Business Profile" if has_gbp_coords else "Project Data",
            "verification_status": VerificationStatus.VERIFIED.value if has_coords else VerificationStatus.NOT_VERIFIED.value,
            "confidence": "HIGH",
            "recommendation": "Geocode the physical business address to establish exact proximity ranking boundaries."
        })

        # Category 7: Citations & Directory Listings
        if citations:
            listed_cits = [c for c in citations if c.status == "listed"]
            status = FindingStatus.PASS.value if len(listed_cits) >= 5 else FindingStatus.PARTIAL.value
            findings.append({
                "category": "citations_directories",
                "check_key": "directory_citation_volume",
                "title": "Local Directory Citation Presence",
                "status": status,
                "severity": "info" if status == FindingStatus.PASS.value else "warning",
                "evidence": f"{len(listed_cits)} active directory citations tracked out of {len(citations)} total.",
                "source": "Citations Registry",
                "verification_status": VerificationStatus.OBSERVED.value,
                "confidence": "HIGH",
                "recommendation": "Claim listings on major industry and regional directories."
            })
        else:
            findings.append({
                "category": "citations_directories",
                "check_key": "citation_presence",
                "title": "Local Directory Citation Presence",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "No citations recorded for this project.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Audit and import local business citations across Apple Maps, Bing, Yelp, and regional portals."
            })

        # Category 8: Local Backlinks
        findings.append({
            "category": "local_backlinks",
            "check_key": "backlink_signals",
            "title": "Local Authority Inbound Backlinks",
            "status": FindingStatus.NOT_VERIFIED.value,
            "severity": "info",
            "evidence": "External backlink crawler integration not connected.",
            "source": "Project Data",
            "verification_status": VerificationStatus.NOT_VERIFIED.value,
            "confidence": "HIGH",
            "recommendation": "Build inbound links from local chambers of commerce, sponsorships, and local news outlets."
        })

        # Category 9: Review Responses
        if reviews:
            answered = [r for r in reviews if r.response_status in ["published", "approved"]]
            response_pct = round((len(answered) / len(reviews)) * 100)
            status = FindingStatus.PASS.value if response_pct >= 80 else (FindingStatus.PARTIAL.value if response_pct >= 50 else FindingStatus.FAIL.value)
            findings.append({
                "category": "review_responses",
                "check_key": "owner_response_rate",
                "title": "Owner Response Rate to Customer Reviews",
                "status": status,
                "severity": "info" if response_pct >= 80 else "warning",
                "evidence": f"{len(answered)} of {len(reviews)} reviews answered ({response_pct}% response rate).",
                "source": "Connected Google Business Profile" if gbp else "Review Sync Engine",
                "verification_status": VerificationStatus.OBSERVED.value,
                "confidence": "HIGH",
                "recommendation": "Respond promptly to all customer reviews, acknowledging positive feedback and resolving issues."
            })
        else:
            findings.append({
                "category": "review_responses",
                "check_key": "owner_response_rate",
                "title": "Review Response Tracking",
                "status": FindingStatus.NOT_APPLICABLE.value,
                "severity": "info",
                "evidence": "No reviews present to evaluate owner responses.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_APPLICABLE.value,
                "confidence": "HIGH",
                "recommendation": "Collect initial customer reviews before tracking response rate."
            })

        # Category 10: GBP Photos & Media
        if gbp and gbp.photos_count > 0:
            findings.append({
                "category": "gbp_media",
                "check_key": "photo_upload_count",
                "title": "Google Business Profile Photo Asset Volume",
                "status": FindingStatus.PASS.value if gbp.photos_count >= 10 else FindingStatus.PARTIAL.value,
                "severity": "info" if gbp.photos_count >= 10 else "warning",
                "evidence": f"{gbp.photos_count} photos recorded on bound Google Business Profile.",
                "source": "Connected Google Business Profile",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Upload high-quality geotagged photos of your storefront, team, and projects regularly."
            })
        elif gbp:
            findings.append({
                "category": "gbp_media",
                "check_key": "photo_upload_count",
                "title": "Google Business Profile Photo Assets",
                "status": FindingStatus.FAIL.value,
                "severity": "warning",
                "evidence": "0 photos recorded on bound Google Business Profile.",
                "source": "Connected Google Business Profile",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Upload high-resolution photos to your Google Business Profile."
            })
        else:
            findings.append({
                "category": "gbp_media",
                "check_key": "photo_upload_count",
                "title": "Google Business Profile Photo Assets",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Google Business Profile not connected.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Connect Google Business Profile to verify photo assets."
            })

        # Category 11: Local Landing Pages
        if crawled_pages:
            findings.append({
                "category": "local_landing_pages",
                "check_key": "landing_page_presence",
                "title": "Dedicated Local Service Landing Pages",
                "status": FindingStatus.PASS.value if len(crawled_pages) >= 3 else FindingStatus.PARTIAL.value,
                "severity": "info",
                "evidence": f"{len(crawled_pages)} total crawl pages discovered.",
                "source": "Website Crawl",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Create dedicated service-location landing pages for each target suburb or neighborhood."
            })
        else:
            findings.append({
                "category": "local_landing_pages",
                "check_key": "landing_page_presence",
                "title": "Dedicated Local Service Landing Pages",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Crawl data not available to evaluate local landing pages.",
                "source": "Website Crawl",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Perform website crawl to catalog landing pages."
            })

        # Category 12: GBP Activity & Posts
        if gbp and gbp.posts_count > 0:
            findings.append({
                "category": "gbp_activity",
                "check_key": "post_recency",
                "title": "Google Business Profile Update Frequency",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": f"{gbp.posts_count} posts recorded on bound Google Business Profile.",
                "source": "Connected Google Business Profile",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Publish weekly Google updates, offers, and seasonal announcements."
            })
        elif gbp:
            findings.append({
                "category": "gbp_activity",
                "check_key": "post_recency",
                "title": "Google Business Profile Updates & Posts",
                "status": FindingStatus.PARTIAL.value,
                "severity": "info",
                "evidence": "0 posts recorded on bound Google Business Profile.",
                "source": "Connected Google Business Profile",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Publish fresh updates on Google Business Profile to signal operational activity."
            })
        else:
            findings.append({
                "category": "gbp_activity",
                "check_key": "post_recency",
                "title": "Google Business Profile Updates & Posts",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Google Business Profile not connected.",
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Connect Google Business Profile to evaluate post activity."
            })

        # Category 13: Website Authority & Trust
        has_ssl = profile.website and profile.website.startswith("https://")
        findings.append({
            "category": "website_authority",
            "check_key": "ssl_https_secured",
            "title": "SSL / HTTPS Domain Security",
            "status": FindingStatus.PASS.value if has_ssl else FindingStatus.FAIL.value,
            "severity": "info" if has_ssl else "critical",
            "evidence": f"Website protocol is {'HTTPS' if has_ssl else 'insecure HTTP'}.",
            "source": "Website Inspector",
            "source_url": profile.website,
            "verification_status": VerificationStatus.DETECTED.value,
            "confidence": "HIGH",
            "recommendation": "Ensure website serves valid SSL certificate on all endpoints."
        })

        # Category 14: Internal Linking
        if crawled_pages:
            has_internal = any(p.internal_links_count > 0 for p in crawled_pages)
            findings.append({
                "category": "internal_linking",
                "check_key": "internal_link_structure",
                "title": "Internal Link Architecture Between Local Pages",
                "status": FindingStatus.PASS.value if has_internal else FindingStatus.PARTIAL.value,
                "severity": "info" if has_internal else "warning",
                "evidence": f"Evaluated internal linking across {len(crawled_pages)} crawled pages.",
                "source": "Website Crawler",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Link location pages and service pages contextually from homepage and navigation menus."
            })
        else:
            findings.append({
                "category": "internal_linking",
                "check_key": "internal_link_structure",
                "title": "Internal Link Architecture",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Website crawl not available.",
                "source": "Website Crawler",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Crawl website to evaluate internal link distribution."
            })

        # Check if the latest crawl job failed after any historical crawl audit (Test 7 requirement)
        has_failed_latest_job = (
            latest_job is not None and 
            latest_job.status in (AuditJobStatus.FAILED, AuditJobStatus.CANCELLED) and
            (not latest_crawl_audit or (latest_job.created_at or now) >= (latest_crawl_audit.created_at or now))
        )

        # Category 15: Technical SEO & Mobile
        if not has_failed_latest_job and latest_crawl_audit and (latest_crawl_audit.pages_analyzed or 0) > 0 and latest_crawl_audit.overall_score is not None:
            # 1. Overall Crawl Health & Score with Provenance
            score_status = FindingStatus.PASS.value if latest_crawl_audit.overall_score >= 80 else (FindingStatus.PARTIAL.value if latest_crawl_audit.overall_score >= 60 else FindingStatus.FAIL.value)
            crawl_date_str = latest_crawl_audit.created_at or (latest_job.completed_at if latest_job else None)
            crawl_date_fmt = crawl_date_str.strftime("%d %b %Y, %H:%M") if crawl_date_str else "Recent"
            job_id_str = f"Job #{latest_job.id}" if latest_job else f"Audit #{latest_crawl_audit.id}"
            
            # 1. Overall Crawl Health & Score with Provenance
            score_status = FindingStatus.PASS.value if latest_crawl_audit.overall_score >= 80 else (FindingStatus.PARTIAL.value if latest_crawl_audit.overall_score >= 60 else FindingStatus.FAIL.value)
            crawl_date_str = latest_crawl_audit.created_at or (latest_job.completed_at if latest_job else None)
            crawl_date_fmt = crawl_date_str.strftime("%d %b %Y, %H:%M") if crawl_date_str else "Recent"
            job_id_str = f"Job #{latest_job.id}" if latest_job else f"Audit #{latest_crawl_audit.id}"
            crawl_ev = f"Technical crawl score: {latest_crawl_audit.overall_score}/100 across {latest_crawl_audit.pages_analyzed} pages with {latest_crawl_audit.critical_issues or 0} critical issues. [Crawl: {job_id_str} | Date: {crawl_date_fmt} | Status: Completed]"
            
            findings.append({
                "category": "technical_seo",
                "check_key": "crawl_health_score",
                "title": "Technical Crawl & Accessibility Health",
                "status": score_status,
                "severity": "info" if score_status == FindingStatus.PASS.value else ("warning" if score_status == FindingStatus.PARTIAL.value else "critical"),
                "evidence": crawl_ev,
                "rule_definition": "Audits total domain technical health score, critical crawl impediments, and page accessibility.",
                "what_was_checked": f"Audited {latest_crawl_audit.pages_analyzed} crawled domain pages against technical SEO rule suite.",
                "observed_value": crawl_ev,
                "expected_value": "Technical SEO health score >= 80/100 with zero blocking critical crawler errors.",
                "why_it_matters": "Technical health directly influences Google crawl budget efficiency and indexation stability.",
                "affected_urls": [profile.website or project.domain or ""],
                "technical_evidence": {
                    "health_score": latest_crawl_audit.overall_score,
                    "pages_analyzed": latest_crawl_audit.pages_analyzed,
                    "critical_issues": latest_crawl_audit.critical_issues or 0
                },
                "remediation_steps": [
                    "Resolve critical errors listed in the Local Website & Technical Audit view.",
                    "Fix server 4xx/5xx responses and broken internal redirect hops."
                ],
                "verification_steps": [
                    "Re-run Technical Website Scan and verify overall health score exceeds 80."
                ],
                "source": "SEO Technical Auditor",
                "source_url": profile.website or (f"https://{project.domain}" if project and project.domain else None),
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Resolve broken links, redirect chains, and server errors identified in crawl audit."
            })
            
            # 2. HTTP Status & Error Codes (4xx / 5xx)
            error_pages = [p for p in crawled_pages if (p.status_code or 200) >= 400]
            if error_pages:
                err_urls = [f"{p.url} (HTTP {p.status_code})" for p in error_pages[:5]]
                findings.append({
                    "category": "technical_seo",
                    "check_key": "http_status_errors",
                    "title": "HTTP 4xx/5xx Client & Server Errors",
                    "status": FindingStatus.FAIL.value,
                    "severity": "critical",
                    "evidence": f"{len(error_pages)} of {len(crawled_pages)} crawled pages returned HTTP errors: {', '.join(err_urls)}.",
                    "rule_definition": "Inspects all crawled pages for HTTP 4xx (client error / not found) and 5xx (server error) status codes.",
                    "what_was_checked": f"Audited HTTP response codes across {len(crawled_pages)} crawled URLs.",
                    "observed_value": f"{len(error_pages)} of {len(crawled_pages)} pages returned HTTP errors.",
                    "expected_value": "All public pages return HTTP 200 OK status codes.",
                    "why_it_matters": "Broken HTTP status codes result in dropped rankings and degraded user experience.",
                    "affected_urls": [p.url for p in error_pages][:10],
                    "technical_evidence": {"error_pages_count": len(error_pages), "error_details": err_urls},
                    "remediation_steps": [
                        "Review affected URLs in server access logs.",
                        "Restore missing content or implement permanent 301 redirects to relevant active landing pages.",
                        "Update internal navigation links pointing to dead URLs."
                    ],
                    "verification_steps": [
                        "Re-run website crawler and verify 0 pages return HTTP 4xx or 5xx status codes."
                    ],
                    "source": "Website Crawler",
                    "source_url": error_pages[0].url if error_pages else None,
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Fix broken page routes or configure permanent 301 redirects to active destination URLs."
                })
            else:
                findings.append({
                    "category": "technical_seo",
                    "check_key": "http_status_errors",
                    "title": "HTTP Status & Response Codes",
                    "status": FindingStatus.PASS.value,
                    "severity": "info",
                    "evidence": f"All {len(crawled_pages)} crawled pages returned successful HTTP 200 responses without 4xx/5xx errors.",
                    "rule_definition": "Inspects all crawled pages for HTTP 4xx and 5xx error status codes.",
                    "what_was_checked": f"Audited HTTP status codes across {len(crawled_pages)} pages.",
                    "observed_value": "All crawled pages returned HTTP 200 OK.",
                    "expected_value": "100% of crawled pages return valid HTTP 200 responses.",
                    "why_it_matters": "Guarantees search spiders and visitors can access all linked pages reliably.",
                    "affected_urls": [],
                    "technical_evidence": {"crawled_count": len(crawled_pages), "error_count": 0},
                    "remediation_steps": [
                        "Maintain server uptime and periodic route validation."
                    ],
                    "verification_steps": [
                        "Confirm ongoing HTTP 200 status in periodic crawls."
                    ],
                    "source": "Website Crawler",
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Maintain clean server route handling and monitor 404 error logs regularly."
                })

            # 3. Broken Links (Internal & External)
            broken_links_count = sum(len(p.broken_links or []) for p in crawled_pages)
            if latest_job and (latest_job.broken_links_found or 0) > broken_links_count:
                broken_links_count = latest_job.broken_links_found
            if broken_links_count > 0:
                affected_p_urls = [p.url for p in crawled_pages if p.broken_links][:10]
                findings.append({
                    "category": "technical_seo",
                    "check_key": "broken_links",
                    "title": "Broken Hyperlinks & Dead References",
                    "status": FindingStatus.FAIL.value,
                    "severity": "warning",
                    "evidence": f"Detected {broken_links_count} broken hyperlinks across crawled pages.",
                    "rule_definition": "Tests internal and outbound hyperlinks across page HTML for dead references and 404 targets.",
                    "what_was_checked": f"Audited hyperlinks across {len(crawled_pages)} crawled pages.",
                    "observed_value": f"{broken_links_count} broken hyperlink references detected.",
                    "expected_value": "0 broken hyperlinks across all published website pages.",
                    "why_it_matters": "Broken links waste crawl budget and frustrate visitors attempting to navigate.",
                    "affected_urls": affected_p_urls,
                    "technical_evidence": {"broken_links_count": broken_links_count},
                    "remediation_steps": [
                        "Update or remove dead <a href='...'> references in page content and footer menus.",
                        "Replace outdated external partner links with updated URLs."
                    ],
                    "verification_steps": [
                        "Re-crawl website and verify broken link count is 0."
                    ],
                    "source": "Link Graph Auditor",
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Update or remove broken hyperlink href targets across navigation and body content."
                })
            else:
                findings.append({
                    "category": "technical_seo",
                    "check_key": "broken_links",
                    "title": "Broken Hyperlinks & Dead References",
                    "status": FindingStatus.PASS.value,
                    "severity": "info",
                    "evidence": f"No broken internal or external hyperlinks detected across {len(crawled_pages)} crawled pages.",
                    "rule_definition": "Tests internal and outbound hyperlinks for dead references.",
                    "what_was_checked": f"Audited link graph across {len(crawled_pages)} crawled pages.",
                    "observed_value": "No broken hyperlinks detected.",
                    "expected_value": "Zero dead link references.",
                    "why_it_matters": "Ensures seamless user journey and optimal crawl budget distribution.",
                    "affected_urls": [],
                    "technical_evidence": {"broken_links_count": 0},
                    "remediation_steps": [
                        "Maintain link checking before publishing new content."
                    ],
                    "verification_steps": [
                        "Confirm zero broken links on next scheduled crawl."
                    ],
                    "source": "Link Graph Auditor",
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Maintain clean outbound and internal links across all published pages."
                })

            # 4. Canonical Tags & Duplicate URLs
            missing_canonical = [p for p in crawled_pages if not p.canonical_url and p.is_indexable]
            if len(missing_canonical) > 0:
                findings.append({
                    "category": "technical_seo",
                    "check_key": "canonical_urls",
                    "title": "Canonical URL Consistency",
                    "status": FindingStatus.PARTIAL.value if len(missing_canonical) <= len(crawled_pages) // 2 else FindingStatus.FAIL.value,
                    "severity": "warning",
                    "evidence": f"{len(missing_canonical)} of {len(crawled_pages)} crawled indexable pages lack a canonical link tag.",
                    "rule_definition": "Checks indexable HTML pages for an explicit <link rel='canonical' href='...' /> element.",
                    "what_was_checked": f"Checked {len(crawled_pages)} indexable HTML pages for a canonical link element.",
                    "observed_value": f"{len(missing_canonical)} of {len(crawled_pages)} indexable pages do not contain a canonical URL.",
                    "expected_value": "<link rel='canonical' href='https://domain.com/page/'> present on every indexable page.",
                    "why_it_matters": "Search engines may have multiple URL candidates representing the same content, diluting ranking power.",
                    "affected_urls": [p.url for p in missing_canonical][:10],
                    "technical_evidence": {"missing_count": len(missing_canonical), "total_indexable": len(crawled_pages)},
                    "remediation_steps": [
                        "1. Add one canonical URL to each affected page <head>.",
                        "2. Use the preferred canonical HTTPS URL format.",
                        "3. Ensure canonical points to the final self or master page.",
                        "4. Do not canonicalize unrelated content."
                    ],
                    "verification_steps": [
                        "Re-run crawl and confirm all indexable pages have valid canonical URLs."
                    ],
                    "source": "HTML Meta Validator",
                    "verification_status": VerificationStatus.DETECTED.value,
                    "confidence": "HIGH",
                    "recommendation": "Embed explicit <link rel='canonical' href='...' /> tags on every public page to prevent duplicate content indexing."
                })
            else:
                findings.append({
                    "category": "technical_seo",
                    "check_key": "canonical_urls",
                    "title": "Canonical URL Consistency",
                    "status": FindingStatus.PASS.value,
                    "severity": "info",
                    "evidence": f"Canonical URL tags validated across all {len(crawled_pages)} crawled pages.",
                    "rule_definition": "Checks indexable HTML pages for an explicit canonical link tag.",
                    "what_was_checked": f"Validated canonical tags across {len(crawled_pages)} pages.",
                    "observed_value": "All crawled indexable pages contain valid canonical tags.",
                    "expected_value": "100% canonical tag coverage.",
                    "why_it_matters": "Eliminates duplicate content ambiguity for Google and Bing.",
                    "affected_urls": [],
                    "technical_evidence": {"missing_count": 0},
                    "remediation_steps": [
                        "Maintain canonical tag generation on new landing pages."
                    ],
                    "verification_steps": [
                        "Confirm canonical tags in future crawl reports."
                    ],
                    "source": "HTML Meta Validator",
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Keep canonical URLs aligned with primary domain structure."
                })

            # 5. Robots & Indexability Directives
            noindex_pages = [p for p in crawled_pages if not p.is_indexable]
            target_url_str = (f"https://{project.domain}" if project and project.domain else "").rstrip('/')
            if any(p.url.rstrip('/') == (profile.website or "").rstrip('/') or p.url.rstrip('/') == target_url_str for p in noindex_pages):
                findings.append({
                    "category": "technical_seo",
                    "check_key": "robots_indexability",
                    "title": "Homepage Indexability & Search Engine Directives",
                    "status": FindingStatus.FAIL.value,
                    "severity": "critical",
                    "evidence": "Homepage contains a 'noindex' directive or is blocked by robots.txt, preventing Google indexing.",
                    "rule_definition": "Inspects homepage meta robots directives and robots.txt disallow rules.",
                    "what_was_checked": "Evaluated homepage search engine indexability directives.",
                    "observed_value": "Homepage has noindex or crawl restriction directive.",
                    "expected_value": "Homepage is indexable with 'index, follow' directives.",
                    "why_it_matters": "A blocked homepage prevents all brand and local keywords from ranking in search results.",
                    "affected_urls": [profile.website or project.domain or ""],
                    "technical_evidence": {"homepage_blocked": True},
                    "remediation_steps": [
                        "Remove 'noindex' from homepage <meta name='robots'> tag.",
                        "Remove Disallow rules targeting the homepage in robots.txt."
                    ],
                    "verification_steps": [
                        "Re-crawl homepage and verify indexable status is True."
                    ],
                    "source": "Robots & Meta Inspector",
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Remove 'noindex' from homepage <meta name='robots'> to allow Google to index your primary domain."
                })
            else:
                findings.append({
                    "category": "technical_seo",
                    "check_key": "robots_indexability",
                    "title": "Search Engine Indexability & Directives",
                    "status": FindingStatus.PASS.value,
                    "severity": "info",
                    "evidence": f"Crawl directives allow public indexing. ({len(noindex_pages)} auxiliary pages restricted).",
                    "rule_definition": "Evaluates public search engine indexability directives.",
                    "what_was_checked": f"Audited meta robots and indexability across {len(crawled_pages)} pages.",
                    "observed_value": "Homepage and core marketing pages are indexable.",
                    "expected_value": "Core marketing pages allow public search engine indexation.",
                    "why_it_matters": "Permits search engines to crawl and rank public landing pages.",
                    "affected_urls": [],
                    "technical_evidence": {"noindex_count": len(noindex_pages)},
                    "remediation_steps": [
                        "Ensure private administrative pages remain disallow/noindex while marketing pages remain open."
                    ],
                    "verification_steps": [
                        "Review indexability status in ongoing crawls."
                    ],
                    "source": "Robots & Meta Inspector",
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "confidence": "HIGH",
                    "recommendation": "Ensure private administrative pages remain disallow/noindex while marketing pages remain open."
                })

            # 6. Page Performance & Response Time (Crawler Latency)
            measured_pages = [p for p in crawled_pages if (p.load_time_ms or 0) > 0]
            if not measured_pages:
                perf_status = FindingStatus.NOT_VERIFIED.value
                perf_evidence = f"No crawler response time measurements recorded across {len(crawled_pages)} crawled pages."
            else:
                avg_load_time = sum(p.load_time_ms for p in measured_pages) / len(measured_pages)
                slow_pages = [p for p in measured_pages if p.load_time_ms >= 2500]
                if avg_load_time < 1200:
                    perf_status = FindingStatus.PASS.value
                elif avg_load_time < 2500:
                    perf_status = FindingStatus.PARTIAL.value
                else:
                    perf_status = FindingStatus.FAIL.value
                perf_evidence = f"Crawler response time: {int(avg_load_time)}ms average across {len(measured_pages)} measured pages ({len(slow_pages)} pages > 2.5s)."

            findings.append({
                "category": "technical_seo",
                "check_key": "page_response_time",
                "title": "Server Response & Page Load Latency",
                "status": perf_status,
                "severity": "info" if perf_status == FindingStatus.PASS.value else "warning",
                "evidence": perf_evidence,
                "rule_definition": "Measures HTTP server response latency and HTML document delivery speed across crawled pages.",
                "what_was_checked": f"Evaluated response latency for {len(measured_pages)} crawled HTML pages.",
                "observed_value": perf_evidence,
                "expected_value": "Average page response latency below 1,200ms with zero server timeouts.",
                "why_it_matters": "Fast server response times improve Google crawl efficiency and visitor conversion rates.",
                "affected_urls": [p.url for p in crawled_pages if (p.load_time_ms or 0) >= 2500][:10],
                "technical_evidence": {
                    "measured_pages": len(measured_pages),
                    "average_latency_ms": int(avg_load_time) if measured_pages else None,
                    "slow_pages_count": len(slow_pages) if measured_pages else 0
                },
                "remediation_steps": [
                    "Enable server-side page caching and bytecode caching.",
                    "Optimize database query execution and reduce server middleware overhead.",
                    "Deploy CDN edge delivery for global static asset caching."
                ],
                "verification_steps": [
                    "Re-crawl website pages and verify average response latency drops below 1,200ms."
                ],
                "source": "Performance Profiler",
                "verification_status": VerificationStatus.VERIFIED.value if measured_pages else VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Enable server caching, HTTP/2 compression, and CDN edge distribution to optimize TTFB under 600ms."
            })
        elif crawler_error or has_failed_latest_job or (latest_job and (latest_job.status in (AuditJobStatus.FAILED, AuditJobStatus.CANCELLED) or ((latest_job.pages_crawled or 0) == 0 and (latest_job.pages_failed or 0) > 0))):
            err_text = crawler_error or (latest_job.error_message if latest_job else None) or (latest_job.current_stage if latest_job else None) or "Target server connection failed"
            job_id_str = f"Job #{latest_job.id}" if latest_job else "Crawl Job"
            status_val = latest_job.status.value.upper() if (latest_job and hasattr(latest_job.status, 'value')) else "FAILED"
            findings.append({
                "category": "technical_seo",
                "check_key": "crawl_health_score",
                "title": "Technical Crawl Scan Diagnostics",
                "status": FindingStatus.ERROR.value,
                "severity": "critical",
                "evidence": f"Unable to complete technical scan. Reason: {err_text}. [{job_id_str} | Status: {status_val}]",
                "rule_definition": "Monitors technical crawler execution connectivity, DNS resolution, and HTTP handshakes.",
                "what_was_checked": "Evaluated crawler execution connectivity and target website accessibility.",
                "observed_value": f"Crawler execution failed: {err_text}",
                "expected_value": "Successful crawl of domain HTML pages without network or firewall blocks.",
                "why_it_matters": "If search engine crawlers cannot connect to the server, website pages cannot be indexed.",
                "affected_urls": [profile.website or project.domain or ""],
                "technical_evidence": {"error": err_text, "job_status": status_val},
                "remediation_steps": [
                    "Verify domain DNS records resolve correctly to the active web host.",
                    "Ensure firewall or CDN (Cloudflare) is not blocking automated crawler user-agents.",
                    "Check server error logs for 5xx gateway drops or connection reset errors."
                ],
                "verification_steps": [
                    "Execute a fresh technical website crawl and confirm successful HTTP 200 responses."
                ],
                "source": "Website Crawler",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Inspect web server firewall, robots.txt restrictions, and ensure domain resolves over HTTPS."
            })
        else:
            findings.append({
                "category": "technical_seo",
                "check_key": "crawl_health_score",
                "title": "Technical Crawl Health",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "No crawled website pages have been analyzed yet for this project.",
                "rule_definition": "Evaluates overall website indexability, page health, status codes, and link architecture.",
                "what_was_checked": "Awaiting initial website crawl execution.",
                "observed_value": "No crawled pages in database",
                "expected_value": "Completed crawl of indexable domain pages.",
                "why_it_matters": "Technical crawl verifies that search engine spiders can access and index business content.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Initiate a website crawl from the Technical Audit or Central Intelligence Scan module."
                ],
                "verification_steps": [
                    "Verify crawler completes and catalogs indexable website pages."
                ],
                "source": "SEO Technical Auditor",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Execute a technical website crawl to detect broken links and HTTP errors."
            })

        # Category 16: LocalBusiness Schema
        crawled_has_localbusiness = any(
            any("localbusiness" in str(st).lower() for st in (p.schema_types or []))
            for p in crawled_pages
        )
        if schema_records:
            valid_schemas = [s for s in schema_records if s.is_valid and "LocalBusiness" in s.schema_type]
            status = FindingStatus.PASS.value if (valid_schemas or crawled_has_localbusiness) else FindingStatus.PARTIAL.value
            findings.append({
                "category": "schema_localbusiness",
                "check_key": "localbusiness_jsonld",
                "title": "Schema.org LocalBusiness Structured Data",
                "status": status,
                "severity": "info" if status == FindingStatus.PASS.value else "warning",
                "evidence": f"Found {len(valid_schemas)} valid LocalBusiness structured data instances across {len(schema_records)} validated pages." if valid_schemas else "Detected LocalBusiness structured data on crawled pages.",
                "rule_definition": "Validates Schema.org LocalBusiness JSON-LD structured markup on public landing pages.",
                "what_was_checked": f"Scanned {len(schema_records)} schema records for valid Schema.org/LocalBusiness types.",
                "observed_value": f"{len(valid_schemas)} valid LocalBusiness schema instances found.",
                "expected_value": "Valid Schema.org LocalBusiness JSON-LD markup with matching NAP details on key pages.",
                "why_it_matters": "Structured data enables rich snippet results and helps search engines verify business entity details.",
                "affected_urls": [s.page_url for s in schema_records if s.page_url][:10],
                "technical_evidence": {"valid_count": len(valid_schemas), "total_records": len(schema_records)},
                "remediation_steps": [
                    "Embed Schema.org LocalBusiness JSON-LD on homepage and contact pages.",
                    "Include @type, name, address, telephone, openingHours, and geo coordinates.",
                    "Test schema with Google Rich Results Test."
                ],
                "verification_steps": [
                    "Re-run schema intelligence extraction and confirm valid LocalBusiness markup is recognized."
                ],
                "source": "Schema Intelligence Validator",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Embed comprehensive Schema.org LocalBusiness JSON-LD with matching address, phone, and geo coordinates."
            })
        elif crawled_has_localbusiness:
            findings.append({
                "category": "schema_localbusiness",
                "check_key": "localbusiness_jsonld",
                "title": "Schema.org LocalBusiness Structured Data",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": "Detected LocalBusiness Schema structured data on crawled website pages.",
                "rule_definition": "Validates Schema.org LocalBusiness structured data markup on crawled pages.",
                "what_was_checked": "Checked crawled HTML pages for Schema.org LocalBusiness markup.",
                "observed_value": "LocalBusiness schema detected on crawled pages.",
                "expected_value": "Valid LocalBusiness schema markup present on site.",
                "why_it_matters": "Provides machine-readable business identity to search engine crawlers.",
                "affected_urls": [],
                "technical_evidence": {"crawled_detection": True},
                "remediation_steps": [
                    "Maintain Schema.org JSON-LD markup accuracy as business details change."
                ],
                "verification_steps": [
                    "Verify schema remains valid on future crawl updates."
                ],
                "source": "Website HTML Analyzer",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Maintain verified Schema.org LocalBusiness JSON-LD with matching address, phone, and geo coordinates."
            })
        else:
            findings.append({
                "category": "schema_localbusiness",
                "check_key": "localbusiness_jsonld",
                "title": "Schema.org LocalBusiness Structured Data",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "No schema records or crawled structured data validated yet for this project.",
                "rule_definition": "Validates Schema.org LocalBusiness structured markup on website pages.",
                "what_was_checked": "Checked for Schema.org LocalBusiness records in database and crawl markup.",
                "observed_value": "No schema data validated yet.",
                "expected_value": "Schema.org LocalBusiness JSON-LD markup on homepage and contact pages.",
                "why_it_matters": "Without structured data, search engines rely solely on unstructured HTML text.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Add Schema.org LocalBusiness JSON-LD to your website header or via CMS plugin."
                ],
                "verification_steps": [
                    "Validate markup in Schema Intelligence or Google Rich Results Test."
                ],
                "source": "Schema Intelligence Validator",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Validate structured data markup on homepage and contact pages."
            })

        # Category 17: Local Content
        if crawled_pages:
            substantial_pages = [p for p in crawled_pages if (p.word_count or 0) >= 200]
            status = FindingStatus.PASS.value if len(substantial_pages) > 0 else FindingStatus.PARTIAL.value
            findings.append({
                "category": "local_content",
                "check_key": "local_relevance_content",
                "title": "Geo-Targeted Service Content & Depth",
                "status": status,
                "severity": "info" if status == FindingStatus.PASS.value else "warning",
                "evidence": f"Found {len(substantial_pages)} pages with substantial editorial depth (>200 words) across {len(crawled_pages)} crawled pages.",
                "rule_definition": "Evaluates editorial depth, word count, and localized service content on crawled pages.",
                "what_was_checked": f"Audited word count and body copy depth across {len(crawled_pages)} pages.",
                "observed_value": f"{len(substantial_pages)} of {len(crawled_pages)} pages have >=200 words.",
                "expected_value": "Key service landing pages should contain >=200 words of localized, informative content.",
                "why_it_matters": "Thin content struggles to rank for competitive local search queries.",
                "affected_urls": [p.url for p in crawled_pages if (p.word_count or 0) < 200][:10],
                "technical_evidence": {"substantial_pages": len(substantial_pages), "total_pages": len(crawled_pages)},
                "remediation_steps": [
                    "Expand thin service pages with detailed descriptions, FAQs, and local project examples.",
                    "Add customer testimonials highlighting specific suburbs served."
                ],
                "verification_steps": [
                    "Re-crawl pages and confirm word count exceeds 200 words on target landing pages."
                ],
                "source": "Content Analyzer",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Include localized case studies, customer testimonials, and neighborhood references on key service pages."
            })
        else:
            findings.append({
                "category": "local_content",
                "check_key": "local_relevance_content",
                "title": "Geo-Targeted Service Content & Case Studies",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Content depth analysis requires crawled pages.",
                "rule_definition": "Evaluates editorial content depth on website pages.",
                "what_was_checked": "Awaiting crawled pages to evaluate word count.",
                "observed_value": "No crawled pages available.",
                "expected_value": "Substantial localized content on crawled pages.",
                "why_it_matters": "Content depth signals expertise, experience, authoritativeness, and trust.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Run website crawl to catalog content depth."
                ],
                "verification_steps": [
                    "Check content findings after crawl completion."
                ],
                "source": "Content Analyzer",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Include localized case studies, customer testimonials, and neighborhood references."
            })

        # Category 18: Social / Brand Signals
        has_social_citations = any(
            getattr(c, 'category', None) == "social" or
            getattr(c, 'directory_type', None) == "social" or
            any(s in (getattr(c, 'source_name', None) or getattr(c, 'domain', None) or '').lower() for s in ["facebook", "linkedin", "instagram", "twitter"])
            for c in citations
        )
        if has_social_citations:
            findings.append({
                "category": "social_brand_signals",
                "check_key": "brand_profile_links",
                "title": "Brand Social Profiles & Local Citations",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": "Verified presence across major social networks and local brand directories.",
                "rule_definition": "Validates presence of official business social media profiles and brand directory listings.",
                "what_was_checked": f"Audited {len(citations)} citation records for recognized social platforms.",
                "observed_value": "Verified social profiles detected in citations.",
                "expected_value": "Active Facebook Business, LinkedIn, and Instagram brand profiles with consistent NAP.",
                "why_it_matters": "Social brand citations provide secondary entity verification for search algorithms.",
                "affected_urls": [],
                "technical_evidence": {"has_social": True},
                "remediation_steps": [
                    "Ensure social profile business names, phone numbers, and website links match canonical profile exactly."
                ],
                "verification_steps": [
                    "Confirm social citation listings reflect matching address and phone."
                ],
                "source": "Brand Intelligence & Citations",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Maintain verified Facebook Business, LinkedIn, and Instagram brand profiles."
            })
        else:
            findings.append({
                "category": "social_brand_signals",
                "check_key": "brand_profile_links",
                "title": "Brand Social Profiles & Local Citations",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Social presence verification pending connector integration or directory citations.",
                "rule_definition": "Validates presence of official business social media profiles.",
                "what_was_checked": "Checked directory citations for verified social profiles.",
                "observed_value": "No social citations recorded.",
                "expected_value": "Active social media profiles linked in business citations.",
                "why_it_matters": "Signals brand legitimacy and social engagement to search engines.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Add your business Facebook, Instagram, LinkedIn, and YouTube profile URLs to Citations."
                ],
                "verification_steps": [
                    "Re-run Local SEO Audit to verify social profiles."
                ],
                "source": "Brand Intelligence",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Maintain verified Facebook Business, LinkedIn, and Instagram brand profiles."
            })

        # Category 19: User Engagement Signals
        if gbp and (gbp.search_impressions > 0 or gbp.call_clicks > 0 or gbp.website_clicks > 0 or gbp.direction_requests > 0):
            findings.append({
                "category": "user_engagement",
                "check_key": "interaction_signals",
                "title": "User Clicks, Calls, and Driving Directions",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": f"Recorded {gbp.search_impressions} impressions, {gbp.call_clicks} phone calls, {gbp.website_clicks} website clicks on bound Google Business Profile.",
                "rule_definition": "Monitors customer interaction signals (calls, direction requests, website clicks) from Google Business Profile.",
                "what_was_checked": "Checked Google Business Profile Performance API interaction metrics.",
                "observed_value": f"{gbp.search_impressions} impressions, {gbp.call_clicks} calls, {gbp.website_clicks} clicks.",
                "expected_value": "Consistent monthly impressions and user engagement actions on Google Maps.",
                "why_it_matters": "Active user engagement signals strong real-world relevance and boosts local map pack rankings.",
                "affected_urls": [],
                "technical_evidence": {
                    "impressions": gbp.search_impressions,
                    "calls": gbp.call_clicks,
                    "clicks": gbp.website_clicks,
                    "directions": gbp.direction_requests
                },
                "remediation_steps": [
                    "Maintain complete business listing attributes and respond to reviews to maximize engagement."
                ],
                "verification_steps": [
                    "Review weekly performance insights in GBP Performance."
                ],
                "source": "Connected Google Business Profile",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Maintain complete business listing attributes to maximize search impressions and customer actions."
            })
        elif gbp:
            findings.append({
                "category": "user_engagement",
                "check_key": "interaction_signals",
                "title": "User Clicks, Calls, and Driving Directions",
                "status": FindingStatus.PARTIAL.value,
                "severity": "info",
                "evidence": "Google Business Profile connected; performance interaction metrics awaiting initial sync/activity.",
                "rule_definition": "Monitors customer interaction signals from Google Business Profile.",
                "what_was_checked": "Checked GBP Performance metrics for customer actions.",
                "observed_value": "GBP connected, 0 recorded actions in current sync window.",
                "expected_value": "Active customer interactions recorded on Google Maps.",
                "why_it_matters": "Customer actions reflect local search intent and commercial demand.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Ensure GBP listing is fully populated with services, photos, and operating hours."
                ],
                "verification_steps": [
                    "Check GBP Performance after 7 days of customer activity."
                ],
                "source": "Connected Google Business Profile",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Monitor Search Console and GBP Performance insights weekly."
            })
        else:
            findings.append({
                "category": "user_engagement",
                "check_key": "interaction_signals",
                "title": "User Clicks, Calls, and Driving Directions",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Google Business Profile not connected. Interaction engagement signals require connected GBP.",
                "rule_definition": "Monitors customer interaction metrics on Google Maps.",
                "what_was_checked": "Checked for connected Google Business Profile.",
                "observed_value": "GBP not connected.",
                "expected_value": "Connected GBP providing real-time performance insights.",
                "why_it_matters": "Interaction signals validate local visibility and customer acquisition.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Connect your Google Business Profile in Connections Settings."
                ],
                "verification_steps": [
                    "Verify interaction data synchronizes successfully."
                ],
                "source": "Project Data",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Connect Google Business Profile to track organic calls, clicks, and driving directions."
            })

        # Category 20: Competitor / Market Analysis
        if competitors:
            findings.append({
                "category": "competitor_market_analysis",
                "check_key": "competitor_tracking_active",
                "title": "Local Market Competitor Tracking",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": f"{len(competitors)} local competitors tracked in this market.",
                "rule_definition": "Tracks benchmark competitors in the local suburban market to compare visibility and review metrics.",
                "what_was_checked": f"Audited {len(competitors)} configured competitor benchmarks.",
                "observed_value": f"{len(competitors)} competitors tracked.",
                "expected_value": "At least 3 benchmark competitors tracked for competitive gap analysis.",
                "why_it_matters": "Competitor tracking identifies market gaps, review volume targets, and ranking opportunities.",
                "affected_urls": [],
                "technical_evidence": {"competitors_count": len(competitors)},
                "remediation_steps": [
                    "Monitor competitor review acquisition pace and local map pack rank changes."
                ],
                "verification_steps": [
                    "Check Competitors View for benchmark comparison metrics."
                ],
                "source": "Competitor Intelligence Engine",
                "verification_status": VerificationStatus.USER_PROVIDED.value,
                "confidence": "HIGH",
                "recommendation": "Monitor competitor review volume, ratings, and local pack rankings weekly."
            })
        else:
            findings.append({
                "category": "competitor_market_analysis",
                "check_key": "competitor_tracking_active",
                "title": "Local Market Competitor Tracking",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "No competitors configured for comparative intelligence.",
                "rule_definition": "Tracks benchmark competitors in the local suburban market.",
                "what_was_checked": "Checked for configured competitor profiles.",
                "observed_value": "0 competitors configured.",
                "expected_value": "Top 3 local competitors configured for benchmark comparisons.",
                "why_it_matters": "Benchmarking reveals what rating and review counts are needed to dominate the local 3-pack.",
                "affected_urls": [],
                "technical_evidence": {},
                "remediation_steps": [
                    "Add top 3 local competitors in the Competitors View."
                ],
                "verification_steps": [
                    "Re-run audit to evaluate competitor benchmark scores."
                ],
                "source": "Competitor Intelligence Engine",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Add top local competitors to benchmark visibility, reviews, and authority."
            })

        # 3. Calculate Category Scores & Overall Score
        # Status score mapping: PASS = 100%, PARTIAL = 50%, FAIL = 0%, NOT_VERIFIED = Excluded from numerator & denominator
        category_scores: Dict[str, Any] = {}
        weighted_sum = 0.0
        active_weight_sum = 0.0

        findings_summary = {
            "total": len(findings),
            "pass": sum(1 for f in findings if f["status"] == FindingStatus.PASS.value),
            "partial": sum(1 for f in findings if f["status"] == FindingStatus.PARTIAL.value),
            "fail": sum(1 for f in findings if f["status"] == FindingStatus.FAIL.value),
            "not_verified": sum(1 for f in findings if f["status"] == FindingStatus.NOT_VERIFIED.value),
            "not_applicable": sum(1 for f in findings if f["status"] == FindingStatus.NOT_APPLICABLE.value),
            "error": sum(1 for f in findings if f["status"] == FindingStatus.ERROR.value)
        }

        # Group findings by category
        from collections import defaultdict
        cat_findings = defaultdict(list)
        for f in findings:
            cat_findings[f["category"]].append(f)

        for cat, w in DEFAULT_CATEGORY_WEIGHTS.items():
            cat_list = cat_findings[cat]
            eval_list = [f for f in cat_list if f["status"] in [FindingStatus.PASS.value, FindingStatus.PARTIAL.value, FindingStatus.FAIL.value]]
            if eval_list:
                score_sum = sum(100.0 if f["status"] == FindingStatus.PASS.value else 50.0 for f in eval_list if f["status"] != FindingStatus.FAIL.value)
                cat_score = round(score_sum / len(eval_list))
                category_scores[cat] = {
                    "score": cat_score,
                    "status": "evaluated",
                    "weight": w,
                    "checks_evaluated": len(eval_list),
                    "checks_total": len(cat_list)
                }
                weighted_sum += cat_score * w
                active_weight_sum += w
            else:
                category_scores[cat] = {
                    "score": None,
                    "status": "not_verified",
                    "weight": w,
                    "checks_evaluated": 0,
                    "checks_total": len(cat_list)
                }

        overall_score = round(weighted_sum / active_weight_sum) if active_weight_sum > 0 else None

        # Resolve authoritative crawl ID
        crawl_id_val = latest_job.id if latest_job else (latest_crawl_audit.id if latest_crawl_audit else None)

        # 4. Save LocalAuditRun and LocalAuditFinding records
        audit_run = LocalAuditRun(
            project_id=project_id,
            crawl_id=crawl_id_val,
            framework_version=framework_version,
            status="completed",
            overall_score=overall_score,
            category_scores=category_scores,
            findings_summary=findings_summary,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db.add(audit_run)
        await db.flush()

        for f_data in findings:
            finding = LocalAuditFinding(
                project_id=project_id,
                audit_run_id=audit_run.id,
                category=f_data["category"],
                check_key=f_data["check_key"],
                title=f_data["title"],
                status=f_data["status"],
                severity=f_data["severity"],
                score_impact=f_data.get("score_impact", 0.0),
                rule_definition=f_data.get("rule_definition"),
                what_was_checked=f_data.get("what_was_checked"),
                observed_value=f_data.get("observed_value") or (f_data.get("evidence") if isinstance(f_data.get("evidence"), str) else None),
                expected_value=f_data.get("expected_value"),
                why_it_matters=f_data.get("why_it_matters"),
                affected_urls=f_data.get("affected_urls", []),
                technical_evidence=f_data.get("technical_evidence", {}),
                remediation_steps=f_data.get("remediation_steps", []),
                verification_steps=f_data.get("verification_steps", []),
                crawl_id=f_data.get("crawl_id") or crawl_id_val,
                source_timestamp=f_data.get("source_timestamp") or started_at,
                evidence=f_data.get("evidence"),
                source=f_data.get("source"),
                source_url=f_data.get("source_url"),
                verification_status=f_data.get("verification_status", VerificationStatus.NOT_VERIFIED.value),
                confidence=f_data.get("confidence", "HIGH"),
                recommendation=f_data.get("recommendation"),
                action_type=f_data.get("action_type", "manual_action"),
                created_at=datetime.now(timezone.utc)
            )
            db.add(finding)

        await db.commit()
        
        # Reload with eager loaded findings
        stmt = (
            select(LocalAuditRun)
            .options(selectinload(LocalAuditRun.findings))
            .where(LocalAuditRun.id == audit_run.id)
        )
        res = await db.execute(stmt)
        loaded_run = res.scalars().first()
        logger.info(f"Completed Local SEO Audit run {audit_run.id} for project {project_id} with score {overall_score}")
        return loaded_run or audit_run

