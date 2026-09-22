"""
LocalLift — 20-Category Local SEO Audit API Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.audit import LocalAuditRun, LocalAuditFinding
from app.schemas.audit import LocalAuditRunOut, LocalAuditRunCreate
from app.services.local_seo.audit_framework import LocalSEOAuditFramework

router = APIRouter(prefix="/audits", tags=["Local SEO Audits"])


@router.post("/{project_id}/local/run", response_model=LocalAuditRunOut)
async def trigger_local_seo_audit(
    project_id: int,
    audit_in: Optional[LocalAuditRunCreate] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a comprehensive 20-category Local SEO audit run.
    Evaluates evidence, generates traceable findings with provenance, and computes category scores.
    """
    await verify_project_access(project_id, current_user, db)
    framework_version = audit_in.framework_version if audit_in else "local_seo_v1"
    run = await LocalSEOAuditFramework.run_audit(project_id, db, framework_version)
    
    # Reload with findings
    stmt = (
        select(LocalAuditRun)
        .options(selectinload(LocalAuditRun.findings))
        .where(LocalAuditRun.id == run.id)
    )
    res = await db.execute(stmt)
    return res.scalars().first()


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
