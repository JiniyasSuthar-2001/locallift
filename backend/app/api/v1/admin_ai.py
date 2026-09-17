from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_active_superuser
from app.models.user import User, Organization
from app.models.ai_control import OrganizationAIConfig
from app.services.ai_consumption_service import AIConsumptionService

router = APIRouter(prefix="/admin/ai", tags=["Master AI Controls"])

class GlobalAIConfigUpdate(BaseModel):
    global_ai_enabled: bool

class OrgAIConfigUpdate(BaseModel):
    ai_enabled: Optional[bool] = None
    ai_daily_limit: Optional[int] = Field(None, ge=0)
    ai_monthly_limit: Optional[int] = Field(None, ge=0)
    ai_per_request_limit: Optional[int] = Field(None, ge=0)
    ai_credits_balance: Optional[float] = Field(None, ge=0.0)

@router.get("/config")
async def get_global_ai_config(
    admin_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves global AI kill switch status."""
    global_enabled = await AIConsumptionService.get_global_ai_enabled(db)
    return {"global_ai_enabled": global_enabled}

@router.put("/config")
async def update_global_ai_config(
    body: GlobalAIConfigUpdate,
    admin_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Updates global AI kill switch status."""
    await AIConsumptionService.set_global_ai_enabled(db, body.global_ai_enabled)
    return {
        "message": f"Global AI has been {'enabled' if body.global_ai_enabled else 'disabled'}.",
        "global_ai_enabled": body.global_ai_enabled
    }

@router.get("/organizations/{org_id}")
async def get_org_ai_config(
    org_id: int,
    admin_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves detailed AI configuration and credit status for an organization."""
    org_res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    status_data = await AIConsumptionService.get_usage_status(db, org_id)
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        **status_data
    }

@router.put("/organizations/{org_id}")
async def update_org_ai_config(
    org_id: int,
    body: OrgAIConfigUpdate,
    admin_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Updates AI access toggles, usage limits, and credit balances for an organization."""
    org_res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    config = await AIConsumptionService.get_or_create_org_config(db, org_id)

    if body.ai_enabled is not None:
        config.ai_enabled = body.ai_enabled
    if body.ai_daily_limit is not None:
        config.ai_daily_limit = body.ai_daily_limit
    if body.ai_monthly_limit is not None:
        config.ai_monthly_limit = body.ai_monthly_limit
    if body.ai_per_request_limit is not None:
        config.ai_per_request_limit = body.ai_per_request_limit
    if body.ai_credits_balance is not None:
        config.ai_credits_balance = body.ai_credits_balance

    await db.commit()
    await db.refresh(config)

    status_data = await AIConsumptionService.get_usage_status(db, org_id)
    return {
        "message": f"AI controls updated for organization '{org.name}'",
        "organization_id": org.id,
        **status_data
    }
