"""
LocalLift — Central Local SEO Intelligence Scan API Endpoints

Provides central project-level scan execution, polling, and results retrieval.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models.user import User
from app.models.intelligence_scan import ProjectIntelligenceScan, ScanStatus
from app.core.deps import get_current_user, verify_project_access
from app.core.audit_logger import log_user_action
from app.services.local_seo.intelligence_scan_service import LocalIntelligenceScanService
from app.services.local_seo.scan_allowance_service import ScanAllowanceService
from app.models.connections import OrganizationSERPConfig

logger = logging.getLogger("locallift.intelligence_scan_api")

router = APIRouter(prefix="/projects", tags=["Central Intelligence Scan"])


@router.post("/{project_id}/intelligence-scan")
async def trigger_intelligence_scan(
    request: Request,
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers or resumes a comprehensive 13-stage Central Local SEO Intelligence Scan for the project.
    Executes in background and returns initial scan tracking state.
    """
    project = await verify_project_access(project_id, current_user, db)

    # Check monthly scan allowance before triggering a new scan
    is_allowed, allowance_info = await ScanAllowanceService.check_allowance(db, project.organization_id)
    if not is_allowed:
        used_count = allowance_info.get("used", 0)
        limit_count = allowance_info.get("allowed", 0)
        raise HTTPException(
            status_code=429,
            detail=f"Your monthly LocalLift audit allowance has been used. ({used_count}/{limit_count} used this month. Resets next billing cycle.)"
        )

    log_user_action(
        request, "TRIGGER_CENTRAL_INTELLIGENCE_SCAN",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        business_name=project.name
    )

    scan = await LocalIntelligenceScanService.get_or_create_scan(
        project_id=project_id,
        organization_id=project.organization_id,
        db=db
    )

    # If it was freshly queued, enqueue background execution
    if scan.status == ScanStatus.QUEUED.value:
        background_tasks.add_task(
            LocalIntelligenceScanService.run_scan_task,
            scan_id=scan.id,
            project_id=project_id
        )

    return {
        "scan_id": scan.id,
        "project_id": scan.project_id,
        "status": scan.status,
        "progress_pct": scan.progress_pct,
        "current_stage": scan.current_stage,
        "current_stage_label": scan.current_stage_label,
        "completed_stages_count": scan.completed_stages_count,
        "total_stages_count": scan.total_stages_count,
        "stages": scan.stages,
        "results_summary": scan.results_summary,
        "error_summary": scan.error_summary,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None
    }


