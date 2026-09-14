import json
import logging
import urllib.parse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.config import settings
from app.core.deps import get_current_user, verify_project_access, get_user_organization_ids
from app.core.audit_logger import log_user_action
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
    SingleServiceStatus,
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
from app.services.google import GoogleOAuthCore, GoogleOAuthService
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.public_maps_service import PublicGoogleMapsService

logger = logging.getLogger("locallift.connections")

router = APIRouter(prefix="/connections", tags=["Connections & Integrations"])
integrations_router = APIRouter(prefix="/integrations", tags=["Google Integrations"])

SERVICE_KEY_MAP = {
    "business-profile": "business_profile",
    "business_profile": "business_profile",
    "ads": "google_ads",
    "google-ads": "google_ads",
    "google_ads": "google_ads",
    "search-console": "search_console",
    "search_console": "search_console",
    "analytics": "analytics"
}


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


def normalize_service_key(raw_service: str) -> str:
    key = SERVICE_KEY_MAP.get(raw_service.lower().strip())
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Google service '{raw_service}'. Must be one of: business-profile, ads, search-console, analytics."
        )
    return key


@router.get("/status", response_model=GoogleConnectionStatusOut)
@integrations_router.get("/google/status", response_model=GoogleConnectionStatusOut)
async def get_connections_status(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns structured connection status for each independent Google service:
    - business_profile
    - google_ads
    - search_console
    - analytics
    Never exposes credentials or access/refresh tokens.
    """
    org_id = await get_active_org_id(current_user, db, project_id)
    services_summary = await GoogleConnectionsService.get_services_status_summary(org_id, db)

    bp_status = SingleServiceStatus(**services_summary["business_profile"])
    ads_status = SingleServiceStatus(**services_summary["google_ads"])
    gsc_status = SingleServiceStatus(**services_summary["search_console"])
    ga4_status = SingleServiceStatus(**services_summary["analytics"])

    # Fetch discovered resources across all connections for backward compatibility
    conn_map = await GoogleConnectionsService.get_all_connections_for_org(org_id, db)
    ads_list = []
    gsc_list = []
    ga_list = []
    any_connected = False
    first_email = None

    for s_name, conn in conn_map.items():
        if conn and conn.status == "connected":
            any_connected = True
            if not first_email and conn.account_email:
                first_email = conn.account_email
            if conn.ads_accounts:
                ads_list.extend([GoogleAdsAccountOut.model_validate(a) for a in conn.ads_accounts])
            if conn.search_console_properties:
                gsc_list.extend([GoogleSearchConsolePropertyOut.model_validate(g) for g in conn.search_console_properties])
            if conn.analytics_properties:
                ga_list.extend([GoogleAnalyticsPropertyOut.model_validate(ga) for ga in conn.analytics_properties])

    logger.info(f"[UI] settings.google.service_status.updated org_id={org_id}")

    return GoogleConnectionStatusOut(
        business_profile=bp_status,
        google_ads=ads_status,
        search_console=gsc_status,
        analytics=ga4_status,
        is_connected=any_connected,
        account_email=first_email,
        status="connected" if any_connected else "disconnected",
        gbp_locations_count=bp_status.resource_count,
        ads_accounts_count=len(ads_list),
        search_console_properties_count=len(gsc_list),
        analytics_properties_count=len(ga_list),
        ads_accounts=ads_list,
        search_console_properties=gsc_list,
        analytics_properties=ga_list,
        discovered_gbp_locations=[]
    )


@router.get("/google/{raw_service}/auth-url")
@router.get("/google/auth-url")
@integrations_router.get("/google/{raw_service}/authorize")
async def get_service_google_auth_url(
    request: Request,
    raw_service: Optional[str] = None,
    service: Optional[str] = Query(None),
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates service-specific Google OAuth 2.0 authorization URL.
    Requests ONLY scopes required for the specified Google service.
    """
    req_id = getattr(request.state, "request_id", "unknown")
    target_service_str = raw_service or service or "business_profile"
    service_key = normalize_service_key(target_service_str)
    org_id = await get_active_org_id(current_user, db, project_id)

    log_user_action(
        request, f"settings.google.{service_key}.connect_clicked",
        user_id=current_user.id,
        organization_id=org_id,
        project_id=project_id
    )
    logger.info(f"[USER_ACTION] settings.google.{service_key}.connect_clicked user_id={current_user.id} org_id={org_id}")
    logger.info(f"[OAUTH] service={service_key} stage=authorization_started user_id={current_user.id} org_id={org_id}")

    if not GoogleOAuthCore.is_configured():
        return {
            "configured": False,
            "auth_url": None,
            "service": service_key,
            "message": "Google OAuth is not configured in settings. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        }

    auth_url = GoogleOAuthCore.get_authorization_url(
        service=service_key,
        project_id=project_id or 0,
        user_id=current_user.id,
        organization_id=org_id
    )

    logger.info(f"[OAUTH][request_id={req_id}] service={service_key} stage=authorization_url_created user_id={current_user.id}")

    return {
        "configured": True,
        "service": service_key,
        "auth_url": auth_url,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI
    }


@router.get("/google/callback")
@router.get("/google/{raw_service}/callback")
@integrations_router.get("/google/{raw_service}/callback")
async def handle_google_browser_callback(
    request: Request,
    raw_service: Optional[str] = None,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Browser GET Callback endpoint hit directly by Google OAuth redirect.
    Validates state JWT, identifies target service, exchanges code for tokens,
    persists credentials strictly for that service, and redirects browser back to Settings.
    """
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[OAUTH] stage=callback_received code_present={bool(code)} state_present={bool(state)} error={error}")

    frontend_redirect_base = f"{settings.FRONTEND_BASE_URL}/connections"

    if error:
        err_msg = error_description or error or "Google authorization was cancelled or denied."
        logger.warning(f"[OAUTH] stage=callback_error message='{err_msg}'")
        safe_msg = urllib.parse.quote(err_msg[:200])
        return RedirectResponse(url=f"{frontend_redirect_base}?google=error&message={safe_msg}", status_code=302)

    if not code or not state:
        logger.error(f"[OAUTH] stage=callback_error reason=missing_code_or_state")
        return RedirectResponse(url=f"{frontend_redirect_base}?google=error&message=Missing+authorization+code+or+state", status_code=302)

    # 1. Decode & validate signed OAuth state JWT
    expected_service_key = SERVICE_KEY_MAP.get(raw_service.lower().strip()) if raw_service else None
    try:
        state_data = GoogleOAuthCore.decode_and_validate_oauth_state(state, expected_service=expected_service_key)
        target_service = state_data.get("service", "business_profile")
        logger.info(f"[OAUTH] service={target_service} stage=state_validated user_id={state_data.get('user_id')} org_id={state_data.get('organization_id')}")
    except ValueError as ve:
        logger.error(f"[OAUTH] stage=callback_error reason=state_validation_failed error='{ve}'")
        safe_err = urllib.parse.quote(f"State validation failed: {str(ve)}")
        return RedirectResponse(url=f"{frontend_redirect_base}?google=error&message={safe_err}", status_code=302)

    target_user_id = state_data.get("user_id")
    target_org_id = state_data.get("organization_id")
    target_project_id = state_data.get("project_id")

    if not target_user_id or not target_org_id:
        logger.error(f"[OAUTH] service={target_service} stage=callback_error reason=invalid_state_payload")
        return RedirectResponse(url=f"{frontend_redirect_base}?google=error&message=Invalid+OAuth+state+context", status_code=302)

    # 2. Verify target user exists and is active
    user_res = await db.execute(select(User).where(User.id == target_user_id, User.is_active == True))
    target_user = user_res.scalars().first()
    if not target_user:
        logger.error(f"[OAUTH] service={target_service} stage=callback_error reason=user_not_found user_id={target_user_id}")
        return RedirectResponse(url=f"{frontend_redirect_base}?google=error&message=User+account+not+found", status_code=302)

    # 3. Exchange code for tokens
    logger.info(f"[OAUTH] service={target_service} stage=token_exchange_started user_id={target_user_id}")
    try:
        token_data = await GoogleOAuthCore.exchange_code_for_tokens(code)
        logger.info(f"[OAUTH] service={target_service} stage=token_exchange_success user_id={target_user_id}")
    except Exception as e:
        logger.error(f"[OAUTH] service={target_service} stage=token_exchange_failed error='{e}'")
        safe_exc = urllib.parse.quote(f"Token exchange failed: {str(e)[:100]}")
        return RedirectResponse(url=f"{frontend_redirect_base}?google=error&message={safe_exc}", status_code=302)

    # 4. Save connection for specific service with token-at-rest encryption
    conn = await GoogleConnectionsService.save_connection_tokens(
        organization_id=target_org_id,
        user_id=target_user.id,
        service=target_service,
        token_data=token_data,
        db=db,
        project_id=target_project_id if (target_project_id and target_project_id > 0) else None
    )
    logger.info(f"[OAUTH] service={target_service} stage=connection_saved organization_id={target_org_id} email={conn.account_email}")

    # 5. Trigger background discovery for this service
    try:
        await GoogleConnectionsService.discover_and_sync_all_resources(conn, db)
    except Exception as disc_err:
        logger.warning(f"[OAUTH] service={target_service} Background discovery notice: {disc_err}")

    redirect_url = f"{frontend_redirect_base}?google_service={target_service}&status=success"
    logger.info(f"[OAUTH] service={target_service} stage=redirecting url='{redirect_url}'")
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/google/callback")
async def handle_google_post_callback(
    req: GoogleCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    API POST Callback endpoint for programmatically exchanging codes or unit testing.
    """
    if not req.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code from Google."
        )

    target_project_id = req.project_id
    target_org_id = None
    target_service = req.service or "business_profile"

    if req.state:
        try:
            state_data = GoogleOAuthCore.decode_and_validate_oauth_state(req.state)
            if state_data.get("user_id") and state_data["user_id"] != current_user.id and not current_user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="OAuth state mismatch: Initiated by a different user."
                )
            target_org_id = state_data.get("organization_id")
            target_service = state_data.get("service", target_service)
            if not target_project_id and state_data.get("project_id"):
                target_project_id = state_data.get("project_id")
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth state validation failed: {str(ve)}"
            )

    if target_project_id and target_project_id > 0:
        proj = await verify_project_access(target_project_id, current_user, db)
        org_id = proj.organization_id
    else:
        org_id = target_org_id or await get_active_org_id(current_user, db)

    token_data = await GoogleOAuthCore.exchange_code_for_tokens(req.code)

    conn = await GoogleConnectionsService.save_connection_tokens(
        organization_id=org_id,
        user_id=current_user.id,
        service=target_service,
        token_data=token_data,
        db=db,
        project_id=target_project_id if (target_project_id and target_project_id > 0) else None
    )

    discovery_res = await GoogleConnectionsService.discover_and_sync_all_resources(conn, db)

    return {
        "success": True,
        "service": target_service,
        "message": f"Google {target_service} connected successfully.",
        "account_email": conn.account_email,
        "discovery": discovery_res
    }


