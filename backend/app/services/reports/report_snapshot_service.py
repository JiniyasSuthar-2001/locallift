"""
LocalLift — Report Snapshot & Run Resolution Engine

Implements deterministic, run-aware report resolution across Central Intelligence Scans and Standalone Module runs.
Run Precedence Rule:
  "The newest valid completed run for that specific module wins."

Produces a single authoritative resolved report dataset for:
  - Intelligence-Audit view
  - Executive Summary view
  - White-label PDF export
  - Master XLSX export
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.project import Project, Website
from app.models.intelligence_scan import ProjectIntelligenceScan, ScanStatus, StageStatus
from app.models.audit import (
    LocalAuditRun,
    LocalAuditFinding,
    SEOAudit,
    SEOIssue,
    WebsitePage,
    AuditJob
)
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan, GeoGridPointResult
from app.models.local_seo import (
    BusinessProfile,
    Review,
    Citation,
    NAPRecord,
    Competitor,
    SchemaRecord
)
from app.services.local_seo.business_profile_service import BusinessProfileService
from app.services.local_seo.audit_framework import AUDIT_FRAMEWORK_CATEGORIES
from app.services.local_seo.nap_service import NAPComparisonService
from app.services.local_seo.content_opportunity_service import ContentOpportunityEngine

logger = logging.getLogger("locallift.report_snapshot_service")


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


class ReportSnapshotService:
    @classmethod
    async def resolve_report_snapshot(
        cls,
        project_id: int,
        db: AsyncSession,
        specific_central_scan_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resolves the authoritative report dataset for a project by evaluating Central Intelligence Scans
        and standalone module runs with precise execution timestamps and provenance metadata.
        """
        # 1. Fetch Project
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            raise ValueError(f"Project with ID {project_id} not found.")

        # 2. Fetch Latest Valid Central Intelligence Scan
        central_scan_stmt = (
            select(ProjectIntelligenceScan)
            .where(
                ProjectIntelligenceScan.project_id == project_id,
                ProjectIntelligenceScan.status.in_([ScanStatus.COMPLETED.value, ScanStatus.PARTIAL.value])
            )
        )
        if specific_central_scan_id:
            central_scan_stmt = central_scan_stmt.where(ProjectIntelligenceScan.id == specific_central_scan_id)
        else:
            central_scan_stmt = central_scan_stmt.order_by(ProjectIntelligenceScan.id.desc())

        central_res = await db.execute(central_scan_stmt)
        central_scan: Optional[ProjectIntelligenceScan] = central_res.scalars().first()

        central_stages = central_scan.stages or {} if central_scan else {}
        central_results = central_scan.results_summary or {} if central_scan else {}
        central_completed_at = _parse_dt(central_scan.completed_at or central_scan.started_at) if central_scan else None

        provenance: Dict[str, Dict[str, Any]] = {}

        # =====================================================================
        # MODULE 1: Canonical Business Profile
        # =====================================================================
        profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)
        bp_source_type = "canonical_profile"
        bp_executed_at = _parse_dt(profile.updated_at or profile.created_at) or datetime.now(timezone.utc)
        
        # Check Central Scan stage
        stage_bp = central_stages.get("business_profile")
        if stage_bp and stage_bp.get("status") in (StageStatus.SUCCESS.value, StageStatus.PARTIAL.value):
            st_dt = _parse_dt(stage_bp.get("completed_at")) or central_completed_at
            if central_completed_at and (not bp_executed_at or central_completed_at >= bp_executed_at):
                bp_source_type = "central_scan"
                bp_executed_at = st_dt or central_completed_at

        provenance["business_profile"] = {
            "source_type": bp_source_type,
            "source_run_id": central_scan.id if bp_source_type == "central_scan" else profile.id,
            "source_module": "business_profile",
            "executed_at": bp_executed_at.isoformat() if bp_executed_at else datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED",
            "is_override": False
        }

        resolved_bp = {
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
            "primary_category": profile.primary_category or project.primary_category,
            "additional_categories": profile.additional_categories or [],
            "service_area": profile.service_area or [],
            "verification_status": profile.verification_status,
            "place_id": profile.place_id,
            "maps_url": profile.maps_url,
            "source": profile.source,
            "last_verified_at": profile.last_verified_at.isoformat() if profile.last_verified_at else None
        }

        # =====================================================================
        # MODULE 2: Local SEO 20-Category Audit Run & Complete Findings
        # =====================================================================
        # Query latest standalone valid local audit run
        audit_res = await db.execute(
            select(LocalAuditRun)
            .options(selectinload(LocalAuditRun.findings))
            .where(
                LocalAuditRun.project_id == project_id,
                LocalAuditRun.status.in_(["completed", "completed_with_warnings", "completed_with_errors", "COMPLETED", "PARTIAL"])
            )
            .order_by(LocalAuditRun.id.desc())
        )
        all_audit_runs = audit_res.scalars().all()
        standalone_audit_run = all_audit_runs[0] if all_audit_runs else None

        # Check Central Scan local_audit stage
        stage_la = central_stages.get("local_audit")
        t_central_la = _parse_dt(stage_la.get("completed_at")) if stage_la else central_completed_at
        t_standalone_la = _parse_dt(standalone_audit_run.completed_at or standalone_audit_run.started_at) if standalone_audit_run else None

        chosen_audit_run: Optional[LocalAuditRun] = None
        la_source_type = "standalone_local_audit"
        la_is_override = False

        if standalone_audit_run and (not t_central_la or (t_standalone_la and t_standalone_la > t_central_la)):
            chosen_audit_run = standalone_audit_run
            la_source_type = "standalone_local_audit"
            la_is_override = True if t_central_la else False
            la_executed_at = t_standalone_la or datetime.now(timezone.utc)
            la_status = standalone_audit_run.status.upper()
            la_run_id = standalone_audit_run.id
        elif central_scan and stage_la:
            # Central scan stage is newer or only run available
            # If central scan saved a specific audit_run_id, find that exact run
            central_la_run_id = (central_results.get("local_audit") or {}).get("audit_run_id")
            if central_la_run_id:
                for ar in all_audit_runs:
                    if ar.id == central_la_run_id:
                        chosen_audit_run = ar
                        break
            if not chosen_audit_run:
                chosen_audit_run = standalone_audit_run

            la_source_type = "central_scan"
            la_is_override = False
            la_executed_at = t_central_la or central_completed_at or datetime.now(timezone.utc)
            la_status = stage_la.get("status", "COMPLETED")
            la_run_id = central_scan.id
        else:
            chosen_audit_run = standalone_audit_run
            la_source_type = "standalone_local_audit"
            la_is_override = False
            la_executed_at = t_standalone_la or datetime.now(timezone.utc)
            la_status = chosen_audit_run.status.upper() if chosen_audit_run else "NOT_CONFIGURED"
            la_run_id = chosen_audit_run.id if chosen_audit_run else None

        provenance["local_audit"] = {
            "source_type": la_source_type,
            "source_run_id": la_run_id,
            "source_module": "local_audit",
            "executed_at": la_executed_at.isoformat() if la_executed_at else None,
            "status": la_status,
            "is_override": la_is_override
        }

        # Build full audit findings dataset (all findings, not sliced)
        raw_findings = chosen_audit_run.findings if chosen_audit_run else []
        resolved_findings: List[Dict[str, Any]] = []
        critical_findings: List[Dict[str, Any]] = []
        warning_findings: List[Dict[str, Any]] = []
        passed_findings: List[Dict[str, Any]] = []

        for f in raw_findings:
            cat_info = AUDIT_FRAMEWORK_CATEGORIES.get(f.category, {})
            cat_name = cat_info.get("name", f.category.replace("_", " ").title())
            finding_dict = {
                "id": f.id,
                "audit_run_id": f.audit_run_id,
                "category_key": f.category,
                "category_name": cat_name,
                "check_key": f.check_key,
                "title": f.title,
                "status": f.status,
                "severity": f.severity.upper() if f.severity else "INFO",
                "score_impact": f.score_impact,
                "evidence": f.evidence,
                "recommended_action": f.recommendation,
                "recommendation": f.recommendation,
                "source": f.source,
                "source_url": f.source_url,
                "verification_status": f.verification_status,
                "confidence": f.confidence,
                "action_type": f.action_type,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            resolved_findings.append(finding_dict)
            if f.severity and f.severity.upper() == "CRITICAL" and f.status != "PASS":
                critical_findings.append(finding_dict)
            elif f.severity and f.severity.upper() == "WARNING" and f.status != "PASS":
                warning_findings.append(finding_dict)
            elif f.status == "PASS":
                passed_findings.append(finding_dict)

        # Build category score breakdown across all 20 categories
        category_scores_map = chosen_audit_run.category_scores or {} if chosen_audit_run else {}
        category_breakdowns: List[Dict[str, Any]] = []
        for cat_key, cat_meta in AUDIT_FRAMEWORK_CATEGORIES.items():
            cat_score_entry = category_scores_map.get(cat_key)
            if isinstance(cat_score_entry, dict):
                cat_score_val = cat_score_entry.get("score")
                cat_weight_val = cat_score_entry.get("weight", cat_meta.get("weight", 0.05))
            else:
                cat_score_val = cat_score_entry
                cat_weight_val = cat_meta.get("weight", 0.05)
            cat_findings = [f for f in resolved_findings if f["category_key"] == cat_key]
            category_breakdowns.append({
                "category_key": cat_key,
                "category_name": cat_meta.get("name", cat_key),
                "weight": cat_weight_val,
                "score": cat_score_val,
                "total_checks": len(cat_findings),
                "passed_checks": len([f for f in cat_findings if f["status"] == "PASS"]),
                "failed_checks": len([f for f in cat_findings if f["status"] == "FAIL"]),
                "warning_checks": len([f for f in cat_findings if f["status"] == "PARTIAL"]),
                "not_verified_checks": len([f for f in cat_findings if f["status"] in ("NOT_VERIFIED", "ERROR")])
            })

        resolved_audit = {
            "overall_score": chosen_audit_run.overall_score if chosen_audit_run else None,
            "audit_run_id": chosen_audit_run.id if chosen_audit_run else None,
            "status": chosen_audit_run.status if chosen_audit_run else "NOT_CONFIGURED",
            "completed_at": chosen_audit_run.completed_at.isoformat() if chosen_audit_run and chosen_audit_run.completed_at else None,
            "category_scores": category_scores_map,
            "category_breakdowns": category_breakdowns,
            "total_findings": len(resolved_findings),
            "critical_count": len(critical_findings),
            "warning_count": len(warning_findings),
            "passed_count": len(passed_findings),
            "findings": resolved_findings,
            "priority_findings": (critical_findings + warning_findings)[:10]
        }

        # =====================================================================
        # MODULE 3: 5x5 Geo-Grid Visibility & All Matrix Points + Competitors
        # =====================================================================
        geo_res = await db.execute(
            select(GeoGridScan)
            .options(
                selectinload(GeoGridScan.keyword_rel),
                selectinload(GeoGridScan.point_results)
            )
            .where(
                GeoGridScan.project_id == project_id,
                GeoGridScan.scan_status.in_(["completed", "completed_with_errors", "COMPLETED", "PARTIAL"])
            )
            .order_by(GeoGridScan.id.desc())
        )
        all_geo_scans = geo_res.scalars().all()
        standalone_geo = all_geo_scans[0] if all_geo_scans else None

        stage_geo = central_stages.get("geo")
        t_central_geo = _parse_dt(stage_geo.get("completed_at")) if stage_geo else central_completed_at
        t_standalone_geo = _parse_dt(standalone_geo.scanned_at or standalone_geo.started_at) if standalone_geo else None

        chosen_geo_scan: Optional[GeoGridScan] = None
        geo_source_type = "standalone_geogrid"
        geo_is_override = False

        if standalone_geo and (not t_central_geo or (t_standalone_geo and t_standalone_geo > t_central_geo)):
            chosen_geo_scan = standalone_geo
            geo_source_type = "standalone_geogrid"
            geo_is_override = True if t_central_geo else False
            geo_executed_at = t_standalone_geo or datetime.now(timezone.utc)
            geo_status = standalone_geo.scan_status.upper()
            geo_run_id = standalone_geo.id
        elif central_scan and stage_geo:
            central_scan_ids = (central_results.get("geo") or {}).get("scan_ids") or []
            if central_scan_ids:
                for gs in all_geo_scans:
                    if gs.id in central_scan_ids:
                        chosen_geo_scan = gs
                        break
            if not chosen_geo_scan:
                chosen_geo_scan = standalone_geo

            geo_source_type = "central_scan"
            geo_is_override = False
            geo_executed_at = t_central_geo or central_completed_at or datetime.now(timezone.utc)
            geo_status = stage_geo.get("status", "COMPLETED")
            geo_run_id = central_scan.id
        else:
            chosen_geo_scan = standalone_geo
            geo_source_type = "standalone_geogrid"
            geo_is_override = False
            geo_executed_at = t_standalone_geo or datetime.now(timezone.utc)
            geo_status = chosen_geo_scan.scan_status.upper() if chosen_geo_scan else "NOT_CONFIGURED"
            geo_run_id = chosen_geo_scan.id if chosen_geo_scan else None

        provenance["geo"] = {
            "source_type": geo_source_type,
            "source_run_id": geo_run_id,
            "source_module": "geo",
            "executed_at": geo_executed_at.isoformat() if geo_executed_at else None,
            "status": geo_status,
            "is_override": geo_is_override
        }

        # Load complete row-level grid points
        raw_points = chosen_geo_scan.point_results if chosen_geo_scan else []
        resolved_points: List[Dict[str, Any]] = []
        geogrid_competitors: List[Dict[str, Any]] = []

        for pt in raw_points:
            pt_dict = {
                "id": pt.id,
                "scan_id": pt.scan_id,
                "point_number": pt.point_number,
                "row": pt.row,
                "col": pt.col,
                "latitude": pt.latitude,
                "longitude": pt.longitude,
                "area_name": pt.area_name or f"Point {pt.point_number + 1}",
                "keyword": pt.keyword,
                "provider": pt.provider,
                "status": pt.status,
                "rank": pt.rank,
                "matched_business": pt.matched_business,
                "matched_place_id": pt.matched_place_id,
                "matched_domain": pt.matched_domain,
                "ranking_url": pt.ranking_url,
                "distance_km": pt.distance_km,
                "direction": pt.direction,
                "searched_at": pt.searched_at.isoformat() if pt.searched_at else None,
                "error": pt.error
            }
            resolved_points.append(pt_dict)

            # Ingest individual competitors for this point
            raw_comps = pt.competitors or []
            if isinstance(raw_comps, list):
                for comp in raw_comps:
                    if isinstance(comp, dict):
                        geogrid_competitors.append({
                            "scan_id": pt.scan_id,
                            "point_id": pt.id,
                            "point_number": pt.point_number,
                            "area_name": pt.area_name or f"Point {pt.point_number + 1}",
                            "keyword": pt.keyword,
                            "competitor_name": comp.get("name") or comp.get("title") or "Unknown",
                            "domain": comp.get("domain"),
                            "rank": comp.get("rank") or comp.get("position"),
                            "place_id": comp.get("place_id"),
                            "ranking_url": comp.get("url") or comp.get("website"),
                            "distance_km": pt.distance_km,
                            "rating": comp.get("rating"),
                            "reviews_count": comp.get("reviews_count") or comp.get("user_ratings_total")
                        })

        resolved_geo = {
            "scan_id": chosen_geo_scan.id if chosen_geo_scan else None,
            "keyword": chosen_geo_scan.keyword_rel.keyword if (chosen_geo_scan and chosen_geo_scan.keyword_rel) else None,
            "center_lat": chosen_geo_scan.center_lat if chosen_geo_scan else None,
            "center_lng": chosen_geo_scan.center_lng if chosen_geo_scan else None,
            "radius_km": chosen_geo_scan.radius_km if chosen_geo_scan else None,
            "grid_size": chosen_geo_scan.grid_size if chosen_geo_scan else 5,
            "local_visibility_pct": chosen_geo_scan.local_visibility_pct if chosen_geo_scan else 0.0,
            "average_rank": chosen_geo_scan.average_rank if chosen_geo_scan else None,
            "total_points": chosen_geo_scan.total_points if chosen_geo_scan else len(resolved_points),
            "completed_points": chosen_geo_scan.completed_points if chosen_geo_scan else len([p for p in resolved_points if p["status"] == "SUCCESS"]),
            "ranking_found_points": chosen_geo_scan.ranking_found_points if chosen_geo_scan else len([p for p in resolved_points if p["rank"] is not None]),
            "not_found_points": chosen_geo_scan.not_found_points if chosen_geo_scan else len([p for p in resolved_points if p["rank"] is None]),
            "scanned_at": chosen_geo_scan.scanned_at.isoformat() if chosen_geo_scan and chosen_geo_scan.scanned_at else None,
            "points": resolved_points,
            "competitors": geogrid_competitors
        }

        # =====================================================================
        # MODULE 4: Technical Website Audit, Crawl & PageSpeed
        # =====================================================================
        # Fetch latest SEOAudit
        seo_res = await db.execute(
            select(SEOAudit)
            .options(selectinload(SEOAudit.issues))
            .where(SEOAudit.project_id == project_id)
            .order_by(SEOAudit.id.desc())
        )
        all_seo_audits = seo_res.scalars().all()
        standalone_seo_audit = all_seo_audits[0] if all_seo_audits else None

        # Fetch latest AuditJob
        job_res = await db.execute(
            select(AuditJob)
            .where(AuditJob.project_id == project_id)
            .order_by(AuditJob.id.desc())
        )
        latest_audit_job = job_res.scalars().first()

        # Fetch WebsitePages
        pages_res = await db.execute(
            select(WebsitePage)
            .join(Website, Website.id == WebsitePage.website_id)
            .where(Website.project_id == project_id)
            .order_by(WebsitePage.id.asc())
        )
        all_pages = pages_res.scalars().all()

        stage_wa = central_stages.get("website_audit")
        t_central_wa = _parse_dt(stage_wa.get("completed_at")) if stage_wa else central_completed_at
        t_standalone_wa = _parse_dt(standalone_seo_audit.created_at) if standalone_seo_audit else None

        wa_source_type = "standalone_website_audit"
        wa_is_override = False
        if standalone_seo_audit and (not t_central_wa or (t_standalone_wa and t_standalone_wa > t_central_wa)):
            wa_source_type = "standalone_website_audit"
            wa_is_override = True if t_central_wa else False
            wa_executed_at = t_standalone_wa or datetime.now(timezone.utc)
            wa_run_id = standalone_seo_audit.id
        elif central_scan and stage_wa:
            wa_source_type = "central_scan"
            wa_is_override = False
            wa_executed_at = t_central_wa or central_completed_at or datetime.now(timezone.utc)
            wa_run_id = central_scan.id
        else:
            wa_source_type = "standalone_website_audit"
            wa_is_override = False
            wa_executed_at = t_standalone_wa or datetime.now(timezone.utc)
            wa_run_id = standalone_seo_audit.id if standalone_seo_audit else None

        provenance["website_audit"] = {
            "source_type": wa_source_type,
            "source_run_id": wa_run_id,
            "source_module": "website_audit",
            "executed_at": wa_executed_at.isoformat() if wa_executed_at else None,
            "status": "COMPLETED" if standalone_seo_audit or stage_wa else "NOT_CONFIGURED",
            "is_override": wa_is_override
        }

        # Resolve PageSpeed details from central_results or SEOAudit
        pagespeed_data = (central_results.get("website_audit") or {}).get("pagespeed") or central_results.get("pagespeed")
        if not pagespeed_data and standalone_seo_audit and standalone_seo_audit.details:
            pagespeed_data = standalone_seo_audit.details.get("pagespeed")

        # Resolve all website pages
        resolved_pages: List[Dict[str, Any]] = []
        for p in all_pages:
            resolved_pages.append({
                "id": p.id,
                "url": p.url,
                "status_code": p.status_code,
                "title": p.title,
                "meta_description": p.meta_description,
                "h1": p.h1,
                "h2_list": p.h2_list or [],
                "word_count": p.word_count or 0,
                "canonical_url": p.canonical_url,
                "is_indexable": p.is_indexable,
                "load_time_ms": p.load_time_ms or 0,
                "schema_types": p.schema_types or [],
                "phones_found": p.phones_found or [],
                "emails_found": p.emails_found or [],
                "images_count": p.images_count or 0,
                "missing_alt_count": p.missing_alt_count or 0,
                "internal_links_count": p.internal_links_count or 0,
                "external_links_count": p.external_links_count or 0,
                "broken_links": p.broken_links or [],
                "issues_detected": p.issues_detected or [],
                "created_at": p.created_at.isoformat() if p.created_at else None
            })

        # Resolve all technical SEO issues
        raw_issues = standalone_seo_audit.issues if standalone_seo_audit else []
        resolved_issues: List[Dict[str, Any]] = []
        for iss in raw_issues:
            resolved_issues.append({
                "id": iss.id,
                "category": iss.category,
                "severity": iss.severity.value if hasattr(iss.severity, "value") else str(iss.severity),
                "title": iss.title,
                "evidence": iss.evidence,
                "why_it_matters": iss.why_it_matters,
                "recommended_solution": iss.recommended_solution,
                "action_type": iss.action_type,
                "affected_url": iss.affected_url,
                "status": iss.status.value if hasattr(iss.status, "value") else str(iss.status),
                "created_at": iss.created_at.isoformat() if iss.created_at else None
            })

        resolved_website_audit = {
            "health_score": standalone_seo_audit.overall_score if standalone_seo_audit else project.technical_score,
            "pages_analyzed": len(resolved_pages) if resolved_pages else (standalone_seo_audit.pages_analyzed if standalone_seo_audit else 0),
            "critical_issues": len([i for i in resolved_issues if i["severity"].lower() == "critical"]),
            "warnings": len([i for i in resolved_issues if i["severity"].lower() == "warning"]),
            "passed_checks": standalone_seo_audit.passed_checks if standalone_seo_audit else 0,
            "pagespeed": pagespeed_data,
            "audit_job": {
                "id": latest_audit_job.id if latest_audit_job else None,
                "status": latest_audit_job.status.value if latest_audit_job and hasattr(latest_audit_job.status, "value") else "completed",
                "started_at": latest_audit_job.started_at.isoformat() if latest_audit_job and latest_audit_job.started_at else None,
                "completed_at": latest_audit_job.completed_at.isoformat() if latest_audit_job and latest_audit_job.completed_at else None
            } if latest_audit_job else None,
            "pages": resolved_pages,
            "issues": resolved_issues
        }

        # =====================================================================
        # MODULE 5: Tracked Keywords & Rankings
        # =====================================================================
        kw_res = await db.execute(
            select(Keyword)
            .options(selectinload(Keyword.rank_history))
            .where(Keyword.project_id == project_id)
            .order_by(Keyword.id.asc())
        )
        all_keywords = kw_res.scalars().all()
        
        stage_kw = central_stages.get("rankings")
        t_central_kw = _parse_dt(stage_kw.get("completed_at")) if stage_kw else central_completed_at
        latest_kw_check = max([_parse_dt(k.last_checked_at) for k in all_keywords if k.last_checked_at] or [datetime.now(timezone.utc)])

        kw_source_type = "standalone_keywords"
        kw_is_override = False
        if all_keywords and (not t_central_kw or latest_kw_check > t_central_kw):
            kw_source_type = "standalone_keywords"
            kw_is_override = True if t_central_kw else False
            kw_executed_at = latest_kw_check
        elif central_scan and stage_kw:
            kw_source_type = "central_scan"
            kw_is_override = False
            kw_executed_at = t_central_kw or central_completed_at or datetime.now(timezone.utc)
        else:
            kw_source_type = "standalone_keywords"
            kw_is_override = False
            kw_executed_at = latest_kw_check

        provenance["rankings"] = {
            "source_type": kw_source_type,
            "source_run_id": central_scan.id if kw_source_type == "central_scan" else project.id,
            "source_module": "rankings",
            "executed_at": kw_executed_at.isoformat() if kw_executed_at else None,
            "status": "COMPLETED" if all_keywords or stage_kw else "NOT_CONFIGURED",
            "is_override": kw_is_override
        }

        resolved_keywords: List[Dict[str, Any]] = []
        ranking_history_rows: List[Dict[str, Any]] = []
        for k in all_keywords:
            resolved_keywords.append({
                "id": k.id,
                "keyword": k.keyword,
                "search_intent": k.search_intent,
                "search_volume": k.search_volume,
                "difficulty": k.difficulty,
                "target_location": k.target_location,
                "current_rank": k.current_rank,
                "previous_rank": k.previous_rank,
                "target_rank": k.target_rank,
                "ranking_url": k.ranking_url,
                "serp_type": k.serp_type,
                "opportunity_score": k.opportunity_score,
                "business_relevance": k.business_relevance,
                "last_checked_at": k.last_checked_at.isoformat() if k.last_checked_at else None
            })
            for h in (k.rank_history or []):
                ranking_history_rows.append({
                    "keyword_id": k.id,
                    "keyword": k.keyword,
                    "location_name": h.location_name,
                    "rank_position": h.rank_position,
                    "serp_type": h.serp_type,
                    "checked_at": h.checked_at.isoformat() if h.checked_at else None
                })

        # =====================================================================
        # MODULE 6: Reputation & Reviews
        # =====================================================================
        rev_res = await db.execute(
            select(Review).where(Review.project_id == project_id).order_by(Review.review_date.desc())
        )
        all_reviews = rev_res.scalars().all()
        stage_rev = central_stages.get("reviews")
        t_central_rev = _parse_dt(stage_rev.get("completed_at")) if stage_rev else central_completed_at
        latest_rev_dt = max([_parse_dt(r.created_at or r.review_date) for r in all_reviews] or [datetime.now(timezone.utc)])

        rev_source_type = "reviews_service"
        rev_is_override = False
        if all_reviews and (not t_central_rev or latest_rev_dt > t_central_rev):
            rev_source_type = "reviews_service"
            rev_is_override = True if t_central_rev else False
            rev_executed_at = latest_rev_dt
        elif central_scan and stage_rev:
            rev_source_type = "central_scan"
            rev_is_override = False
            rev_executed_at = t_central_rev or central_completed_at or datetime.now(timezone.utc)
        else:
            rev_source_type = "reviews_service"
            rev_is_override = False
            rev_executed_at = latest_rev_dt

        provenance["reviews"] = {
            "source_type": rev_source_type,
            "source_run_id": central_scan.id if rev_source_type == "central_scan" else project.id,
            "source_module": "reviews",
            "executed_at": rev_executed_at.isoformat() if rev_executed_at else None,
            "status": "COMPLETED" if all_reviews or stage_rev else "NOT_CONFIGURED",
            "is_override": rev_is_override
        }

        total_revs = len(all_reviews)
        avg_rating = round(sum(r.rating for r in all_reviews) / total_revs, 1) if total_revs > 0 else None
        resolved_reviews: List[Dict[str, Any]] = []
        for r in all_reviews:
            resolved_reviews.append({
                "id": r.id,
                "author_name": r.author_name,
                "rating": r.rating,
                "review_text": r.review_text,
                "review_date": r.review_date.isoformat() if r.review_date else None,
                "response_text": r.response_text,
                "response_status": r.response_status,
                "response_date": r.response_date.isoformat() if r.response_date else None,
                "source": r.source,
                "sentiment": r.sentiment,
                "topics": r.topics or [],
                "created_at": r.created_at.isoformat() if r.created_at else None
            })

        # =====================================================================
        # MODULE 7: Directory Citations
        # =====================================================================
        cit_res = await db.execute(
            select(Citation).where(Citation.project_id == project_id).order_by(Citation.id.asc())
        )
        all_citations = cit_res.scalars().all()
        stage_cit = central_stages.get("citations")
        t_central_cit = _parse_dt(stage_cit.get("completed_at")) if stage_cit else central_completed_at
        latest_cit_dt = max([_parse_dt(c.created_at) for c in all_citations] or [datetime.now(timezone.utc)])

        cit_source_type = "citations_service"
        cit_is_override = False
        if all_citations and (not t_central_cit or latest_cit_dt > t_central_cit):
            cit_source_type = "citations_service"
            cit_is_override = True if t_central_cit else False
            cit_executed_at = latest_cit_dt
        elif central_scan and stage_cit:
            cit_source_type = "central_scan"
            cit_is_override = False
            cit_executed_at = t_central_cit or central_completed_at or datetime.now(timezone.utc)
        else:
            cit_source_type = "citations_service"
            cit_is_override = False
            cit_executed_at = latest_cit_dt

        provenance["citations"] = {
            "source_type": cit_source_type,
            "source_run_id": central_scan.id if cit_source_type == "central_scan" else project.id,
            "source_module": "citations",
            "executed_at": cit_executed_at.isoformat() if cit_executed_at else None,
            "status": "COMPLETED" if all_citations or stage_cit else "NOT_CONFIGURED",
            "is_override": cit_is_override
        }

        matching_cits = len([c for c in all_citations if c.nap_status in ("consistent", "match")])
        resolved_citations: List[Dict[str, Any]] = []
        for c in all_citations:
            resolved_citations.append({
                "id": c.id,
                "directory_name": c.source_name or c.domain,
                "domain": c.domain,
                "listing_url": c.listing_url,
                "domain_authority": c.domain_authority,
                "status": c.status,
                "nap_status": c.nap_status,
                "verification_status": c.verification_status,
                "citation_type": c.citation_type,
                "found_name": c.found_name,
                "found_address": c.found_address,
                "found_phone": c.found_phone,
                "found_website": c.found_website,
                "created_at": c.created_at.isoformat() if c.created_at else None
            })

        # =====================================================================
        # MODULE 8: NAP Consistency
        # =====================================================================
        nap_res = await db.execute(
            select(NAPRecord).where(NAPRecord.project_id == project_id).order_by(NAPRecord.id.desc())
        )
        nap_record = nap_res.scalars().first()
        nap_comparison = await NAPComparisonService.compare_project_nap(project_id, db)
        
        nap_score = nap_comparison.get("nap_consistency_pct")
        if nap_score is None and nap_record and nap_record.nap_score is not None:
            nap_score = nap_record.nap_score

        provenance["nap"] = {
            "source_type": "nap_consistency_engine",
            "source_run_id": central_scan.id if central_scan else (nap_record.id if nap_record else project.id),
            "source_module": "nap",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED",
            "is_override": False
        }

        # =====================================================================
        # MODULE 9: Schema.org Intelligence
        # =====================================================================
        sch_res = await db.execute(
            select(SchemaRecord).where(SchemaRecord.project_id == project_id).order_by(SchemaRecord.id.asc())
        )
        all_schemas = sch_res.scalars().all()
        resolved_schemas: List[Dict[str, Any]] = []
        unique_schema_types = set()
        for s in all_schemas:
            if s.schema_type:
                unique_schema_types.add(s.schema_type)
            resolved_schemas.append({
                "id": s.id,
                "page_url": s.page_url,
                "schema_type": s.schema_type,
                "page_type": s.page_type,
                "business_type": s.business_type,
                "is_valid": s.is_valid,
                "quality_score": s.quality_score,
                "detected_types": s.detected_types or [],
                "applicable_schemas": s.applicable_schemas or {},
                "errors": s.errors or [],
                "warnings": s.warnings or [],
                "missing_properties": s.missing_properties or [],
                "nap_status": s.nap_status,
                "raw_json_ld": s.raw_json_ld,
                "last_validated_at": s.last_validated_at.isoformat() if s.last_validated_at else None
            })

        provenance["schema"] = {
            "source_type": "schema_engine",
            "source_run_id": central_scan.id if central_scan else project.id,
            "source_module": "schema",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED" if all_schemas else "NOT_CONFIGURED",
            "is_override": False
        }

        # =====================================================================
        # MODULE 10: Competitor Intelligence
        # =====================================================================
        comp_res = await db.execute(
            select(Competitor).where(Competitor.project_id == project_id).order_by(Competitor.id.asc())
        )
        all_competitors = comp_res.scalars().all()
        resolved_competitors: List[Dict[str, Any]] = []
        for comp in all_competitors:
            resolved_competitors.append({
                "id": comp.id,
                "name": comp.name,
                "domain": comp.domain,
                "gbp_name": comp.gbp_name,
                "place_id": comp.place_id,
                "rating": comp.rating,
                "reviews_count": comp.reviews_count or 0,
                "citations_count": comp.citations_count or 0,
                "backlinks_count": comp.backlinks_count or 0,
                "local_visibility_score": comp.local_visibility_score,
                "geo_grid_share_pct": comp.geo_grid_share_pct,
                "top_keywords_count": comp.top_keywords_count or 0,
                "avg_maps_rank": comp.avg_maps_rank,
                "source": comp.source,
                "last_seen_at": comp.last_seen_at.isoformat() if comp.last_seen_at else None
            })

        provenance["competitors"] = {
            "source_type": "competitor_intelligence",
            "source_run_id": central_scan.id if central_scan else project.id,
            "source_module": "competitors",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED" if all_competitors else "NOT_CONFIGURED",
            "is_override": False
        }

        # =====================================================================
        # MODULE 11: Content & Suburban Landing Page Gaps
        # =====================================================================
        content_opps = await ContentOpportunityEngine.generate_opportunities(project_id, db)
        provenance["content_gaps"] = {
            "source_type": "content_opportunity_engine",
            "source_run_id": central_scan.id if central_scan else project.id,
            "source_module": "content_gaps",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETED" if content_opps else "NOT_CONFIGURED",
            "is_override": False
        }

        # =====================================================================
        # MODULE 12: Google Business Profile (OAuth / Places Status)
        # =====================================================================
        gbp_status = (central_results.get("gbp") or {}).get("status", "VERIFIED_PUBLIC_PLACES" if profile.place_id else "NOT_CONNECTED")
        provenance["gbp"] = {
            "source_type": "central_scan" if central_scan else "google_business_service",
            "source_run_id": central_scan.id if central_scan else project.id,
            "source_module": "gbp",
            "executed_at": (central_completed_at or datetime.now(timezone.utc)).isoformat(),
            "status": gbp_status,
            "is_override": False
        }

        # =====================================================================
        # MODULE 13: Executive Narrative & 90-Day Action Roadmap
        # =====================================================================
        # Overall Local SEO Health Score calculation
        health_score = resolved_audit.get("overall_score")
        if health_score is None:
            health_score = project.health_score

        summary_parts = []
        score_text = f"{health_score}/100" if health_score is not None else "Score unavailable"
        summary_parts.append(
            f"{profile.business_name} currently has an overall Local SEO Health Score of {score_text} "
            f"evaluated across {len(resolved_findings)} audit checkpoints."
        )

        if resolved_geo.get("local_visibility_pct") is not None:
            summary_parts.append(
                f"Localized territory visibility across the 5x5 Geo-Grid is {resolved_geo['local_visibility_pct']}% "
                f"(average rank: {resolved_geo.get('average_rank') or 'N/A'})."
            )
        else:
            summary_parts.append("5x5 Geo-Grid rankings are awaiting initial geographic scan.")

        if resolved_keywords:
            top_3 = len([k for k in resolved_keywords if k.get("current_rank") and k["current_rank"] <= 3])
            summary_parts.append(f"Tracking {len(resolved_keywords)} high-intent local search keywords with {top_3} ranking in the Top 3 Local Pack.")

        if total_revs > 0:
            summary_parts.append(f"Customer reputation displays {total_revs} recorded reviews with an average rating of {avg_rating or 0.0}/5.0.")

        if resolved_citations:
            summary_parts.append(f"Audited {len(resolved_citations)} directory citations with {matching_cits} matching canonical NAP.")

        executive_summary_text = " ".join(summary_parts)

        # Dynamic 90-Day Action Plan
        action_plan = {
            "month_1": {
                "focus": "Foundation, Canonical NAP Standardization & Critical Checkpoint Fixes",
                "actions": [f["recommended_action"] for f in critical_findings[:4]] or [
                    "Standardize business name, address, and phone number across Google Business Profile and core citations.",
                    "Resolve top crawl issues and missing meta title/descriptions on high-priority service pages.",
                    "Verify canonical LocalBusiness schema markup implementation on homepage."
                ]
            },
            "month_2": {
                "focus": "On-Page Localization, Schema Optimization & Suburban Landing Pages",
                "actions": [f["recommended_action"] for f in warning_findings[:4]] or [
                    "Implement localized Schema.org JSON-LD markup with exact geo-coordinates on all service area landing pages.",
                    "Publish targeted suburban landing pages for highest search-intent service areas.",
                    "Align primary and secondary GBP categories with leading local ranking competitors."
                ]
            },
            "month_3": {
                "focus": "Authority Building, Review Velocity & 5x5 Geo-Grid Expansion",
                "actions": [
                    "Launch automated customer review request workflow to build monthly review velocity.",
                    "Acquire prominent citations across regional directories and industry associations.",
                    "Run recurring 5x5 Geo-Grid tracking scans to verify expansion of Top 3 Local Pack coverage."
                ]
            }
        }

        # Dynamic Next Month Recommendations
        recs: List[str] = []
        if critical_findings:
            recs.append(f"Resolve {len(critical_findings)} critical Local SEO audit findings affecting foundational crawlability and NAP trust.")
        if len(resolved_keywords) > 0 and len([k for k in resolved_keywords if k.get("current_rank") and k["current_rank"] <= 3]) == 0:
            recs.append("Optimize localized landing pages and GBP primary categories to push tracked keywords into Top 3 Local Pack positions.")
        if total_revs == 0 or (avg_rating and avg_rating < 4.6):
            recs.append("Accelerate customer review collection campaign to build competitive social proof and increase review rating density.")
        if nap_score is None or nap_score < 90:
            recs.append("Audit and standardize mismatched NAP listings across major search and directory citation networks.")
        if not resolved_schemas:
            recs.append("Deploy structured LocalBusiness Schema.org JSON-LD to qualify for search engine rich snippets.")
        if len(recs) < 4:
            recs.append("Publish regular Google Business Profile updates and optimize localized service post coverage.")

        # =====================================================================
        # Provenance Metadata & Completeness Verification
        # =====================================================================
        now_utc = datetime.now(timezone.utc)
        
        # Calculate authoritative "data_as_of" timestamp (latest execution among all resolved modules)
        all_exec_timestamps = []
        for prov in provenance.values():
            dt = _parse_dt(prov.get("executed_at"))
            if dt:
                all_exec_timestamps.append(dt)
        data_as_of = max(all_exec_timestamps) if all_exec_timestamps else now_utc

        coverage_stats = {
            "audit_categories_count": len(category_breakdowns),
            "audit_findings_count": len(resolved_findings),
            "geogrid_points_count": len(resolved_points),
            "geogrid_competitors_count": len(geogrid_competitors),
            "website_pages_count": len(resolved_pages),
            "website_issues_count": len(resolved_issues),
            "keywords_count": len(resolved_keywords),
            "reviews_count": len(resolved_reviews),
            "citations_count": len(resolved_citations),
            "competitors_count": len(resolved_competitors),
            "schema_records_count": len(resolved_schemas),
            "content_gaps_count": len(content_opps)
        }

        override_modules = [m for m, p in provenance.items() if p.get("is_override")]

        return {
            "title": f"Local SEO Intelligence & Audit Report — {profile.business_name}",
            "project_id": project.id,
            "organization_id": project.organization_id,
            "report_generated_at": now_utc.isoformat(),
            "data_as_of": data_as_of.isoformat(),
            "central_scan": {
                "id": central_scan.id if central_scan else None,
                "status": central_scan.status if central_scan else "NOT_CONFIGURED",
                "completed_at": central_completed_at.isoformat() if central_completed_at else None,
                "completed_stages_count": central_scan.completed_stages_count if central_scan else 0,
                "total_stages_count": central_scan.total_stages_count if central_scan else 13
            },
            "provenance": provenance,
            "overrides_summary": {
                "has_overrides": len(override_modules) > 0,
                "override_modules": override_modules,
                "total_overrides": len(override_modules)
            },
            "coverage": coverage_stats,
            "health_score": health_score,
            "business_profile": resolved_bp,
            "executive_summary": {
                "narrative": executive_summary_text,
                "overall_health_score": health_score,
                "sub_scores": {
                    "technical": project.technical_score,
                    "onpage": project.onpage_score,
                    "local": project.local_score,
                    "gbp": project.gbp_score,
                    "reviews": project.reviews_score,
                    "citations": project.citations_score,
                    "keywords": project.keywords_score,
                    "maps": project.maps_score
                },
                "metrics": {
                    "total_keywords": len(resolved_keywords),
                    "top_3_keywords": len([k for k in resolved_keywords if k.get("current_rank") and k["current_rank"] <= 3]),
                    "top_10_keywords": len([k for k in resolved_keywords if k.get("current_rank") and k["current_rank"] <= 10]),
                    "total_reviews": total_revs,
                    "avg_rating": avg_rating,
                    "nap_consistency_pct": nap_score,
                    "open_issues_count": len(critical_findings) + len(warning_findings),
                    "local_visibility_pct": resolved_geo.get("local_visibility_pct")
                },
                "next_month_recommendations": recs[:4]
            },
            "audit": resolved_audit,
            "geo_visibility": resolved_geo,
            "website_audit": resolved_website_audit,
            "keywords": resolved_keywords,
            "ranking_history": ranking_history_rows,
            "reputation": {
                "total_reviews": total_revs,
                "average_rating": avg_rating,
                "unanswered_count": len([r for r in resolved_reviews if not r.get("response_text")]),
                "reviews": resolved_reviews
            },
            "citations": {
                "total": len(resolved_citations),
                "matching_nap_count": matching_cits,
                "listings": resolved_citations
            },
            "nap": {
                "nap_score": nap_score,
                "total_sources_evaluated": nap_comparison.get("total_sources_evaluated", len(resolved_citations)),
                "consistent_sources_count": nap_comparison.get("consistent_sources_count", matching_cits),
                "mismatches_count": nap_comparison.get("mismatches_count", len(resolved_citations) - matching_cits),
                "mismatches_data": nap_comparison.get("mismatches_data", [])
            },
            "schema": {
                "total_records": len(resolved_schemas),
                "unique_types": list(unique_schema_types),
                "records": resolved_schemas
            },
            "competitors": {
                "total": len(resolved_competitors),
                "items": resolved_competitors
            },
            "content_gaps": {
                "total": len(content_opps),
                "opportunities": content_opps
            },
            "priority_findings": resolved_audit.get("priority_findings", []),
            "action_plan": action_plan,
            "methodology": {
                "VERIFIED": "Direct live API verification from Google Business Profile or authenticated services.",
                "OBSERVED": "Directly crawled and parsed from live web URLs, HTML markup, or verified directory listings.",
                "USER_PROVIDED": "Information submitted manually by the user or client profile.",
                "DETECTED": "Algorithmic inference or pattern detection from page contents or search results.",
                "NOT_VERIFIED": "Third-party or external entity status cannot be confirmed without active API keys or credentials."
            }
        }
