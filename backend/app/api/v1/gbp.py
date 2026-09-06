from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.gbp import GoogleBusinessProfile, GoogleAccount, GBPChange
from app.schemas.gbp import GBPProfileOut, GBPChangeOut

router = APIRouter(prefix="/gbp", tags=["Google Business Profile"])

@router.get("/{project_id}", response_model=Optional[GBPProfileOut])
async def get_gbp_profile(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find GoogleAccount for project
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
    if not account:
        return None

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
    )
    return prof_res.scalars().first()

@router.get("/{project_id}/changes", response_model=List[GBPChangeOut])
async def get_gbp_changes(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
    if not account:
        return []

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
    )
    profile = prof_res.scalars().first()
    if not profile:
        return []

    changes_res = await db.execute(
        select(GBPChange).where(GBPChange.gbp_profile_id == profile.id).order_by(GBPChange.detected_at.desc())
    )
    return changes_res.scalars().all()

@router.post("/{project_id}/sync")
async def sync_gbp_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
    if not account:
        raise HTTPException(status_code=400, detail="Google Account not connected for this project")

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
    )
    profile = prof_res.scalars().first()
    if profile:
        profile.last_synced_at = datetime.now(timezone.utc)
        await db.commit()

    return {"message": "Google Business Profile synced successfully", "status": "synced"}
