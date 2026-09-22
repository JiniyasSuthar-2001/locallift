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