@router.post("/google/{raw_service}/disconnect")
@integrations_router.post("/google/{raw_service}/disconnect")
async def disconnect_specific_google_service(
    raw_service: str,
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely disconnects a specific Google service without affecting other service connections.
    """
    service_key = normalize_service_key(raw_service)
    org_id = await get_active_org_id(current_user, db, project_id)

    logger.info(f"[USER_ACTION] settings.google.{service_key}.disconnect_clicked user_id={current_user.id} org_id={org_id}")

    success = await GoogleConnectionsService.disconnect(
        organization_id=org_id,
        service=service_key,
        db=db
    )

    if not success:
        return {"success": False, "service": service_key, "message": f"No active connection found for service '{service_key}'."}

    logger.info(f"[UI] settings.google.service_status.updated org_id={org_id}")
    return {"success": True, "service": service_key, "message": f"Google {service_key} successfully disconnected."}


@router.post("/google/disconnect")
async def disconnect_google_legacy(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy disconnect endpoint. Defaults to disconnecting business_profile.
    """
    org_id = await get_active_org_id(current_user, db, project_id)
    success = await GoogleConnectionsService.disconnect(org_id, db, service="business_profile")

    if not success:
        return {"success": False, "message": "No active Google connection found."}

    return {"success": True, "message": "Google Business Profile connection successfully disconnected."}


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
    """
    org_id = await get_active_org_id(current_user, db, project_id)
    conn_map = await GoogleConnectionsService.get_all_connections_for_org(org_id, db)

    discovered_gbp = []
    discovered_ads = []
    discovered_gsc = []
    discovered_ga4 = []
    any_synced = False

    for s_key, conn in conn_map.items():
        if conn and conn.status == "connected":
            res = await GoogleConnectionsService.discover_and_sync_all_resources(conn, db)
            if "gbp_locations" in res:
                discovered_gbp.extend(res.get("gbp_locations", []))
            if "search_console" in res:
                discovered_gsc.extend([
                    {"site_url": s.get("site_url", ""), "permission_level": s.get("permission_level", "siteOwner")}
                    for s in res.get("search_console", [])
                ])
            if "ads_accounts" in res:
                discovered_ads.extend(res.get("ads_accounts", []))
            if "analytics_properties" in res:
                discovered_ga4.extend([
                    {"property_id": g.get("property_id", ""), "display_name": g.get("display_name", ""), "account_name": g.get("account_name", "")}
                    for g in res.get("analytics_properties", [])
                ])
            any_synced = True

    return {
        "connected": any_synced,
        "success": True,
        "gbp_locations": discovered_gbp,
        "ads_accounts": discovered_ads,
        "gsc_properties": discovered_gsc,
        "ga4_properties": discovered_ga4,
        "message": "Google resources synchronized successfully." if any_synced else "No active Google connections found to sync."
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
