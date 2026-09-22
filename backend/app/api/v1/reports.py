from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.core.audit_logger import log_user_action
from app.models.user import User
from app.models.project import Project
from app.models.audit import SEOAudit, SEOIssue, SEOTask, LocalAuditRun, LocalAuditFinding
from app.models.ranking import Keyword, GeoGridScan
from app.models.local_seo import Review, Citation, NAPRecord, Competitor
from app.services.local_seo.business_profile_service import BusinessProfileService
from app.services.local_seo.audit_framework import AUDIT_FRAMEWORK_CATEGORIES

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/{project_id}/executive")
async def generate_executive_report(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "GENERATE_REPORT",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        report_type="executive"
    )

    # Fetch stats
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.project_id == project_id))
    issues = iss_res.scalars().all()

    tasks_res = await db.execute(select(SEOTask).where(SEOTask.project_id == project_id))
    tasks = tasks_res.scalars().all()

    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
    keywords = kw_res.scalars().all()

    rev_res = await db.execute(select(Review).where(Review.project_id == project_id))
    reviews = rev_res.scalars().all()

    nap_res = await db.execute(select(NAPRecord).where(NAPRecord.project_id == project_id))
    nap = nap_res.scalars().first()

    total_kw = len(keywords)
    top_3 = len([k for k in keywords if k.current_rank and k.current_rank <= 3])
    top_10 = len([k for k in keywords if k.current_rank and k.current_rank <= 10])
    completed_tasks = len([t for t in tasks if t.status == 'completed'])
    open_issues = len([i for i in issues if i.status == 'open'])
    total_revs = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_revs, 1) if total_revs > 0 else None

    # Construct truthful executive summary
    summary_parts = []
    if project.health_score is not None:
        summary_parts.append(f"{project.name} has an overall Local SEO Health Score of {project.health_score}/100.")
    else:
        summary_parts.append(f"{project.name} Local SEO Health Score is awaiting initial audit.")

    if total_kw == 0:
        summary_parts.append("No local search keywords are currently configured or tracked.")
    elif top_3 > 0:
        summary_parts.append(f"The business currently tracks {total_kw} local search terms with {top_3} ranking in the Top 3 Local Pack.")
    elif top_10 > 0:
        summary_parts.append(f"The business currently tracks {total_kw} local search terms with {top_10} ranking in the Top 10.")
    else:
        summary_parts.append(f"The business currently tracks {total_kw} local search terms awaiting first rank scan or visibility improvements.")

    if completed_tasks > 0:
        summary_parts.append(f"During the last 30 days, {completed_tasks} technical and on-page optimization tasks were completed.")
    else:
        summary_parts.append("No optimization tasks have been completed in the last 30 days.")

    executive_summary = " ".join(summary_parts)

    # Dynamic data-driven recommendations
    recommendations: List[str] = []
    if project.health_score is None:
        recommendations.append("Execute an initial website technical and on-page audit to identify baseline crawl issues.")
    elif open_issues > 0:
        recommendations.append(f"Resolve {open_issues} open technical and on-page SEO issues to improve site crawlability.")

    if total_kw == 0:
        recommendations.append("Add high-intent local target keywords to begin monitoring local map pack rankings.")
    elif top_3 == 0 and total_kw > 0:
        recommendations.append("Optimize localized landing pages and GBP categories to push tracked keywords into the Top 3 Local Pack.")
    else:
        recommendations.append("Continue proactive review generation campaign to maintain Top 3 Local Pack density.")

    if total_revs == 0:
        recommendations.append("Launch a customer review acquisition campaign to build initial local social proof and star ratings.")
    elif avg_rating is not None and avg_rating < 4.5:
        recommendations.append("Improve customer sentiment and actively respond to feedback to raise the average review rating.")

    if nap is None or nap.nap_score is None or nap.nap_score < 85:
        recommendations.append("Audit and standardize NAP (Name, Address, Phone) consistency across major directory citations.")

    if len(recommendations) < 3:
        recommendations.append("Deploy localized Schema markup across key service pages to enhance search engine rich snippets.")
    if len(recommendations) < 4:
        recommendations.append("Publish regular Google Business Profile updates and localized service posts to boost engagement.")

    seen_recs = set()
    final_recommendations = []
    for r in recommendations:
        if r not in seen_recs:
            seen_recs.add(r)
            final_recommendations.append(r)
        if len(final_recommendations) == 4:
            break

    return {
        "title": f"Local SEO Executive Performance Report — {project.name}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "name": project.name,
            "domain": project.domain,
            "primary_category": project.primary_category,
            "health_score": project.health_score,
            "sub_scores": {
                "technical": project.technical_score,
                "onpage": project.onpage_score,
                "local": project.local_score,
                "gbp": project.gbp_score,
                "reviews": project.reviews_score,
                "citations": project.citations_score,
                "keywords": project.keywords_score,
                "maps": project.maps_score,
            }
        },
        "executive_summary": executive_summary,
        "metrics": {
            "total_keywords": total_kw,
            "top_3_keywords": top_3,
            "top_10_keywords": top_10,
            "total_reviews": total_revs,
            "avg_rating": avg_rating,
            "nap_consistency_score": nap.nap_score if (nap and nap.nap_score is not None) else project.citations_score,
            "open_issues_count": open_issues,
            "completed_tasks_count": completed_tasks
        },
        "next_month_recommendations": final_recommendations
    }

