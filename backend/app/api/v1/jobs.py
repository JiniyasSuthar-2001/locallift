"""
Jobs and Provider Usage API endpoints for LocalLift.
Provides asynchronous scan job lifecycle management, cancellation,
global task monitoring, and project-isolated provider usage tracking.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update

from app.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.ranking import GeoGridScan
from app.models.intelligence_scan import ProjectIntelligenceScan
from app.services.serp.ranking_job_service import KeywordRankingJobService
from app.services.provider_usage_service import ProviderUsageService

logger = logging.getLogger("locallift.api.jobs")

router = APIRouter(prefix="/projects", tags=["Scan Jobs & Provider Usage"])


@router.post("/{project_id}/keywords/start-scan")
async def start_keyword_scan(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start an asynchronous Keyword Rank Tracker scan job for 30-40+ keywords.
    Returns immediately with job_id and QUEUED/RUNNING status.
    The scan runs in the background with bounded concurrency and cooperative cancellation.
    """
    project = await verify_project_access(project_id, current_user, db)

    # Trigger job creation
    job = await KeywordRankingJobService.create_and_run_job(
        db=db,
        project_id=project.id,
        user_id=current_user.id
    )

    return {
        "job_id": job.id,
        "project_id": job.project_id,
        "organization_id": job.organization_id,
        "job_type": job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type),
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "current_stage": job.current_stage,
        "message": f"Keyword scan job created for {job.total_items} keywords"
    }


@router.get("/{project_id}/jobs")
async def list_project_jobs(
    project_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    job_type_filter: Optional[str] = Query(None, alias="job_type"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List scan jobs strictly for the specified project and organization.
    """
    project = await verify_project_access(project_id, current_user, db)

    query = select(ScanJob).where(
        ScanJob.project_id == project.id,
        ScanJob.organization_id == project.organization_id
    )

    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
            query = query.where(ScanJob.status == status_enum)
        except ValueError:
            pass

    if job_type_filter:
        try:
            type_enum = JobType(job_type_filter)
            query = query.where(ScanJob.job_type == type_enum)
        except ValueError:
            pass

    query = query.order_by(ScanJob.created_at.desc()).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        {
            "id": j.id,
            "organization_id": j.organization_id,
            "project_id": j.project_id,
            "job_type": j.job_type.value if hasattr(j.job_type, "value") else str(j.job_type),
            "status": j.status.value if hasattr(j.status, "value") else str(j.status),
            "total_items": j.total_items,
            "processed_items": j.processed_items,
            "successful_items": j.successful_items,
            "failed_items": j.failed_items,
            "not_found_items": j.not_found_items,
            "token_usage": j.token_usage,
            "point_usage": j.point_usage,
            "error_count": j.error_count,
            "current_stage": j.current_stage,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "cancelled_at": j.cancelled_at.isoformat() if j.cancelled_at else None,
            "expires_at": j.expires_at.isoformat() if j.expires_at else None,
            "summary_data": j.summary_data or {}
        }
        for j in jobs
    ]


@router.get("/{project_id}/jobs/{job_id}")
async def get_job_status(
    project_id: int,
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed status of a specific scan job.
    Strictly validates that job belongs to project_id and user's organization.
    """
    project = await verify_project_access(project_id, current_user, db)

    job = await db.get(ScanJob, job_id)
    if not job or job.project_id != project.id or job.organization_id != project.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found for project {project_id}"
        )

    # Check expiration dynamically
    if job.status in (JobStatus.QUEUED, JobStatus.RUNNING) and job.expires_at:
        now_utc = datetime.now(timezone.utc)
        job_exp = job.expires_at if job.expires_at.tzinfo else job.expires_at.replace(tzinfo=timezone.utc)
        if now_utc > job_exp:
            job.status = JobStatus.EXPIRED
            job.completed_at = now_utc
            job.error_details = "Job exceeded maximum execution limit of 300 seconds."
            await db.commit()
            await db.refresh(job)

    return {
        "id": job.id,
        "organization_id": job.organization_id,
        "project_id": job.project_id,
        "job_type": job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type),
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "successful_items": job.successful_items,
        "failed_items": job.failed_items,
        "not_found_items": job.not_found_items,
        "token_usage": job.token_usage,
        "point_usage": job.point_usage,
        "error_count": job.error_count,
        "current_stage": job.current_stage,
        "error_details": job.error_details,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "cancelled_at": job.cancelled_at.isoformat() if job.cancelled_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "summary_data": job.summary_data or {}
    }


