"""
LocalLift — Canonical Business Profile API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.schemas.local_seo import BusinessProfileOut, BusinessProfileUpdate
from app.services.local_seo.business_profile_service import BusinessProfileService

router = APIRouter(prefix="/projects", tags=["Business Profile"])


@router.get("/{project_id}/business-profile", response_model=BusinessProfileOut)
async def get_project_business_profile(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the canonical business profile for an authorized project.
    """
    await verify_project_access(project_id, current_user, db)
    profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)
    return profile


@router.put("/{project_id}/business-profile", response_model=BusinessProfileOut)
async def update_project_business_profile(
    project_id: int,
    profile_in: BusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the canonical business profile and synchronizes identity fields
    across locations and project records.
    """
    await verify_project_access(project_id, current_user, db)
    updated = await BusinessProfileService.update_canonical_profile(project_id, profile_in, db)
    return updated


@router.get("/{project_id}/business-profile/integrity")
async def get_business_profile_integrity(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validates completeness of core identity attributes for Local SEO and Geo-Grid scanning.
    """
    await verify_project_access(project_id, current_user, db)
    profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)
    return BusinessProfileService.verify_profile_integrity(profile)