from fastapi import Response
from app.api.v1.audits import get_canonical_audit
from app.services.reports.pdf_service import AuditPDFService
from app.services.reports.xlsx_service import MasterXLSXService

@router.get("/{project_id}/pdf")
async def download_audit_pdf(
    project_id: int,
    crawl_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    canonical_data = await get_canonical_audit(project_id=project_id, crawl_id=crawl_id, current_user=current_user, db=db)
    pdf_bytes = AuditPDFService.generate_pdf(canonical_data)
    domain = canonical_data.get("domain", "audit").replace("https://", "").replace("http://", "").replace("/", "")
    filename = f"SEO_Audit_Report_{domain}_{canonical_data.get('crawl_id') or 'latest'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{project_id}/xlsx")
async def download_audit_xlsx(
    project_id: int,
    crawl_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    canonical_data = await get_canonical_audit(project_id=project_id, crawl_id=crawl_id, current_user=current_user, db=db)
    xlsx_bytes = MasterXLSXService.generate_xlsx(canonical_data)
    domain = canonical_data.get("domain", "audit").replace("https://", "").replace("http://", "").replace("/", "")
    filename = f"Master_SEO_Audit_{domain}_{canonical_data.get('crawl_id') or 'latest'}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/{project_id}/local-seo")
async def generate_local_seo_report(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a full structured Local SEO Intelligence & Audit Report.
    Truthful evidence-based data aggregated across canonical profile, audit framework, geo-grid, reviews, citations, and competitors.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "GENERATE_LOCAL_SEO_REPORT",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        report_type="local_seo_intelligence"
    )

    # 1. Canonical Profile
    profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)

    # 2. Latest Local Audit Run
    audit_res = await db.execute(
        select(LocalAuditRun)
        .options(selectinload(LocalAuditRun.findings))
        .where(LocalAuditRun.project_id == project_id)
        .order_by(LocalAuditRun.id.desc())
        .limit(1)
    )
    audit_run = audit_res.scalars().first()

    # 3. Latest GeoGrid Scan
    geo_res = await db.execute(
        select(GeoGridScan)
        .options(selectinload(GeoGridScan.keyword_rel), selectinload(GeoGridScan.point_results))
        .where(GeoGridScan.project_id == project_id)
        .order_by(GeoGridScan.id.desc())
        .limit(1)
    )
    latest_geo = geo_res.scalars().first()

    # 4. Keywords
    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
    keywords = kw_res.scalars().all()

    # 5. Reviews
    rev_res = await db.execute(select(Review).where(Review.project_id == project_id))
    reviews = rev_res.scalars().all()

    # 6. Citations
    cit_res = await db.execute(select(Citation).where(Citation.project_id == project_id))
    citations = cit_res.scalars().all()

    # 7. Competitors
    comp_res = await db.execute(select(Competitor).where(Competitor.project_id == project_id))
    competitors = comp_res.scalars().all()

    # Calculate summaries
    total_revs = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_revs, 1) if total_revs > 0 else None
    matching_cits = len([c for c in citations if c.nap_status == "match"])

    # Findings breakdown
    findings = audit_run.findings if audit_run else []
    critical_findings = [f for f in findings if f.severity == "CRITICAL" and f.status != "PASS"]
    warning_findings = [f for f in findings if f.severity == "WARNING" and f.status != "PASS"]
    passed_findings = [f for f in findings if f.status == "PASS"]

    # Top priority findings
    priority_findings = []
    for f in (critical_findings + warning_findings)[:10]:
        priority_findings.append({
            "id": f.id,
            "category_key": f.category_key,
            "category_name": AUDIT_FRAMEWORK_CATEGORIES.get(f.category_key, {}).get("name", f.category_key),
            "title": f.title,
            "severity": f.severity,
            "status": f.status,
            "evidence": f.evidence,
            "recommended_action": f.recommended_action,
            "source": f.source,
            "source_url": f.source_url,
            "verification_status": f.verification_status
        })

    # Executive narrative
    summary_parts = []
    if audit_run and audit_run.overall_score is not None:
        summary_parts.append(f"{profile.business_name} currently has an overall Local SEO Health Score of {audit_run.overall_score}/100 based on {len(findings)} audited checkpoints.")
    else:
        summary_parts.append(f"{profile.business_name} Local SEO health baseline is awaiting execution of a full local audit.")

    if latest_geo and latest_geo.local_visibility_pct is not None:
        summary_parts.append(f"Geographic visibility across the 5x5 localized territory is {latest_geo.local_visibility_pct}% for target keyword '{latest_geo.keyword_rel.keyword if latest_geo.keyword_rel else 'local search'}'.")
    else:
        summary_parts.append("No active 5x5 Geo-Grid scans have been recorded for this territory.")

    if len(keywords) > 0:
        top_3 = len([k for k in keywords if k.current_rank and k.current_rank <= 3])
        summary_parts.append(f"Tracking {len(keywords)} local search keywords with {top_3} ranking in the Top 3.")

    if total_revs > 0 and avg_rating is not None:
        summary_parts.append(f"Reputation profile displays {total_revs} recorded customer reviews with an average rating of {avg_rating} / 5.0.")

    if len(citations) > 0:
        summary_parts.append(f"Documented {len(citations)} external directory citations with {matching_cits} matching canonical NAP.")

    executive_summary = " ".join(summary_parts)

    # 90-Day Action Roadmap
    action_plan = {
        "month_1": {
            "focus": "Foundation, Canonical NAP Standardization & Critical Fixes",
            "actions": [f.recommended_action for f in critical_findings[:4]] or [
                "Establish canonical business profile and synchronize address/phone across primary platforms.",
                "Execute local website crawler and resolve any crawl errors or broken meta tags.",
                "Standardize NAP on Google Business Profile and major citation directories."
            ]
        },
        "month_2": {
            "focus": "On-Page Localization, Schema & Category Optimization",
            "actions": [f.recommended_action for f in warning_findings[:4]] or [
                "Implement structured LocalBusiness JSON-LD schema with complete geo-coordinates.",
                "Enhance localized landing page content with neighborhood signals and service area coverage.",
                "Review primary and secondary GBP category classifications against ranking competitors."
            ]
        },
        "month_3": {
            "focus": "Authority Building, Review Velocity & Geo-Grid Expansion",
            "actions": [
                "Deploy proactive customer review acquisition workflow to increase monthly review volume.",
                "Acquire citations on prominent industry and regional business directories.",
                "Run periodic 5x5 Geo-Grid scans to verify local ranking improvements across service borders."
            ]
        }
    }

    return {
        "title": f"Local SEO Intelligence & Audit Report — {profile.business_name}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project.id,
        "business_profile": {
            "business_name": profile.business_name,
            "website": profile.website or project.domain,
            "primary_phone": profile.primary_phone,
            "primary_address": profile.primary_address,
            "city": profile.city,
            "state": profile.state,
            "postal_code": profile.postal_code,
            "country": profile.country,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
            "primary_category": profile.primary_category,
            "additional_categories": profile.additional_categories or [],
            "service_area": profile.service_area or [],
            "verification_status": profile.verification_status,
            "place_id": profile.place_id,
            "maps_url": profile.maps_url
        },
        "executive_summary": executive_summary,
        "audit": {
            "overall_score": audit_run.overall_score if audit_run else None,
            "audit_id": audit_run.id if audit_run else None,
            "completed_at": audit_run.completed_at if audit_run else None,
            "category_scores": audit_run.category_scores if audit_run else {},
            "total_findings": len(findings),
            "critical_count": len(critical_findings),
            "warning_count": len(warning_findings),
            "passed_count": len(passed_findings)
        },
        "geo_visibility": {
            "latest_scan_id": latest_geo.id if latest_geo else None,
            "keyword": latest_geo.keyword_rel.keyword if (latest_geo and latest_geo.keyword_rel) else None,
            "local_visibility_pct": latest_geo.local_visibility_pct if latest_geo else None,
            "average_rank": latest_geo.average_rank if latest_geo else None,
            "total_points": latest_geo.total_points if latest_geo else None,
            "ranking_found_points": latest_geo.ranking_found_points if latest_geo else None,
            "not_found_points": latest_geo.not_found_points if latest_geo else None,
            "scanned_at": latest_geo.scanned_at if latest_geo else None
        },
        "keywords": [
            {
                "id": k.id,
                "keyword": k.keyword,
                "target_location": k.target_location,
                "current_rank": k.current_rank,
                "previous_rank": k.previous_rank,
                "serp_type": k.serp_type,
                "last_checked_at": k.last_checked_at
            }
            for k in keywords
        ],
        "reputation": {
            "total_reviews": total_revs,
            "average_rating": avg_rating,
            "unanswered_count": len([r for r in reviews if not r.response_text]) if total_revs > 0 else 0
        },
        "citations": {
            "total": len(citations),
            "matching_nap_count": matching_cits,
            "listings": [
                {
                    "id": c.id,
                    "directory_name": getattr(c, "source_name", getattr(c, "domain", "Directory")),
                    "listing_url": c.listing_url,
                    "nap_status": c.nap_status,
                    "verification_status": c.verification_status,
                    "domain_authority": c.domain_authority
                }
                for c in citations
            ]
        },
        "competitors": [
            {
                "id": comp.id,
                "name": comp.name,
                "domain": comp.domain,
                "visibility_score": getattr(comp, "local_visibility_score", None),
                "review_count": getattr(comp, "reviews_count", 0),
                "rating": comp.rating
            }
            for comp in competitors
        ],
        "priority_findings": priority_findings,
        "action_plan": action_plan,
        "provenance_legend": {
            "VERIFIED": "Direct live API verification from Google Business Profile or authenticated services.",
            "OBSERVED": "Directly crawled and parsed from live web URLs, HTML markup, or verified directory listings.",
            "USER_PROVIDED": "Information submitted manually by the user or client profile.",
            "DETECTED": "Algorithmic inference or pattern detection from page contents or search results.",
            "NOT_VERIFIED": "Third-party or external entity status cannot be confirmed without active API keys or credentials."
        }
    }

