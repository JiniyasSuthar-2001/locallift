import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.config import settings
from app.core.deps import get_current_user, verify_project_access, get_user_organization_ids
from app.models.user import User, OrganizationMember
from app.models.connections import (
    GoogleConnection,
    GoogleAdsAccount,
    GoogleSearchConsoleProperty,
    GoogleAnalyticsProperty,
    PublicBusinessListing
)
from app.schemas.connections import (
    GoogleConnectionStatusOut,
    GoogleAdsAccountOut,
    GoogleSearchConsolePropertyOut,
    GoogleAnalyticsPropertyOut,
    ImportResourcesRequest,
    ImportResourcesResponse,
    GoogleCallbackRequest,
    PublicMapsImportRequest,
    PublicBusinessListingOut,
    DiscoveredGBPLocation
)
from app.services.google import GoogleOAuthService
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.public_maps_service import PublicGoogleMapsService

logger = logging.getLogger("locallift.connections")

router = APIRouter(prefix="/connections", tags=["Connections & Integrations"])

async def get_active_org_id(user: User, db: AsyncSession, project_id: Optional[int] = None) -> int:
    """Resolves and validates the user's active organization."""
    if project_id:
        proj = await verify_project_access(project_id, user, db)
        return proj.organization_id

    mem_res = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    mem = mem_res.scalars().first()
    if not mem:
        raise HTTPException(status_code=400, detail="User has no associated organization.")
    return mem.organization_id

