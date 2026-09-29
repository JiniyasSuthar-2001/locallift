"""
LocalLift — 20-Category Local SEO Audit API Endpoints
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, status
import logging
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project
from app.models.audit import LocalAuditRun, LocalAuditFinding, AuditJob, AuditJobStatus
from app.schemas.audit import LocalAuditRunOut, LocalAuditRunCreate
from app.services.local_seo.audit_framework import LocalSEOAuditFramework

logger = logging.getLogger("locallift.local_audits")

router = APIRouter(prefix="/audits", tags=["Local SEO Audits"])


async def _execute_technical_scan_job(job_id: int, project_id: int, start_url: str, crawl_options: dict):
    from app.api.v1.audits import run_crawler_and_audit_task
    # 1. Run crawler task which updates AuditJob status, crawls pages, and saves SEOAudit
    await run_crawler_and_audit_task(
        job_id=job_id,
        project_id=project_id,
        start_url=start_url,
        crawl_options=crawl_options
    )
    # 2. Update LocalSEOAuditFramework using the newly created crawl snapshot
    try:
        async with AsyncSessionLocal() as sess:
            await LocalSEOAuditFramework.run_audit(
                project_id=project_id,
                db=sess,
                framework_version="local_seo_v1",
                freshness_hours=168,
                force_crawl=False,
                crawl_snapshot_id=job_id
            )
            logger.info(f"[TECHNICAL_SCAN] Successfully refreshed LocalSEOAuditFramework for Project #{project_id} using crawl #{job_id}")
    except Exception as e:
        logger.error(f"[TECHNICAL_SCAN] Failed to update LocalSEOAuditFramework after crawl: {e}", exc_info=e)


@router.post("/{project_id}/local/run", response_model=LocalAuditRunOut)
async def trigger_local_seo_audit(
    project_id: int,
    audit_in: Optional[LocalAuditRunCreate] = None,
    force_crawl: bool = Query(False, description="Force a fresh technical website crawl"),
    freshness_hours: int = Query(24, ge=1, le=168, description="Maximum crawl age in hours before triggering a refresh"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a comprehensive 20-category Local SEO audit run.
    Evaluates evidence, verifies technical website health, generates traceable findings with provenance, and computes category scores.
    """
    await verify_project_access(project_id, current_user, db)
    framework_version = audit_in.framework_version if audit_in else "local_seo_v1"
    run = await LocalSEOAuditFramework.run_audit(
        project_id=project_id,
        db=db,
        framework_version=framework_version,
        freshness_hours=freshness_hours,
        force_crawl=force_crawl
    )
    
    # Reload with findings
    stmt = (
        select(LocalAuditRun)
        .options(selectinload(LocalAuditRun.findings))
        .where(LocalAuditRun.id == run.id)
    )
    res = await db.execute(stmt)
    return res.scalars().first()


@router.post("/{project_id}/local/technical-scan")
async def trigger_technical_seo_scan(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes an on-demand fresh technical website crawl job and updates Category 15 findings and scores in the background.
    Returns the created AuditJob id immediately for real-time polling.
    """
    proj = await verify_project_access(project_id, current_user, db)
    domain_clean = (proj.domain or "").strip()
    if not domain_clean or domain_clean.lower() in ("example.com", "https://example.com", "http://example.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project website domain is not configured. Please configure a domain before initiating a technical SEO crawl."
        )
    start_url = f"https://{domain_clean}" if not domain_clean.startswith("http") else domain_clean
    crawl_opts = {
        "url": start_url,
        "max_pages": 25,
        "respect_robots": True,
        "crawl_delay_ms": 150,
        "follow_redirects": True,
        "allow_local_dev": False,
        "max_depth": 3,
        "check_external_links": True,
        "max_external_links": 30
    }

    job = AuditJob(
        project_id=project_id,
        organization_id=proj.organization_id,
        job_type="technical_scan",
        status=AuditJobStatus.QUEUED,
        crawler_status="queued",
        progress=0.0,
        current_stage="Technical SEO crawl job queued for execution",
        start_url=start_url,
        options_snapshot=crawl_opts
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _execute_technical_scan_job,
        job_id=job.id,
        project_id=project_id,
        start_url=start_url,
        crawl_options=crawl_opts
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Technical SEO website crawl job queued",
        "created_at": job.created_at.isoformat() if job.created_at else None
    }


@router.get("/{project_id}/local/latest", response_model=Optional[LocalAuditRunOut])
async def get_latest_local_seo_audit(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the latest Local SEO audit run and findings for an authorized project.
    """
    await verify_project_access(project_id, current_user, db)
    stmt = (
        select(LocalAuditRun)
        .options(selectinload(LocalAuditRun.findings))
        .where(LocalAuditRun.project_id == project_id)
        .order_by(LocalAuditRun.id.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().first()


@router.get("/{project_id}/local/history", response_model=List[LocalAuditRunOut])
async def get_local_seo_audit_history(
    project_id: int,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns historical Local SEO audit runs for the project.
    """
    await verify_project_access(project_id, current_user, db)
    stmt = (
        select(LocalAuditRun)
        .options(selectinload(LocalAuditRun.findings))
        .where(LocalAuditRun.project_id == project_id)
        .order_by(LocalAuditRun.id.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{project_id}/local/runs/{run_id}", response_model=LocalAuditRunOut)
async def get_local_seo_audit_run(
    project_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves a specific Local SEO audit run by ID.
    """
    await verify_project_access(project_id, current_user, db)
    stmt = (
        select(LocalAuditRun)
        .options(selectinload(LocalAuditRun.findings))
        .where(LocalAuditRun.id == run_id, LocalAuditRun.project_id == project_id)
    )
    res = await db.execute(stmt)
    run = res.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Local SEO audit run not found.")
    return run
