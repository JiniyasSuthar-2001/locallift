from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.core.audit_logger import log_user_action
from app.models.user import User
from app.models.project import Project
from app.api.v1.audits import get_canonical_audit
from app.services.reports.pdf_service import AuditPDFService
from app.services.reports.xlsx_service import MasterXLSXService
from app.services.reports.report_snapshot_service import ReportSnapshotService
from app.services.reports.local_seo_pdf_service import LocalSEOPDFService
from app.services.reports.local_seo_xlsx_service import LocalSEOXLSXService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{project_id}/local-seo/snapshot")
async def get_local_seo_report_snapshot(
    request: Request,
    project_id: int,
    scan_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the deterministic, authoritative resolved report dataset across Central Intelligence Scans
    and standalone module runs with precise provenance and completeness guarantees.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "GENERATE_LOCAL_SEO_SNAPSHOT",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        report_type="local_seo_snapshot"
    )

    snapshot = await ReportSnapshotService.resolve_report_snapshot(
        project_id=project_id,
        db=db,
        specific_central_scan_id=scan_id
    )
    return snapshot


@router.get("/{project_id}/local-seo")
async def generate_local_seo_report(
    request: Request,
    project_id: int,
    scan_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Backward-compatible endpoint returning the full resolved Local SEO Intelligence report snapshot.
    """
    return await get_local_seo_report_snapshot(
        request=request,
        project_id=project_id,
        scan_id=scan_id,
        current_user=current_user,
        db=db
    )


@router.get("/{project_id}/executive")
async def generate_executive_report(
    request: Request,
    project_id: int,
    scan_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns executive-level summary & KPIs generated from the EXACT same resolved report dataset.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "GENERATE_EXECUTIVE_REPORT",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        report_type="executive"
    )

    snapshot = await ReportSnapshotService.resolve_report_snapshot(
        project_id=project_id,
        db=db,
        specific_central_scan_id=scan_id
    )

    bp = snapshot.get("business_profile") or {}
    exec_data = snapshot.get("executive_summary") or {}
    metrics = exec_data.get("metrics") or {}

    return {
        "title": f"Local SEO Executive Performance Report — {bp.get('business_name') or project.name}",
        "generated_at": snapshot.get("report_generated_at"),
        "data_as_of": snapshot.get("data_as_of"),
        "provenance": snapshot.get("provenance"),
        "project": {
            "name": bp.get("business_name") or project.name,
            "domain": bp.get("website") or project.domain,
            "primary_category": bp.get("primary_category") or project.primary_category,
            "health_score": snapshot.get("health_score"),
            "sub_scores": exec_data.get("sub_scores") or {}
        },
        "executive_summary": exec_data.get("narrative"),
        "metrics": {
            "total_keywords": metrics.get("total_keywords", 0),
            "top_3_keywords": metrics.get("top_3_keywords", 0),
            "top_10_keywords": metrics.get("top_10_keywords", 0),
            "total_reviews": metrics.get("total_reviews", 0),
            "avg_rating": metrics.get("avg_rating"),
            "nap_consistency_score": metrics.get("nap_consistency_pct"),
            "open_issues_count": metrics.get("open_issues_count", 0),
            "local_visibility_pct": metrics.get("local_visibility_pct", 0.0)
        },
        "next_month_recommendations": exec_data.get("next_month_recommendations") or []
    }


@router.get("/{project_id}/local-seo/pdf")
async def download_local_seo_pdf(
    project_id: int,
    scan_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads the white-label Local SEO Intelligence & Audit Report PDF generated
    from the authoritative resolved snapshot without arbitrary data truncation.
    """
    project = await verify_project_access(project_id, current_user, db)
    snapshot = await ReportSnapshotService.resolve_report_snapshot(
        project_id=project_id,
        db=db,
        specific_central_scan_id=scan_id
    )
    pdf_bytes = LocalSEOPDFService.generate_pdf(snapshot)

    domain = (snapshot.get("business_profile", {}).get("website") or project.domain or "business")
    domain_clean = domain.replace("https://", "").replace("http://", "").replace("/", "").replace(":", "_")
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"LocalSEO_Intelligence_Audit_{domain_clean}_{date_str}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{project_id}/local-seo/xlsx")
async def download_local_seo_xlsx(
    project_id: int,
    scan_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads the Master Local SEO Intelligence & Audit XLSX Workbook generated
    from the authoritative resolved snapshot across all 22 structured sheets.
    """
    project = await verify_project_access(project_id, current_user, db)
    snapshot = await ReportSnapshotService.resolve_report_snapshot(
        project_id=project_id,
        db=db,
        specific_central_scan_id=scan_id
    )
    xlsx_bytes = LocalSEOXLSXService.generate_xlsx(snapshot)

    domain = (snapshot.get("business_profile", {}).get("website") or project.domain or "business")
    domain_clean = domain.replace("https://", "").replace("http://", "").replace("/", "").replace(":", "_")
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"LocalSEO_Intelligence_Audit_{domain_clean}_{date_str}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# =====================================================================
# Canonical Technical Website Audit Exports (Separate from Local SEO)
# =====================================================================
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
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
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
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