@router.get("/{project_id}/intelligence-scan/latest")
async def get_latest_intelligence_scan(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the most recent Central Intelligence Scan for the active project.
    """
    await verify_project_access(project_id, current_user, db)

    stmt = (
        select(ProjectIntelligenceScan)
        .where(ProjectIntelligenceScan.project_id == project_id)
        .order_by(ProjectIntelligenceScan.id.desc())
    )
    res = await db.execute(stmt)
    scan = res.scalars().first()

    if not scan:
        return {
            "has_scan": False,
            "scan": None,
            "message": "No intelligence scans have been executed for this project."
        }

    return {
        "has_scan": True,
        "scan": {
            "scan_id": scan.id,
            "project_id": scan.project_id,
            "status": scan.status,
            "progress_pct": scan.progress_pct,
            "current_stage": scan.current_stage,
            "current_stage_label": scan.current_stage_label,
            "completed_stages_count": scan.completed_stages_count,
            "total_stages_count": scan.total_stages_count,
            "stages": scan.stages,
            "results_summary": scan.results_summary,
            "error_summary": scan.error_summary,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None
        }
    }


@router.get("/{project_id}/intelligence-scan/{scan_id}")
async def get_intelligence_scan_status(
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Polls real-time execution status for a specific Central Intelligence Scan.
    """
    await verify_project_access(project_id, current_user, db)

    stmt = select(ProjectIntelligenceScan).where(
        ProjectIntelligenceScan.id == scan_id,
        ProjectIntelligenceScan.project_id == project_id
    )
    res = await db.execute(stmt)
    scan = res.scalars().first()

    if not scan:
        raise HTTPException(status_code=404, detail="Intelligence scan not found for this project.")

    return {
        "scan_id": scan.id,
        "project_id": scan.project_id,
        "status": scan.status,
        "progress_pct": scan.progress_pct,
        "current_stage": scan.current_stage,
        "current_stage_label": scan.current_stage_label,
        "completed_stages_count": scan.completed_stages_count,
        "total_stages_count": scan.total_stages_count,
        "stages": scan.stages,
        "results_summary": scan.results_summary,
        "error_summary": scan.error_summary,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None
    }


@router.post("/{project_id}/intelligence-scan/{scan_id}/cancel")
async def cancel_intelligence_scan_by_id(
    request: Request,
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels an in-progress Central Local SEO Intelligence Scan.
    Preserves completed stages, marks scan status as CANCELLED, and returns partial results.
    """
    project = await verify_project_access(project_id, current_user, db)

    log_user_action(
        request, "CANCEL_CENTRAL_INTELLIGENCE_SCAN",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        scan_id=scan_id
    )

    cancelled_scan = await LocalIntelligenceScanService.cancel_scan(
        scan_id=scan_id,
        project_id=project_id,
        db=db
    )

    return {
        "scan_id": cancelled_scan.id,
        "project_id": cancelled_scan.project_id,
        "status": cancelled_scan.status,
        "progress_pct": cancelled_scan.progress_pct,
        "current_stage": cancelled_scan.current_stage,
        "current_stage_label": cancelled_scan.current_stage_label,
        "completed_stages_count": cancelled_scan.completed_stages_count,
        "total_stages_count": cancelled_scan.total_stages_count,
        "stages": cancelled_scan.stages,
        "results_summary": cancelled_scan.results_summary,
        "error_summary": cancelled_scan.error_summary,
        "started_at": cancelled_scan.started_at.isoformat() if cancelled_scan.started_at else None,
        "completed_at": cancelled_scan.completed_at.isoformat() if cancelled_scan.completed_at else None
    }


@router.post("/{project_id}/intelligence-scan/cancel")
async def cancel_latest_intelligence_scan(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels the latest running Central Local SEO Intelligence Scan for the project.
    """
    project = await verify_project_access(project_id, current_user, db)

    stmt = (
        select(ProjectIntelligenceScan)
        .where(
            ProjectIntelligenceScan.project_id == project_id,
            ProjectIntelligenceScan.status.in_([ScanStatus.QUEUED.value, ScanStatus.RUNNING.value])
        )
        .order_by(ProjectIntelligenceScan.id.desc())
    )
    res = await db.execute(stmt)
    running_scan = res.scalars().first()

    if not running_scan:
        # Check latest scan even if already finished
        latest_res = await db.execute(
            select(ProjectIntelligenceScan)
            .where(ProjectIntelligenceScan.project_id == project_id)
            .order_by(ProjectIntelligenceScan.id.desc())
        )
        latest_scan = latest_res.scalars().first()
        if not latest_scan:
            raise HTTPException(status_code=404, detail="No intelligence scan found to cancel.")
        return {
            "scan_id": latest_scan.id,
            "project_id": latest_scan.project_id,
            "status": latest_scan.status,
            "progress_pct": latest_scan.progress_pct,
            "current_stage": latest_scan.current_stage,
            "current_stage_label": latest_scan.current_stage_label,
            "completed_stages_count": latest_scan.completed_stages_count,
            "total_stages_count": latest_scan.total_stages_count,
            "stages": latest_scan.stages,
            "results_summary": latest_scan.results_summary,
            "error_summary": latest_scan.error_summary,
            "started_at": latest_scan.started_at.isoformat() if latest_scan.started_at else None,
            "completed_at": latest_scan.completed_at.isoformat() if latest_scan.completed_at else None
        }

    cancelled_scan = await LocalIntelligenceScanService.cancel_scan(
        scan_id=running_scan.id,
        project_id=project_id,
        db=db
    )

    log_user_action(
        request, "CANCEL_CENTRAL_INTELLIGENCE_SCAN",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        scan_id=cancelled_scan.id
    )

    return {
        "scan_id": cancelled_scan.id,
        "project_id": cancelled_scan.project_id,
        "status": cancelled_scan.status,
        "progress_pct": cancelled_scan.progress_pct,
        "current_stage": cancelled_scan.current_stage,
        "current_stage_label": cancelled_scan.current_stage_label,
        "completed_stages_count": cancelled_scan.completed_stages_count,
        "total_stages_count": cancelled_scan.total_stages_count,
        "stages": cancelled_scan.stages,
        "results_summary": cancelled_scan.results_summary,
        "error_summary": cancelled_scan.error_summary,
        "started_at": cancelled_scan.started_at.isoformat() if cancelled_scan.started_at else None,
        "completed_at": cancelled_scan.completed_at.isoformat() if cancelled_scan.completed_at else None
    }


@router.get("/{project_id}/intelligence-scan/history")
@router.get("/{project_id}/full-scan/history")
async def get_intelligence_scan_history(
    project_id: int,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns scan history for the central full scan orchestrator for the selected project.
    """
    await verify_project_access(project_id, current_user, db)

    stmt = (
        select(ProjectIntelligenceScan)
        .where(ProjectIntelligenceScan.project_id == project_id)
        .order_by(ProjectIntelligenceScan.id.desc())
        .limit(min(limit, 50))
    )
    res = await db.execute(stmt)
    scans = res.scalars().all()

    return [
        {
            "scan_id": s.id,
            "project_id": s.project_id,
            "status": s.status,
            "progress_pct": s.progress_pct,
            "current_stage": s.current_stage,
            "current_stage_label": s.current_stage_label,
            "completed_stages_count": s.completed_stages_count,
            "total_stages_count": s.total_stages_count,
            "stages": s.stages,
            "results_summary": s.results_summary,
            "error_summary": s.error_summary,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None
        }
        for s in scans
    ]


# ─── Full Scan Route Aliases for API Contract Compliance ───

@router.post("/{project_id}/full-scan")
async def trigger_full_scan_alias(
    request: Request,
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await trigger_intelligence_scan(
        request=request,
        project_id=project_id,
        background_tasks=background_tasks,
        current_user=current_user,
        db=db
    )


@router.get("/{project_id}/full-scan/latest")
async def get_latest_full_scan_alias(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_latest_intelligence_scan(
        project_id=project_id,
        current_user=current_user,
        db=db
    )


@router.get("/{project_id}/full-scan/{scan_id}")
async def get_full_scan_status_alias(
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_intelligence_scan_status(
        project_id=project_id,
        scan_id=scan_id,
        current_user=current_user,
        db=db
    )


@router.post("/{project_id}/full-scan/{scan_id}/cancel")
async def cancel_full_scan_by_id_alias(
    request: Request,
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await cancel_intelligence_scan_by_id(
        request=request,
        project_id=project_id,
        scan_id=scan_id,
        current_user=current_user,
        db=db
    )


@router.post("/{project_id}/full-scan/cancel")
async def cancel_latest_full_scan_alias(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await cancel_latest_intelligence_scan(
        request=request,
        project_id=project_id,
        current_user=current_user,
        db=db
    )


@router.get("/{project_id}/scan-allowance")
async def get_project_scan_allowance(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the organization's monthly LocalLift audit scan allowance status and SerpApi BYO status.
    """
    project = await verify_project_access(project_id, current_user, db)
    allowance = await ScanAllowanceService.get_or_create_allowance(db, project.organization_id)

    serp_res = await db.execute(
        select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == project.organization_id)
    )
    serp_config = serp_res.scalars().first()
    has_byo_serp = bool(serp_config and serp_config.encrypted_api_key)

    return {
        "organization_id": project.organization_id,
        "year_month": allowance.year_month,
        "used_scans": allowance.used_scans,
        "allowed_scans": allowance.allowed_scans,
        "remaining_scans": max(0, allowance.allowed_scans - allowance.used_scans),
        "is_byo_serp": has_byo_serp,
        "last_scan_at": allowance.last_scan_at.isoformat() if allowance.last_scan_at else None
    }