@router.post("/{project_id}/jobs/{job_id}/cancel")
async def cancel_job(
    project_id: int,
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running or queued job.
    Stops further provider API calls and releases resources immediately.
    """
    project = await verify_project_access(project_id, current_user, db)

    job = await KeywordRankingJobService.request_cancellation(
        db=db,
        job_id=job_id,
        project_id=project.id
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or not active for project {project_id}"
        )

    return {
        "id": job.id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "message": f"Cancellation requested for job {job_id}. In-flight provider requests stopping."
    }


@router.post("/{project_id}/cancel-active-scans")
async def cancel_all_active_scans(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Hard Project Isolation:
    When switching projects or on demand, cancels ALL active background operations
    for the project (keyword scans, geo-grid scans, intelligence audits).
    Ensures zero further provider tokens/points are consumed.
    """
    project = await verify_project_access(project_id, current_user, db)
    now_utc = datetime.now(timezone.utc)
    cancelled_count = 0

    # 1. Cancel ScanJob records
    jobs_stmt = select(ScanJob).where(
        ScanJob.project_id == project.id,
        ScanJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
    )
    result = await db.execute(jobs_stmt)
    active_jobs = result.scalars().all()
    for job in active_jobs:
        job.status = JobStatus.CANCELLED
        job.cancelled_at = now_utc
        cancelled_count += 1

    # 2. Cancel GeoGridScan records
    grid_stmt = select(GeoGridScan).where(
        GeoGridScan.project_id == project.id,
        GeoGridScan.status.in_(["queued", "running", "in_progress"])
    )
    grid_result = await db.execute(grid_stmt)
    active_grids = grid_result.scalars().all()
    for g in active_grids:
        g.status = "cancelled"
        cancelled_count += 1

    # 3. Cancel ProjectIntelligenceScan records if any
    try:
        intel_stmt = select(ProjectIntelligenceScan).where(
            ProjectIntelligenceScan.project_id == project.id,
            ProjectIntelligenceScan.status.in_(["QUEUED", "RUNNING", "PARTIAL"])
        )
        intel_result = await db.execute(intel_stmt)
        active_intels = intel_result.scalars().all()
        for i in active_intels:
            i.status = "CANCELLED"
            cancelled_count += 1
    except Exception as e:
        logger.warning(f"Could not cancel intelligence scans for project {project.id}: {e}")

    await db.commit()
    logger.info(f"[Hard Project Isolation] Cancelled {cancelled_count} active operations for project {project.id}")

    return {
        "success": True,
        "project_id": project.id,
        "cancelled_count": cancelled_count,
        "message": f"Successfully cancelled {cancelled_count} active operations for project {project.name}"
    }


@router.get("/{project_id}/provider-usage")
async def get_project_provider_usage(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get provider token/point consumption summary for the active project
    separated into periods: today, 7d, 30d, all_time, plus live provider status & quotas.
    """
    project = await verify_project_access(project_id, current_user, db)

    usage_summary = await ProviderUsageService.get_project_usage_summary(
        db=db,
        project_id=project.id,
        organization_id=project.organization_id
    )

    provider_status = await ProviderUsageService.get_provider_status_and_forecast(
        db=db,
        project_id=project.id,
        organization_id=project.organization_id
    )

    return {
        "project_id": project.id,
        "organization_id": project.organization_id,
        "usage": usage_summary,
        "providers": provider_status
    }