@router.get("/status", response_model=GoogleConnectionStatusOut)
async def get_connections_status(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the comprehensive connection status and discovered resource counts for the organization.
    Safe endpoint: never exposes access/refresh tokens.
    """
    if project_id:
        proj = await verify_project_access(project_id, current_user, db)
        org_id = proj.organization_id
    else:
        mem_res = await db.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
        )
        mem = mem_res.scalars().first()
        if not mem:
            return GoogleConnectionStatusOut(
                is_connected=False,
                status="disconnected",
                scopes=[],
                gbp_locations_count=0,
                ads_accounts_count=0,
                search_console_properties_count=0,
                analytics_properties_count=0
            )
        org_id = mem.organization_id

    conn = await GoogleConnectionsService.get_connection_for_org(org_id, db)


    if not conn or conn.status == "disconnected":
        return GoogleConnectionStatusOut(
            is_connected=False,
            status="disconnected",
            scopes=[],
            gbp_locations_count=0,
            ads_accounts_count=0,
            search_console_properties_count=0,
            analytics_properties_count=0
        )

    # Fetch discovered resources
    ads_list = [GoogleAdsAccountOut.model_validate(a) for a in (conn.ads_accounts or [])]
    gsc_list = [GoogleSearchConsolePropertyOut.model_validate(g) for g in (conn.search_console_properties or [])]
    ga_list = [GoogleAnalyticsPropertyOut.model_validate(ga) for ga in (conn.analytics_properties or [])]

    # Quick count of discovered GBP
    gbp_count = len(gsc_list)  # fallback or synced count

    return GoogleConnectionStatusOut(
        is_connected=True,
        account_email=conn.account_email,
        status=conn.status,
        scopes=conn.scopes or [],
        last_sync_at=conn.last_sync_at,
        sync_error=conn.sync_error,
        gbp_locations_count=gbp_count,
        ads_accounts_count=len(ads_list),
        search_console_properties_count=len(gsc_list),
        analytics_properties_count=len(ga_list),
        ads_accounts=ads_list,
        search_console_properties=gsc_list,
        analytics_properties=ga_list,
        discovered_gbp_locations=[]
    )

@router.get("/google/auth-url")
async def get_google_auth_url(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates the official Google OAuth 2.0 consent URL for connecting Google services.
    """
    org_id = await get_active_org_id(current_user, db, project_id)
    
    if not GoogleOAuthService.is_configured():
        return {
            "configured": False,
            "auth_url": None,
            "message": "Google OAuth is not configured in settings. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        }

    auth_url = GoogleOAuthService.get_authorization_url(
        project_id=project_id or 0,
        user_id=current_user.id,
        custom_state=json.dumps({"org_id": org_id, "user_id": current_user.id})
    )

    return {
        "configured": True,
        "auth_url": auth_url,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI
    }

@router.post("/google/callback")
@router.get("/google/callback")
async def handle_google_callback(
    req: Optional[GoogleCallbackRequest] = None,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Exchanges Google authorization code for tokens, securely persists the connection,
    and runs initial resource discovery. Supports both JSON POST body and URL Query params.
    """
    actual_code = (req.code if req and req.code else code)
    actual_state = (req.state if req and req.state else state)
    actual_project_id = (req.project_id if req and req.project_id is not None else project_id)

    if not actual_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code from Google."
        )

    org_id = await get_active_org_id(current_user, db, actual_project_id)

    try:
        token_data = await GoogleOAuthService.exchange_code_for_tokens(actual_code)
    except Exception as e:
        logger.error(f"Google OAuth token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google token exchange failed: {str(e)}"
        )

    # Save connection tokens securely
    conn = await GoogleConnectionsService.save_connection_tokens(
        organization_id=org_id,
        user_id=current_user.id,
        token_data=token_data,
        db=db,
        project_id=actual_project_id
    )

    # Run initial multi-service discovery
    discovery_res = await GoogleConnectionsService.discover_and_sync_all_resources(conn, db)

    return {
        "success": True,
        "message": "Google Account connected successfully.",
        "account_email": conn.account_email,
        "discovery": discovery_res
    }

@router.post("/google/discover")
@router.get("/google/discover")
@router.post("/google/sync")
async def discover_and_sync_google_resources(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs on-demand discovery and synchronization across all connected Google resources.
    Returns DiscoveredResourcesResponse matching frontend expectations.
    """
    org_id = await get_active_org_id(current_user, db, project_id)
    conn = await GoogleConnectionsService.get_connection_for_org(org_id, db)

    if not conn or conn.status == "disconnected":
        return {
            "connected": False,
            "success": False,
            "gbp_locations": [],
            "ads_accounts": [],
            "gsc_properties": [],
            "ga4_properties": [],
            "message": "No active Google connection found for this organization."
        }

    discovery_res = await GoogleConnectionsService.discover_and_sync_all_resources(conn, db)

    gsc_props = [
        {"site_url": s.get("site_url", ""), "permission_level": s.get("permission_level", "siteOwner")}
        for s in discovery_res.get("search_console", [])
    ]
    ga4_props = [
        {"property_id": g.get("property_id", ""), "display_name": g.get("display_name", ""), "account_name": g.get("account_name", "")}
        for g in discovery_res.get("analytics_properties", [])
    ]

    return {
        "connected": True,
        "success": True,
        "last_sync_at": conn.last_sync_at,
        "gbp_locations": discovery_res.get("gbp_locations", []),
        "ads_accounts": discovery_res.get("ads_accounts", []),
        "gsc_properties": gsc_props,
        "ga4_properties": ga4_props,
        "message": "Google resources discovered and synchronized successfully."
    }

@router.post("/google/import-resources", response_model=ImportResourcesResponse)
async def import_discovered_resources(
    req: ImportResourcesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-imports selected Google Business Profiles and Search Console websites into LocalLift records.
    """
    org_id = await get_active_org_id(current_user, db, req.project_id)

    res = await GoogleConnectionsService.import_resources_to_locallift(
        organization_id=org_id,
        selected_gbp=[loc.model_dump() for loc in (req.selected_gbp_locations or [])],
        selected_gsc_urls=req.selected_search_console_urls or [],
        db=db,
        target_project_id=req.project_id
    )

    return ImportResourcesResponse(**res)

@router.post("/google/disconnect")
async def disconnect_google(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely disconnects Google integration and clears credentials without deleting historical records.
    """
    org_id = await get_active_org_id(current_user, db, project_id)
    success = await GoogleConnectionsService.disconnect(org_id, db)

    if not success:
        return {"success": False, "message": "No active Google connection found."}

    return {"success": True, "message": "Google account successfully disconnected."}

@router.post("/public-maps/import", response_model=PublicBusinessListingOut)
async def import_public_maps_business(
    req: PublicMapsImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Imports a business via public Google Maps URL for 'Public Monitoring' mode.
    Disables owner-only operations while tracking public presence.
    """
    org_id = await get_active_org_id(current_user, db, req.project_id)
    url = req.get_url()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Maps URL is required."
        )

    try:
        listing = await PublicGoogleMapsService.import_public_business(
            organization_id=org_id,
            maps_url=url,
            db=db,
            project_id=req.project_id,
            target_category=req.get_category(),
            business_name=req.get_business_name()
        )
        return listing
    except Exception as e:
        logger.error(f"Failed to import public Maps business: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/public-maps", response_model=List[PublicBusinessListingOut])
async def list_public_monitored_businesses(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all public businesses being monitored for the organization.
    """
    org_id = await get_active_org_id(current_user, db, project_id)

    query = select(PublicBusinessListing).where(PublicBusinessListing.organization_id == org_id)
    if project_id:
        query = query.where(PublicBusinessListing.project_id == project_id)

    res = await db.execute(query.order_by(PublicBusinessListing.id.desc()))
    return res.scalars().all()
