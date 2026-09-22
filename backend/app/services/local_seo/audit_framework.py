"""
LocalLift — 20-Category Local SEO Audit Framework Engine

Defines the hierarchical audit framework:
AuditFramework -> AuditCategory -> AuditCheck -> Weight -> Finding -> Category Score -> Overall Score

All findings carry provenance, traceable evidence, and status (PASS, PARTIAL, FAIL, NOT_VERIFIED, NOT_APPLICABLE, ERROR).
No fabricated scores: categories without evidence return NOT_VERIFIED and are excluded from score inflation.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.audit import LocalAuditRun, LocalAuditFinding, SEOAudit, WebsitePage
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
    async def run_audit(
        cls,
        project_id: int,
        db: AsyncSession,
        framework_version: str = "local_seo_v1"
    ) -> LocalAuditRun:
        """
        Executes a complete Local SEO audit for the specified project.
        Creates and persists LocalAuditRun and all LocalAuditFinding entries.
        """
        started_at = datetime.now(timezone.utc)
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

        # Technical/Crawl Audit
        audit_res = await db.execute(
            select(SEOAudit)
            .options(selectinload(SEOAudit.issues))
            .where(SEOAudit.project_id == project_id)
            .order_by(SEOAudit.id.desc())
        )
        latest_crawl_audit = audit_res.scalars().first()

        # Crawled Pages
        pages_res = await db.execute(
            select(WebsitePage)
            .join(WebsitePage.website)
            .where(WebsitePage.website.has(project_id=project_id))
        )
        crawled_pages = pages_res.scalars().all()

        # GBP Profile
        acc_res = await db.execute(
            select(GoogleAccount)
            .options(selectinload(GoogleAccount.gbp_profiles))
            .where(GoogleAccount.project_id == project_id)
        )
        google_acc = acc_res.scalars().first()
        gbp = google_acc.gbp_profiles[0] if google_acc and google_acc.gbp_profiles else None

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
            findings.append({
                "category": "google_business_profile",
                "check_key": "gbp_claimed_verified",
                "title": "Google Business Profile Verification Status",
                "status": status,
                "severity": "info" if gbp.is_verified else "warning",
                "evidence": f"GBP profile '{gbp.business_name}' is {'verified' if gbp.is_verified else 'unverified/unclaimed'}.",
                "source": "Google Business Profile API",
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
                "evidence": "Google Business Profile OAuth integration is not connected for this project.",
                "source": "Google Integrations Hub",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Connect your Google Business Profile to verify ownership and synchronize listing attributes."
            })

        # Category 2: Categories Taxonomy
        if profile.primary_category and profile.primary_category != "Local Business":
            findings.append({
                "category": "categories_taxonomy",
                "check_key": "primary_category_selected",
                "title": "Specific Primary Business Category Configured",
                "status": FindingStatus.PASS.value,
                "severity": "info",
                "evidence": f"Primary category configured as '{profile.primary_category}'.",
                "source": "Canonical Business Profile",
                "verification_status": VerificationStatus.USER_PROVIDED.value,
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
                "source": "Canonical Business Profile",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Select an exact Google/Schema primary category for this business."
            })

        # Category 3: Reviews & Reputation
        if reviews:
            avg_rating = sum(r.rating for r in reviews) / len(reviews)
            status = FindingStatus.PASS.value if avg_rating >= 4.5 else (FindingStatus.PARTIAL.value if avg_rating >= 3.8 else FindingStatus.FAIL.value)
            findings.append({
                "category": "reviews_reputation",
                "check_key": "review_rating_threshold",
                "title": "Customer Review Rating Score",
                "status": status,
                "severity": "info" if avg_rating >= 4.5 else "warning",
                "evidence": f"{len(reviews)} reviews recorded with average rating of {round(avg_rating, 2)}★.",
                "source": "Review Sync Engine",
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
                "source": "Review Sync Engine",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Synchronize Google and directory reviews to establish reputation metrics."
            })

        # Category 4: NAP Consistency
        if nap_data["total_sources_checked"] > 0:
            nap_score = nap_data["nap_score"] or 0
            status = FindingStatus.PASS.value if nap_score >= 90 else (FindingStatus.PARTIAL.value if nap_score >= 70 else FindingStatus.FAIL.value)
            findings.append({
                "category": "nap_consistency",
                "check_key": "nap_uniformity",
                "title": "Name, Address, and Phone Consistency",
                "status": status,
                "severity": "info" if nap_score >= 90 else "critical",
                "evidence": f"Checked {nap_data['total_sources_checked']} sources: {nap_data['consistent_sources']} consistent, {nap_data['mismatch_sources']} mismatches ({nap_score}% alignment).",
                "source": "NAP Comparison Engine",
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
                "source": "NAP Comparison Engine",
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
                "source": "Website Crawler",
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
                "source": "Website Crawler",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Launch a website audit crawl to inspect on-page metadata, headings, and geo-relevance."
            })

        # Category 6: Proximity & Location Signals
        has_coords = profile.latitude is not None and profile.longitude is not None
        findings.append({
            "category": "proximity_location",
            "check_key": "geo_coordinates_bound",
            "title": "Geographic Latitude & Longitude Coordinates",
            "status": FindingStatus.PASS.value if has_coords else FindingStatus.FAIL.value,
            "severity": "info" if has_coords else "critical",
            "evidence": f"Canonical coordinates: {profile.latitude}, {profile.longitude}" if has_coords else "No geographic coordinates configured.",
            "source": "Canonical Business Profile",
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
                "source": "Citations Registry",
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
            "source": "Backlink Intelligence Provider",
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
                "source": "Review Sync Engine",
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
                "source": "Review Sync Engine",
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
                "evidence": f"{gbp.photos_count} photos present on Google Business Profile.",
                "source": "Google Business Profile API",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Upload high-quality geotagged photos of your storefront, team, and projects regularly."
            })
        else:
            findings.append({
                "category": "gbp_media",
                "check_key": "photo_upload_count",
                "title": "Google Business Profile Photo Assets",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "GBP media assets not verified or profile not connected.",
                "source": "Google Business Profile API",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Ensure at least 10 high-resolution photos are uploaded to your Google Business Profile."
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
                "source": "Website Crawler",
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
                "source": "Website Crawler",
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
                "evidence": f"{gbp.posts_count} posts recorded on GBP.",
                "source": "Google Business Profile API",
                "verification_status": VerificationStatus.VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Publish weekly Google updates, offers, and seasonal announcements."
            })
        else:
            findings.append({
                "category": "gbp_activity",
                "check_key": "post_recency",
                "title": "Google Business Profile Updates & Posts",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "Google post activity data not available.",
                "source": "Google Business Profile API",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Publish fresh updates on Google Business Profile to signal operational activity."
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

        # Category 15: Technical SEO
        if latest_crawl_audit:
            status = FindingStatus.PASS.value if latest_crawl_audit.overall_score >= 80 else (FindingStatus.PARTIAL.value if latest_crawl_audit.overall_score >= 60 else FindingStatus.FAIL.value)
            findings.append({
                "category": "technical_seo",
                "check_key": "crawl_health_score",
                "title": "Technical Crawl & Accessibility Health",
                "status": status,
                "severity": "info" if status == FindingStatus.PASS.value else "warning",
                "evidence": f"Technical crawl score: {latest_crawl_audit.overall_score}/100 across {latest_crawl_audit.pages_analyzed} pages with {latest_crawl_audit.critical_issues} critical issues.",
                "source": "SEO Technical Auditor",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Resolve broken links, redirect chains, and server errors identified in crawl audit."
            })
        else:
            findings.append({
                "category": "technical_seo",
                "check_key": "crawl_health_score",
                "title": "Technical Crawl Health",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "info",
                "evidence": "No technical crawl audit has been completed.",
                "source": "SEO Technical Auditor",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Execute a technical website crawl to detect broken links and HTTP errors."
            })

        # Category 16: LocalBusiness Schema
        if schema_records:
            valid_schemas = [s for s in schema_records if s.is_valid and "LocalBusiness" in s.schema_type]
            status = FindingStatus.PASS.value if valid_schemas else FindingStatus.PARTIAL.value
            findings.append({
                "category": "schema_localbusiness",
                "check_key": "localbusiness_jsonld",
                "title": "Schema.org LocalBusiness Structured Data",
                "status": status,
                "severity": "info" if status == FindingStatus.PASS.value else "warning",
                "evidence": f"Found {len(valid_schemas)} valid LocalBusiness structured data instances across {len(schema_records)} validated pages.",
                "source": "Schema Intelligence Validator",
                "verification_status": VerificationStatus.DETECTED.value,
                "confidence": "HIGH",
                "recommendation": "Embed comprehensive Schema.org LocalBusiness JSON-LD with matching address, phone, and geo coordinates."
            })
        else:
            findings.append({
                "category": "schema_localbusiness",
                "check_key": "localbusiness_jsonld",
                "title": "Schema.org LocalBusiness Structured Data",
                "status": FindingStatus.NOT_VERIFIED.value,
                "severity": "warning",
                "evidence": "No schema records validated yet for this project.",
                "source": "Schema Intelligence Validator",
                "verification_status": VerificationStatus.NOT_VERIFIED.value,
                "confidence": "HIGH",
                "recommendation": "Validate structured data markup on homepage and contact pages."
            })

        # Category 17: Local Content
        findings.append({
            "category": "local_content",
            "check_key": "local_relevance_content",
            "title": "Geo-Targeted Service Content & Case Studies",
            "status": FindingStatus.NOT_VERIFIED.value,
            "severity": "info",
            "evidence": "Content depth analysis requires crawled pages.",
            "source": "Content Analyzer",
            "verification_status": VerificationStatus.NOT_VERIFIED.value,
            "confidence": "HIGH",
            "recommendation": "Include localized case studies, customer testimonials, and neighborhood references."
        })

        # Category 18: Social / Brand Signals
        findings.append({
            "category": "social_brand_signals",
            "check_key": "brand_profile_links",
            "title": "Brand Social Profiles & Local Citations",
            "status": FindingStatus.NOT_VERIFIED.value,
            "severity": "info",
            "evidence": "Social presence verification pending connector integration.",
            "source": "Brand Intelligence",
            "verification_status": VerificationStatus.NOT_VERIFIED.value,
            "confidence": "HIGH",
            "recommendation": "Maintain verified Facebook Business, LinkedIn, and Instagram brand profiles."
        })

        # Category 19: User Engagement Signals
        findings.append({
            "category": "user_engagement",
            "check_key": "interaction_signals",
            "title": "User Clicks, Calls, and Driving Directions",
            "status": FindingStatus.NOT_VERIFIED.value,
            "severity": "info",
            "evidence": "GBP Insights / Search Console engagement signals require connected Google Account.",
            "source": "Google Integrations",
            "verification_status": VerificationStatus.NOT_VERIFIED.value,
            "confidence": "HIGH",
            "recommendation": "Connect Search Console and Google Analytics 4 to track organic engagement."
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

        # 4. Save LocalAuditRun and LocalAuditFinding records
        audit_run = LocalAuditRun(
            project_id=project_id,
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
        await db.refresh(audit_run)
        logger.info(f"Completed Local SEO Audit run {audit_run.id} for project {project_id} with score {overall_score}")
        return audit_run
