import json
import uuid
import urllib.parse
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.config import settings
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project, Location
from app.models.connections import PublicBusinessListing
from app.models.gbp import GoogleBusinessProfile, GoogleAccount, GBPChange, GooglePostObservation, GoogleObservedChange
from app.schemas.gbp import (
    GBPProfileOut,
    GBPChangeOut,
    GBPOAuthURLResponse,
    GBPOAuthCallbackRequest,
    GBPStatusResponse,
    GBPSyncResponse,
    ProductOrServiceItemOut,
    ProductsServicesResponseOut,
    ProductCreate,
    ProductUpdate,
    ServiceCreate,
    ServiceUpdate,
    BulkProductsServicesImport
)
from app.services.google import GoogleOAuthService, GBPSyncService
from app.services.google.connections_service import GoogleConnectionsService

logger = logging.getLogger("locallift.gbp")

router = APIRouter(prefix="/gbp", tags=["Google Business Profile"])

async def _get_or_sync_google_account_for_project(project: Project, db: AsyncSession) -> Optional[GoogleAccount]:
    """
    Resolves the canonical Google connection state for a project.
    Does NOT manufacture fake email identities.
    """
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project.id))
    account = acc_res.scalars().first()
    if account and account.is_connected:
        return account

    gbp_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)
    if gbp_conn and gbp_conn.status in ("connected", "expired") and gbp_conn.access_token:
        if not account:
            account = GoogleAccount(
                project_id=project.id,
                account_email=gbp_conn.account_email,
                access_token=gbp_conn.access_token,
                refresh_token=gbp_conn.refresh_token,
                token_expiry=gbp_conn.token_expiry,
                scopes=gbp_conn.scopes or [],
                is_connected=True
            )
            db.add(account)
            await db.flush()
        else:
            account.account_email = gbp_conn.account_email or account.account_email
            account.access_token = gbp_conn.access_token
            account.refresh_token = gbp_conn.refresh_token or account.refresh_token
            account.token_expiry = gbp_conn.token_expiry
            account.is_connected = True
            await db.flush()

        await db.commit()
        await db.refresh(account)
        return account

    return None


def _calculate_public_completeness(listing: Optional[PublicBusinessListing]) -> Optional[int]:
    """
    Calculates actual completeness score based strictly on retrieved public Google Places fields.
    Returns None ("Not measured") if listing or essential fields are missing.
    Field weightings (Total = 100):
    - Name: 15
    - Formatted Address: 15
    - Phone: 15
    - Website: 15
    - Primary Category: 15
    - Business Status: 10
    - Rating: 10
    - Review Count: 5
    """
    if not listing or listing.lookup_status != "found":
        return None

    score = 0
    if listing.name: score += 15
    if listing.formatted_address: score += 15
    if listing.phone: score += 15
    if listing.website_url: score += 15
    if listing.category or listing.primary_category: score += 15
    if listing.business_status: score += 10
    if listing.rating is not None: score += 10
    if listing.review_count is not None: score += 5

    return score


class PublicPlaceLookupRequest(BaseModel):
    business_name: Optional[str] = None
    location: Optional[str] = None
    maps_url: Optional[str] = None


@router.get("/{project_id}/public-profile")
@router.get("/{project_id}/public-summary")
async def get_public_business_profile(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    System A: Returns public Google Place observation (retrieved via Google Places API).
    Does NOT require user GBP OAuth connection and does NOT use fake defaults.
    """
    project = await verify_project_access(project_id, current_user, db)

    stmt = select(PublicBusinessListing).where(
        PublicBusinessListing.organization_id == project.organization_id,
        PublicBusinessListing.project_id == project_id
    ).order_by(PublicBusinessListing.id.desc())
    res = await db.execute(stmt)
    listing = res.scalars().first()

    if not listing:
        return {
            "source": "google_places_api",
            "lookup_status": "idle",
            "lookup_error": None,
            "place_id": None,
            "business_name": None,
            "formatted_address": None,
            "address_components": None,
            "phone": None,
            "website_url": None,
            "category": None,
            "business_status": None,
            "rating": None,
            "review_count": None,
            "opening_hours": None,
            "latitude": None,
            "longitude": None,
            "maps_url": None,
            "checked_at": None,
            "completeness_score": None,
            "completeness_label": "Not measured"
        }

    comp_score = _calculate_public_completeness(listing)

    # Fetch real observed changes for project
    obs_stmt = select(GoogleObservedChange).where(
        GoogleObservedChange.project_id == project_id
    ).order_by(GoogleObservedChange.observed_at.desc()).limit(20)
    obs_res = await db.execute(obs_stmt)
    obs_changes = obs_res.scalars().all()

    # Fetch real post observations for project
    posts_stmt = select(GooglePostObservation).where(
        GooglePostObservation.project_id == project_id
    ).order_by(GooglePostObservation.observed_at.desc()).limit(20)
    posts_res = await db.execute(posts_stmt)
    posts_obs = posts_res.scalars().all()

    return {
        "source": listing.source or "google_places_api",
        "lookup_status": listing.lookup_status or "found",
        "lookup_error": listing.lookup_error,
        "place_id": listing.place_id,
        "business_name": listing.name,
        "formatted_address": listing.formatted_address,
        "address_components": listing.address_components,
        "phone": listing.phone,
        "website_url": listing.website_url,
        "category": listing.category or listing.primary_category,
        "business_status": listing.business_status,
        "rating": listing.rating,
        "review_count": listing.review_count,
        "opening_hours": listing.opening_hours,
        "latitude": listing.latitude,
        "longitude": listing.longitude,
        "maps_url": listing.maps_url,
        "checked_at": listing.last_checked_at.isoformat() if listing.last_checked_at else None,
        "completeness_score": comp_score,
        "completeness_label": f"{comp_score}% (Measured from retrieved Google Place fields)" if comp_score is not None else "Not measured",
        "observed_changes": [
            {
                "id": c.id,
                "field_name": c.field_name,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "observed_at": c.observed_at.isoformat() if c.observed_at else None,
                "source": c.source,
                "confidence": c.confidence
            } for c in obs_changes
        ],
        "post_observations": [
            {
                "id": p.id,
                "post_type": p.post_type,
                "content_summary": p.content_summary,
                "action_url": p.action_url,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "observed_at": p.observed_at.isoformat() if p.observed_at else None,
                "source": p.source
            } for p in posts_obs
        ]
    }


@router.post("/{project_id}/public-lookup")
async def trigger_public_place_lookup(
    project_id: int,
    req: PublicPlaceLookupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers Google Places API resolution by business name/location or Maps URL.
    Does NOT require GBP OAuth connection.
    """
    project = await verify_project_access(project_id, current_user, db)
    from app.services.google.public_maps_service import PublicGoogleMapsService

    res = await PublicGoogleMapsService.lookup_public_place(
        organization_id=project.organization_id,
        project_id=project.id,
        db=db,
        business_name=req.business_name,
        location_str=req.location,
        maps_url=req.maps_url,
        country=project.country
    )

    listing = res.get("listing")
    comp_score = _calculate_public_completeness(listing) if listing else None

    return {
        "lookup_status": res.get("lookup_status", "found" if listing else "not_found"),
        "lookup_error": res.get("lookup_error"),
        "requested_business_name": req.business_name,
        "requested_location": req.location,
        "requested_maps_url": req.maps_url,
        "source": listing.source if listing else "google_places_api",
        "place_id": listing.place_id if listing else None,
        "business_name": listing.name if listing else None,
        "formatted_address": listing.formatted_address if listing else None,
        "address_components": listing.address_components if listing else None,
        "phone": listing.phone if listing else None,
        "website_url": listing.website_url if listing else None,
        "category": (listing.category or listing.primary_category) if listing else None,
        "business_status": listing.business_status if listing else None,
        "rating": listing.rating if listing else None,
        "review_count": listing.review_count if listing else None,
        "opening_hours": listing.opening_hours if listing else None,
        "latitude": listing.latitude if listing else None,
        "longitude": listing.longitude if listing else None,
        "maps_url": listing.maps_url if listing else None,
        "checked_at": listing.last_checked_at.isoformat() if listing and listing.last_checked_at else None,
        "completeness_score": comp_score,
        "completeness_label": f"{comp_score}% (Measured from retrieved Google Place fields)" if comp_score is not None else "Not measured"
    }


@router.get("/{project_id}/owner-profile")
async def get_owner_gbp_profile(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    System B: Returns owner-authorized GBP information (requiring Google OAuth).
    Never manufactures fake identity emails or fake performance metrics.
    Strictly isolated per project.
    """
    project = await verify_project_access(project_id, current_user, db)

    # 1. First check direct project-bound GBP profile
    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()

    # 2. Check Org connection for email / connection status
    gbp_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)
    is_connected = bool(gbp_conn and gbp_conn.status in ("connected", "expired") and gbp_conn.access_token)
    account_email = gbp_conn.account_email if (is_connected and gbp_conn) else None

    if not profile or not profile.location_resource_name or not is_connected:
        # Fallback to legacy account check if present
        account = await _get_or_sync_google_account_for_project(project, db)
        if not account or not account.is_connected:
            return {
                "is_connected": False,
                "status": "disconnected",
                "account_email": None,
                "message": "Google Business Profile owner account not connected. Connect via OAuth to view owner-authorized metrics.",
                "profile": None
            }
        if not profile:
            prof_res = await db.execute(
                select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
            )
            profile = prof_res.scalars().first()
        account_email = account.account_email

    return {
        "is_connected": True,
        "status": profile.status if profile else "connected",
        "sync_status": profile.sync_status if profile else "idle",
        "account_email": account_email,
        "last_synced_at": profile.last_synced_at.isoformat() if profile and profile.last_synced_at else None,
        "provenance": "SYNCED_GOOGLE_DATA",
        "provenance_label": "SYNCED GOOGLE DATA",
        "profile": {
            "business_name": profile.business_name if profile else None,
            "primary_category": profile.primary_category if profile else None,
            "additional_categories": profile.additional_categories if (profile and profile.additional_categories) else [],
            "address": profile.address if profile else None,
            "city": profile.city if profile else None,
            "state": profile.state if profile else None,
            "postal_code": profile.postal_code if profile else None,
            "country": profile.country if profile else None,
            "phone": profile.phone if profile else None,
            "website_url": profile.website_url if profile else None,
            "latitude": profile.latitude if profile else None,
            "longitude": profile.longitude if profile else None,
            "regular_hours": profile.regular_hours if (profile and profile.regular_hours) else {},
            "special_hours": profile.special_hours if (profile and profile.special_hours) else [],
            "attributes": profile.attributes if (profile and profile.attributes) else {},
            "services": profile.services if (profile and profile.services) else [],
            "products": profile.products if (profile and profile.products) else [],
            "photos_count": profile.photos_count if profile else 0,
            "posts_count": profile.posts_count if profile else 0,
            "completeness_score": profile.completeness_score if profile else 0,
            "location_resource_name": profile.location_resource_name if profile else None,
            "account_resource_name": profile.account_resource_name if profile else None,
            "place_id": profile.place_id if profile else None,
            "maps_uri": profile.maps_uri if profile else None,
            "search_impressions": profile.search_impressions if profile else None,
            "maps_impressions": profile.maps_impressions if profile else None,
            "call_clicks": profile.call_clicks if profile else None,
            "website_clicks": profile.website_clicks if profile else None,
            "direction_requests": profile.direction_requests if profile else None,
            "is_verified": profile.is_verified if profile else False,
            "source_provenance": "GOOGLE_BUSINESS_PROFILE"
        } if profile else None
    }

@router.get("/{project_id}", response_model=Optional[GBPProfileOut])
async def get_gbp_profile(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the primary Google Business Profile for a project.
    Safe serialization: never exposes tokens or secrets.
    """
    project = await verify_project_access(project_id, current_user, db)
    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()
    if profile:
        return profile

    # Fallback to legacy google_account
    account = await _get_or_sync_google_account_for_project(project, db)
    if not account:
        return None

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
    )
    return prof_res.scalars().first()

@router.get("/{project_id}/status", response_model=GBPStatusResponse)
async def get_gbp_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Checks Google connection status and configuration availability for the project.
    """
    project = await verify_project_access(project_id, current_user, db)
    is_configured = GoogleOAuthService.is_configured()

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()

    gbp_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)
    if gbp_conn and gbp_conn.status == "connected" and profile:
        return GBPStatusResponse(
            is_connected=True,
            is_configured=is_configured,
            account_email=gbp_conn.account_email,
            last_synced_at=profile.last_synced_at,
            profiles_count=1,
            message="Connected to Google Business Profile."
        )

    account = await _get_or_sync_google_account_for_project(project, db)
    if not account or not account.is_connected:
        return GBPStatusResponse(
            is_connected=False,
            is_configured=is_configured,
            account_email=None,
            last_synced_at=None,
            profiles_count=0,
            message="Google Account not connected." if is_configured else "Google OAuth credentials not configured in settings."
        )

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
    )
    profiles = prof_res.scalars().all()
    last_synced = max([p.last_synced_at for p in profiles if p.last_synced_at], default=None)

    return GBPStatusResponse(
        is_connected=True,
        is_configured=is_configured,
        account_email=account.account_email,
        last_synced_at=last_synced,
        profiles_count=len(profiles),
        message="Connected to Google Business Profile."
    )

from app.core.security import encrypt_token, decrypt_token

@router.get("/{project_id}/auth-url", response_model=GBPOAuthURLResponse)
async def get_google_auth_url(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates the official Google OAuth 2.0 authorization URL with cryptographically signed state.
    """
    project = await verify_project_access(project_id, current_user, db)

    auth_url = GoogleOAuthService.get_authorization_url(
        project_id=project.id,
        user_id=current_user.id,
        organization_id=project.organization_id
    )

    return GBPOAuthURLResponse(
        auth_url=auth_url,
        is_configured=GoogleOAuthService.is_configured(),
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )

@router.post("/oauth/callback")
async def handle_google_oauth_callback(
    cb_req: GBPOAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Handles Google OAuth callback code exchange with cryptographic state verification and token encryption.
    """
    if not cb_req.code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Google")

    # 1. Cryptographically decode and validate state
    target_project_id = cb_req.project_id
    if cb_req.state:
        try:
            state_data = GoogleOAuthService.decode_and_validate_oauth_state(cb_req.state)
            if state_data.get("user_id") and state_data["user_id"] != current_user.id and not current_user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="OAuth state mismatch: Initiated by a different user."
                )
            if not target_project_id and state_data.get("project_id"):
                target_project_id = state_data.get("project_id")
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth state validation failed: {str(ve)}"
            )

    if not target_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project context cannot be securely established for OAuth connection."
        )

    # 2. Verify project access
    project = await verify_project_access(target_project_id, current_user, db)

    # 3. Exchange code for tokens
    try:
        token_info = await GoogleOAuthService.exchange_code_for_tokens(cb_req.code)
    except Exception as e:
        logger.error(f"Google OAuth token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {str(e)}")

    # 4. Retrieve user info / email
    email = await GoogleOAuthService.get_user_email(token_info["access_token"])

    # 5. Create or update GoogleAccount record with encrypted tokens
    enc_access_token = encrypt_token(token_info["access_token"])
    enc_refresh_token = encrypt_token(token_info.get("refresh_token"))

    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project.id))
    account = acc_res.scalars().first()

    if not account:
        account = GoogleAccount(
            project_id=project.id,
            account_email=email,
            access_token=enc_access_token,
            refresh_token=enc_refresh_token,
            token_expiry=token_info.get("token_expiry"),
            scopes=token_info.get("scope", []),
            is_connected=True
        )
        db.add(account)
    else:
        account.account_email = email
        account.access_token = enc_access_token
        if enc_refresh_token:
            account.refresh_token = enc_refresh_token
        account.token_expiry = token_info.get("token_expiry")
        account.scopes = token_info.get("scope", [])
        account.is_connected = True

    await db.commit()
    await db.refresh(account)

    # 5. Trigger initial background/live sync
    sync_result = {"status": "connected", "profiles_synced": 0, "changes_detected": 0}
    try:
        sync_result = await GBPSyncService.sync_project_gbp(project.id, db)
    except Exception as e:
        logger.warning(f"Initial GBP sync produced notice: {e}")

    return {
        "message": "Google Business Profile connected and synced successfully.",
        "status": "connected",
        "email": email,
        "sync_details": sync_result
    }

@router.get("/{project_id}/changes", response_model=List[GBPChangeOut])
async def get_gbp_changes(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the audit log of all changes detected on Google Business Profile.
    """
    await verify_project_access(project_id, current_user, db)

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()

    if not profile:
        acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
        account = acc_res.scalars().first()
        if account:
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

@router.post("/{project_id}/sync", response_model=GBPSyncResponse)
async def sync_gbp_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes live idempotent synchronization of GBP profile information and performance metrics
    strictly for the selected project's bound GBP location.
    """
    project = await verify_project_access(project_id, current_user, db)

    try:
        sync_res = await GBPSyncService.sync_project_gbp(project_id, db)
        if sync_res.get("status") == "not_connected":
            raise HTTPException(
                status_code=400,
                detail=sync_res.get("error", "Google Business Profile is not connected for this project.")
            )

        return GBPSyncResponse(
            message="Google Business Profile synced successfully.",
            status="synced",
            profiles_synced=sync_res.get("profiles_synced", 1),
            changes_detected=sync_res.get("changes_detected", 0),
            last_synced_at=sync_res.get("last_synced_at", datetime.now(timezone.utc))
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual GBP sync failed for project {project_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Google Business Profile sync failed: {str(e)[:150]}"
        )

@router.post("/{project_id}/disconnect")
async def disconnect_gbp(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnects the Google Business Profile integration for a project.
    """
    project = await verify_project_access(project_id, current_user, db)
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
    was_connected = False
    if account and account.is_connected:
        was_connected = True
        account.is_connected = False
        account.access_token = None
        account.refresh_token = None

    gbp_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)
    if gbp_conn and gbp_conn.status == "connected":
        was_connected = True
        gbp_conn.status = "disconnected"
        gbp_conn.access_token = None

    await db.commit()
    if not was_connected:
        return {"message": "No Google Business Profile connection was active.", "status": "not_connected"}
    return {"message": "Google Business Profile disconnected successfully.", "status": "disconnected"}

@router.get("/gsc/{project_id}")
async def get_gsc_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real Google Search Console metrics stored for the project, with explicit connection and sync states.
    Never reports fake metrics or false disconnected states.
    """
    proj = await verify_project_access(project_id, current_user, db)
    from app.models.connections import GoogleConnection, GoogleSearchConsoleProperty
    from app.models.analytics import GSCMetric
    from app.services.google.connections_service import GoogleConnectionsService

    # 1. Check if organization has active GSC connection
    gsc_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "search_console", db)
    is_connected = bool(gsc_conn and gsc_conn.status == "connected" and gsc_conn.access_token)
    conn_status = gsc_conn.status if gsc_conn else "not_connected"
    sync_error = gsc_conn.sync_error if gsc_conn else None

    # 2. Check for mapped Search Console property
    prop_res = await db.execute(
        select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.project_id == project_id)
    )
    mapped_prop = prop_res.scalars().first()

    # Auto-mapping fallback: if no property explicitly mapped, check if any org GSC property matches domain
    if not mapped_prop and gsc_conn:
        avail_props_res = await db.execute(
            select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.connection_id == gsc_conn.id)
        )
        for p in avail_props_res.scalars().all():
            clean_dom = proj.domain.lower().replace("www.", "")
            if clean_dom in p.site_url.lower():
                p.project_id = project_id
                mapped_prop = p
                await db.commit()
                break

    # 3. Fetch stored GSC metrics
    res = await db.execute(
        select(GSCMetric).where(GSCMetric.project_id == project_id).order_by(GSCMetric.date.desc())
    )
    metrics = res.scalars().all()

    # If connected, property mapped, but no metrics yet -> trigger initial sync automatically
    if is_connected and mapped_prop and not metrics:
        try:
            from app.services.google.gsc_client import GoogleSearchConsoleClient
            token = await GoogleConnectionsService.get_valid_access_token(gsc_conn, db)
            await GoogleSearchConsoleClient.sync_project_gsc_metrics(
                project_id=project_id,
                access_token=token,
                site_url=mapped_prop.site_url,
                db=db
            )
            res = await db.execute(
                select(GSCMetric).where(GSCMetric.project_id == project_id).order_by(GSCMetric.date.desc())
            )
            metrics = res.scalars().all()
        except Exception as e:
            logger.warning(f"[GSC_API] Background sync on fetch failed: {e}")

    # Determine reporting state
    if not gsc_conn or conn_status == "disconnected":
        reporting_state = "not_connected"
    elif conn_status == "expired":
        reporting_state = "needs_reconnection"
    elif sync_error:
        reporting_state = "sync_failed"
    elif not mapped_prop:
        reporting_state = "property_not_mapped"
    elif not metrics:
        reporting_state = "waiting_for_data"
    else:
        reporting_state = "reporting_active"

    if not metrics:
        return {
            "connected": is_connected,
            "reporting_state": reporting_state,
            "status": conn_status,
            "error": sync_error,
            "mapped_property": mapped_prop.site_url if mapped_prop else None,
            "total_clicks": None,
            "total_impressions": None,
            "average_ctr": None,
            "average_position": None,
            "top_queries": [],
            "daily_history": []
        }

    latest = metrics[0]
    total_clicks = sum(m.clicks for m in metrics)
    total_imp = sum(m.impressions for m in metrics)
    avg_ctr = round(sum(m.ctr for m in metrics) / len(metrics), 2)
    avg_pos = round(sum(m.average_position for m in metrics) / len(metrics), 1)

    return {
        "connected": True,
        "reporting_state": reporting_state,
        "status": "active" if reporting_state == "reporting_active" else conn_status,
        "error": sync_error,
        "mapped_property": mapped_prop.site_url if mapped_prop else None,
        "total_clicks": total_clicks,
        "total_impressions": total_imp,
        "average_ctr": avg_ctr,
        "average_position": avg_pos,
        "top_queries": latest.top_queries or [],
        "daily_history": [
            {
                "date": m.date.strftime("%b %d"),
                "clicks": m.clicks,
                "impressions": m.impressions
            }
            for m in reversed(metrics[:14])
        ]
    }


@router.post("/gsc/{project_id}/sync")
async def sync_gsc_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers a fresh sync from Google Search Console Search Analytics API for the project.
    """
    proj = await verify_project_access(project_id, current_user, db)
    from app.models.connections import GoogleConnection, GoogleSearchConsoleProperty
    from app.services.google.connections_service import GoogleConnectionsService
    from app.services.google.gsc_client import GoogleSearchConsoleClient

    gsc_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "search_console", db)
    if not gsc_conn or gsc_conn.status not in ("connected", "expired"):
        raise HTTPException(status_code=400, detail="Google Search Console is not connected for this organization.")

    prop_res = await db.execute(
        select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.project_id == project_id)
    )
    prop = prop_res.scalars().first()
    if not prop:
        raise HTTPException(status_code=400, detail="No Search Console property is mapped to this project. Map a property first.")

    token = await GoogleConnectionsService.get_valid_access_token(gsc_conn, db)
    result = await GoogleSearchConsoleClient.sync_project_gsc_metrics(
        project_id=project_id,
        access_token=token,
        site_url=prop.site_url,
        db=db
    )
    return result


@router.get("/ga4/{project_id}")
async def get_ga4_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real Google Analytics 4 metrics stored for the project, with explicit connection and sync states.
    Never reports fake metrics or false disconnected states.
    """
    proj = await verify_project_access(project_id, current_user, db)
    from app.models.connections import GoogleConnection, GoogleAnalyticsProperty
    from app.models.analytics import GA4Metric
    from app.services.google.connections_service import GoogleConnectionsService

    ga_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "analytics", db)
    is_connected = bool(ga_conn and ga_conn.status == "connected" and ga_conn.access_token)
    conn_status = ga_conn.status if ga_conn else "not_connected"
    sync_error = ga_conn.sync_error if ga_conn else None

    prop_res = await db.execute(
        select(GoogleAnalyticsProperty).where(GoogleAnalyticsProperty.project_id == project_id)
    )
    mapped_prop = prop_res.scalars().first()

    # Auto-mapping fallback: check if any org GA4 property matches domain or business name
    if not mapped_prop and ga_conn:
        avail_props_res = await db.execute(
            select(GoogleAnalyticsProperty).where(GoogleAnalyticsProperty.connection_id == ga_conn.id)
        )
        for p in avail_props_res.scalars().all():
            clean_dom = proj.domain.lower().replace("www.", "")
            clean_name = proj.name.lower()
            if clean_dom in p.display_name.lower() or clean_name in p.display_name.lower():
                p.project_id = project_id
                mapped_prop = p
                await db.commit()
                break

    res = await db.execute(
        select(GA4Metric).where(GA4Metric.project_id == project_id).order_by(GA4Metric.date.desc())
    )
    metrics = res.scalars().all()

    # If connected, property mapped, but no metrics yet -> trigger initial sync automatically
    if is_connected and mapped_prop and not metrics:
        try:
            from app.services.google.ga4_client import GoogleAnalytics4Client
            token = await GoogleConnectionsService.get_valid_access_token(ga_conn, db)
            await GoogleAnalytics4Client.sync_project_ga4_metrics(
                project_id=project_id,
                access_token=token,
                property_id=mapped_prop.property_id,
                db=db
            )
            res = await db.execute(
                select(GA4Metric).where(GA4Metric.project_id == project_id).order_by(GA4Metric.date.desc())
            )
            metrics = res.scalars().all()
        except Exception as e:
            logger.warning(f"[GA4_API] Background sync on fetch failed: {e}")

    # Determine reporting state
    if not ga_conn or conn_status == "disconnected":
        reporting_state = "not_connected"
    elif conn_status == "expired":
        reporting_state = "needs_reconnection"
    elif sync_error:
        reporting_state = "sync_failed"
    elif not mapped_prop:
        reporting_state = "property_not_mapped"
    elif not metrics:
        reporting_state = "waiting_for_data"
    else:
        reporting_state = "reporting_active"

    if not metrics:
        return {
            "connected": is_connected,
            "reporting_state": reporting_state,
            "status": conn_status,
            "error": sync_error,
            "mapped_property": mapped_prop.display_name if mapped_prop else None,
            "total_users": None,
            "organic_users": None,
            "total_sessions": None,
            "sessions": None,
            "engagement_rate": None,
            "total_conversions": None,
            "conversions": None,
            "landing_pages": [],
            "traffic_sources": []
        }

    latest = metrics[0]
    total_u = sum(m.organic_users for m in metrics)
    total_s = sum(m.sessions for m in metrics)
    total_c = sum(m.conversions for m in metrics)
    return {
        "connected": True,
        "reporting_state": reporting_state,
        "status": "active" if reporting_state == "reporting_active" else conn_status,
        "error": sync_error,
        "mapped_property": mapped_prop.display_name if mapped_prop else None,
        "total_users": total_u,
        "organic_users": total_u,
        "total_sessions": total_s,
        "sessions": total_s,
        "engagement_rate": round(sum(m.engagement_rate for m in metrics) / len(metrics), 1),
        "total_conversions": total_c,
        "conversions": total_c,
        "landing_pages": latest.landing_pages or [],
        "traffic_sources": latest.traffic_sources or []
    }


@router.post("/ga4/{project_id}/sync")
async def sync_ga4_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers a fresh sync from Google Analytics 4 Data API for the project.
    """
    proj = await verify_project_access(project_id, current_user, db)
    from app.models.connections import GoogleConnection, GoogleAnalyticsProperty
    from app.services.google.connections_service import GoogleConnectionsService
    from app.services.google.ga4_client import GoogleAnalytics4Client

    ga_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "analytics", db)
    if not ga_conn or ga_conn.status not in ("connected", "expired"):
        raise HTTPException(status_code=400, detail="Google Analytics 4 is not connected for this organization.")

    prop_res = await db.execute(
        select(GoogleAnalyticsProperty).where(GoogleAnalyticsProperty.project_id == project_id)
    )
    prop = prop_res.scalars().first()
    if not prop:
        raise HTTPException(status_code=400, detail="No GA4 property is mapped to this project. Map a property first.")

    token = await GoogleConnectionsService.get_valid_access_token(ga_conn, db)
    result = await GoogleAnalytics4Client.sync_project_ga4_metrics(
        project_id=project_id,
        access_token=token,
        property_id=prop.property_id,
        db=db
    )
    return result


def _normalize_products_and_services(
    products_raw: Any,
    services_raw: Any,
    primary_category: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], int, int]:
    items: List[Dict[str, Any]] = []
    seen_keys = set()
    total_products = 0
    total_services = 0

    # 1. Process Products
    if isinstance(products_raw, list):
        for idx, p in enumerate(products_raw):
            if isinstance(p, dict):
                p_name = str(p.get("name") or p.get("title") or f"Product #{idx + 1}").strip()
                p_key = f"product:{p_name.lower()}"
                if p_key in seen_keys:
                    continue
                seen_keys.add(p_key)
                total_products += 1
                items.append({
                    "id": str(p.get("id") or f"prod-{total_products}"),
                    "type": "product",
                    "name": p_name,
                    "description": p.get("description"),
                    "category": p.get("category") or primary_category or "Products",
                    "price": str(p.get("price")) if p.get("price") is not None else None,
                    "price_range": str(p.get("price_range")) if p.get("price_range") is not None else None,
                    "image_url": p.get("image_url") or p.get("photo_url"),
                    "photo_urls": p.get("photo_urls") or ([p.get("image_url")] if p.get("image_url") else []),
                    "action_url": p.get("action_url") or p.get("url") or p.get("product_url"),
                    "action_type": p.get("action_type") or "VIEW",
                    "source": p.get("source") or "GOOGLE_BUSINESS_PROFILE",
                    "created_at": p.get("created_at"),
                    "updated_at": p.get("updated_at")
                })
            elif isinstance(p, str) and p.strip():
                p_name = p.strip()
                p_key = f"product:{p_name.lower()}"
                if p_key in seen_keys:
                    continue
                seen_keys.add(p_key)
                total_products += 1
                items.append({
                    "id": f"prod-{total_products}",
                    "type": "product",
                    "name": p_name,
                    "description": None,
                    "category": primary_category or "Products",
                    "price": None,
                    "price_range": None,
                    "image_url": None,
                    "photo_urls": [],
                    "action_url": None,
                    "action_type": None,
                    "source": "GOOGLE_BUSINESS_PROFILE",
                    "created_at": None,
                    "updated_at": None
                })

    # 2. Process Services
    if isinstance(services_raw, list):
        for idx, s in enumerate(services_raw):
            if isinstance(s, dict):
                s_name = str(s.get("name") or s.get("title") or f"Service #{idx + 1}").strip()
                s_key = f"service:{s_name.lower()}"
                if s_key in seen_keys:
                    continue
                seen_keys.add(s_key)
                total_services += 1
                items.append({
                    "id": str(s.get("id") or f"serv-{total_services}"),
                    "type": "service",
                    "name": s_name,
                    "description": s.get("description"),
                    "category": s.get("category") or primary_category or "Services",
                    "price": str(s.get("price")) if s.get("price") is not None else None,
                    "price_range": str(s.get("price_range")) if s.get("price_range") is not None else None,
                    "image_url": s.get("image_url") or s.get("photo_url"),
                    "photo_urls": s.get("photo_urls") or ([s.get("image_url")] if s.get("image_url") else []),
                    "action_url": s.get("action_url") or s.get("url") or s.get("booking_url"),
                    "action_type": s.get("action_type") or "BOOK",
                    "source": s.get("source") or "GOOGLE_BUSINESS_PROFILE",
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at")
                })
            elif isinstance(s, str) and s.strip():
                s_name = s.strip()
                s_key = f"service:{s_name.lower()}"
                if s_key in seen_keys:
                    continue
                seen_keys.add(s_key)
                total_services += 1
                items.append({
                    "id": f"serv-{total_services}",
                    "type": "service",
                    "name": s_name,
                    "description": None,
                    "category": primary_category or "Services",
                    "price": None,
                    "price_range": None,
                    "image_url": None,
                    "photo_urls": [],
                    "action_url": None,
                    "action_type": None,
                    "source": "GOOGLE_BUSINESS_PROFILE",
                    "created_at": None,
                    "updated_at": None
                })

    return items, total_products, total_services


@router.get("/{project_id}/products-services", response_model=ProductsServicesResponseOut)
async def get_products_services(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves all verified Products and Services for a business project.
    Aggregates items from bound Google Business Profile and public listings with stable IDs.
    """
    project = await verify_project_access(project_id, current_user, db)

    # 1. Fetch Google Business Profile
    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()

    # 2. Fetch Public Business Listing fallback
    listing_res = await db.execute(
        select(PublicBusinessListing).where(PublicBusinessListing.project_id == project_id)
    )
    listing = listing_res.scalars().first()

    # 3. Resolve Connected Account Email
    connected_email = None
    is_connected = False
    if profile:
        is_connected = profile.status == "CONNECTED"
        if profile.google_account_id:
            gacc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.id == profile.google_account_id))
            gacc = gacc_res.scalars().first()
            if gacc:
                connected_email = gacc.account_email
        elif profile.google_connection_id:
            from app.models.connections import GoogleConnection
            conn_res = await db.execute(select(GoogleConnection).where(GoogleConnection.id == profile.google_connection_id))
            gconn = conn_res.scalars().first()
            if gconn:
                connected_email = gconn.account_email

    products_raw = profile.products if (profile and profile.products) else []
    services_raw = profile.services if (profile and profile.services) else []
    primary_category = (profile.primary_category if profile else None) or (listing.category if listing else project.primary_category)
    business_name = (profile.business_name if profile else None) or (listing.name if listing else project.name)
    place_id = (profile.place_id if profile else None) or (listing.place_id if listing else None)
    last_synced_at = profile.last_synced_at.isoformat() if (profile and profile.last_synced_at) else (
        listing.last_checked_at.isoformat() if (listing and listing.last_checked_at) else None
    )

    items, total_products, total_services = _normalize_products_and_services(
        products_raw, services_raw, primary_category
    )

    sync_status = "NOT_AVAILABLE" if is_connected else "NOT_SYNCED"
    sync_message = (
        "Product/service catalog sync is not available through the connected Google API. Items are maintained in LocalLift catalog."
        if is_connected
        else "Google Business Profile is not connected for this project."
    )

    return {
        "business_name": business_name,
        "place_id": place_id,
        "is_connected": is_connected,
        "connected_account": connected_email,
        "total_products": total_products,
        "total_services": total_services,
        "last_synced_at": last_synced_at,
        "sync_status": sync_status,
        "sync_message": sync_message,
        "can_sync": False,
        "items": items
    }


@router.post("/{project_id}/products-services/sync", response_model=ProductsServicesResponseOut)
async def sync_products_services(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Attempts synchronization of Products and Services.
    Accurately reports that direct product/service catalog sync is not supported via connected Google API.
    """
    project = await verify_project_access(project_id, current_user, db)

    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()

    sync_status = "NOT_AVAILABLE"
    sync_message = "Product/service sync is not available through the connected Google API."

    if profile and profile.location_resource_name:
        try:
            await GBPSyncService.sync_project_gbp(project_id, db)
            await db.refresh(profile)
            sync_status = "NOT_AVAILABLE"
            sync_message = "Product/service sync is not available through the connected Google API. Profile metadata was refreshed."
        except Exception as e:
            logger.warning(f"[GBP_PRODUCTS_SYNC] Live sync notice: {e}")
            sync_status = "FAILED"
            sync_message = f"Google sync failed: {str(e)}"
    else:
        sync_status = "NOT_SYNCED"
        sync_message = "No connected Google Business Profile location found for this project."

    res = await get_products_services(project_id=project_id, current_user=current_user, db=db)
    res["sync_status"] = sync_status
    res["sync_message"] = sync_message
    return res


async def _get_or_create_gbp_profile(project: Project, db: AsyncSession) -> GoogleBusinessProfile:
    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project.id)
    )
    profile = prof_res.scalars().first()
    if not profile:
        # Check if project has an active Google connection
        from app.models.connections import GoogleConnection
        conn_res = await db.execute(
            select(GoogleConnection).where(GoogleConnection.project_id == project.id)
        )
        has_conn = conn_res.scalars().first() is not None

        profile = GoogleBusinessProfile(
            project_id=project.id,
            business_name=project.name,
            primary_category=project.primary_category or "Local Business",
            status="CONNECTED" if has_conn else "UNCONNECTED",
            products=[],
            services=[],
            last_synced_at=datetime.now(timezone.utc)
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.post("/{project_id}/products", response_model=ProductOrServiceItemOut)
async def create_product(
    project_id: int,
    product_in: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new Product in the project catalog and persists to local catalog with LOCALLIFT_MANUAL provenance.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    now_iso = datetime.now(timezone.utc).isoformat()
    new_id = f"prod-{uuid.uuid4().hex[:8]}"

    item = {
        "id": new_id,
        "type": "product",
        "name": product_in.name.strip(),
        "description": product_in.description.strip() if product_in.description else None,
        "category": (product_in.category.strip() if product_in.category else None) or profile.primary_category or "Products",
        "price": product_in.price.strip() if product_in.price else None,
        "price_range": product_in.price_range.strip() if product_in.price_range else None,
        "image_url": product_in.image_url.strip() if product_in.image_url else None,
        "photo_urls": [product_in.image_url.strip()] if product_in.image_url else [],
        "action_url": product_in.action_url.strip() if product_in.action_url else None,
        "action_type": product_in.action_type or "VIEW",
        "source": "LOCALLIFT_MANUAL",
        "created_at": now_iso,
        "updated_at": now_iso
    }

    products = list(profile.products or [])
    products.append(item)
    profile.products = products
    flag_modified(profile, "products")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return item


@router.put("/{project_id}/products/{product_id}", response_model=ProductOrServiceItemOut)
async def update_product(
    project_id: int,
    product_id: str,
    product_in: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an existing Product in the project catalog.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    products = list(profile.products or [])
    target_idx = None
    target_item = None

    for idx, p in enumerate(products):
        if isinstance(p, dict) and str(p.get("id")) == str(product_id):
            target_idx = idx
            target_item = p
            break
        elif isinstance(p, str) and str(product_id) in [f"prod-{idx+1}", p]:
            target_idx = idx
            target_item = {"id": product_id, "name": p, "type": "product"}
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Product not found in catalog")

    now_iso = datetime.now(timezone.utc).isoformat()
    if product_in.name is not None:
        target_item["name"] = product_in.name.strip()
    if product_in.description is not None:
        target_item["description"] = product_in.description.strip() or None
    if product_in.category is not None:
        target_item["category"] = product_in.category.strip() or None
    if product_in.price is not None:
        target_item["price"] = product_in.price.strip() or None
    if product_in.price_range is not None:
        target_item["price_range"] = product_in.price_range.strip() or None
    if product_in.image_url is not None:
        target_item["image_url"] = product_in.image_url.strip() or None
        target_item["photo_urls"] = [product_in.image_url.strip()] if product_in.image_url.strip() else []
    if product_in.action_url is not None:
        target_item["action_url"] = product_in.action_url.strip() or None
    if product_in.action_type is not None:
        target_item["action_type"] = product_in.action_type or "VIEW"

    target_item["updated_at"] = now_iso
    target_item["type"] = "product"
    target_item["source"] = target_item.get("source") or "LOCALLIFT_MANUAL"

    products[target_idx] = target_item
    profile.products = products
    flag_modified(profile, "products")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return target_item


@router.delete("/{project_id}/products/{product_id}")
async def delete_product(
    project_id: int,
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a Product from the project catalog.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    products = list(profile.products or [])
    new_products = []
    deleted = False

    for idx, p in enumerate(products):
        if isinstance(p, dict) and str(p.get("id")) == str(product_id):
            deleted = True
            continue
        elif isinstance(p, str) and str(product_id) in [f"prod-{idx+1}", p]:
            deleted = True
            continue
        new_products.append(p)

    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found in catalog")

    profile.products = new_products
    flag_modified(profile, "products")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return {"message": "Product deleted successfully", "id": product_id}


@router.post("/{project_id}/services", response_model=ProductOrServiceItemOut)
async def create_service(
    project_id: int,
    service_in: ServiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new Service offering in the project catalog with LOCALLIFT_MANUAL provenance.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    now_iso = datetime.now(timezone.utc).isoformat()
    new_id = f"serv-{uuid.uuid4().hex[:8]}"

    item = {
        "id": new_id,
        "type": "service",
        "name": service_in.name.strip(),
        "description": service_in.description.strip() if service_in.description else None,
        "category": (service_in.category.strip() if service_in.category else None) or profile.primary_category or "Services",
        "price": service_in.price.strip() if service_in.price else None,
        "price_range": service_in.price_range.strip() if service_in.price_range else None,
        "image_url": None,
        "photo_urls": [],
        "action_url": service_in.action_url.strip() if service_in.action_url else None,
        "action_type": service_in.action_type or "BOOK",
        "source": "LOCALLIFT_MANUAL",
        "created_at": now_iso,
        "updated_at": now_iso
    }

    services = list(profile.services or [])
    services.append(item)
    profile.services = services
    flag_modified(profile, "services")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return item


@router.put("/{project_id}/services/{service_id}", response_model=ProductOrServiceItemOut)
async def update_service(
    project_id: int,
    service_id: str,
    service_in: ServiceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an existing Service offering in the project catalog.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    services = list(profile.services or [])
    target_idx = None
    target_item = None

    for idx, s in enumerate(services):
        if isinstance(s, dict) and str(s.get("id")) == str(service_id):
            target_idx = idx
            target_item = s
            break
        elif isinstance(s, str) and str(service_id) in [f"serv-{idx+1}", s]:
            target_idx = idx
            target_item = {"id": service_id, "name": s, "type": "service"}
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Service not found in catalog")

    now_iso = datetime.now(timezone.utc).isoformat()
    if service_in.name is not None:
        target_item["name"] = service_in.name.strip()
    if service_in.description is not None:
        target_item["description"] = service_in.description.strip() or None
    if service_in.category is not None:
        target_item["category"] = service_in.category.strip() or None
    if service_in.price is not None:
        target_item["price"] = service_in.price.strip() or None
    if service_in.price_range is not None:
        target_item["price_range"] = service_in.price_range.strip() or None
    if service_in.action_url is not None:
        target_item["action_url"] = service_in.action_url.strip() or None
    if service_in.action_type is not None:
        target_item["action_type"] = service_in.action_type or "BOOK"

    target_item["updated_at"] = now_iso
    target_item["type"] = "service"
    target_item["source"] = target_item.get("source") or "LOCALLIFT_MANUAL"

    services[target_idx] = target_item
    profile.services = services
    flag_modified(profile, "services")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return target_item


@router.delete("/{project_id}/services/{service_id}")
async def delete_service(
    project_id: int,
    service_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a Service from the project catalog.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    services = list(profile.services or [])
    new_services = []
    deleted = False

    for idx, s in enumerate(services):
        if isinstance(s, dict) and str(s.get("id")) == str(service_id):
            deleted = True
            continue
        elif isinstance(s, str) and str(service_id) in [f"serv-{idx+1}", s]:
            deleted = True
            continue
        new_services.append(s)

    if not deleted:
        raise HTTPException(status_code=404, detail="Service not found in catalog")

    profile.services = new_services
    flag_modified(profile, "services")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return {"message": "Service deleted successfully", "id": service_id}


@router.post("/{project_id}/products-services/bulk-import", response_model=ProductsServicesResponseOut)
async def bulk_import_products_services(
    project_id: int,
    import_data: BulkProductsServicesImport,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk imports products and services into the project catalog with LOCALLIFT_MANUAL provenance.
    """
    project = await verify_project_access(project_id, current_user, db)
    profile = await _get_or_create_gbp_profile(project, db)

    now_iso = datetime.now(timezone.utc).isoformat()
    products = list(profile.products or [])
    services = list(profile.services or [])

    if import_data.products:
        for p in import_data.products:
            new_id = f"prod-{uuid.uuid4().hex[:8]}"
            products.append({
                "id": new_id,
                "type": "product",
                "name": p.name.strip(),
                "description": p.description.strip() if p.description else None,
                "category": p.category.strip() if p.category else (profile.primary_category or "Products"),
                "price": p.price.strip() if p.price else None,
                "price_range": p.price_range.strip() if p.price_range else None,
                "image_url": p.image_url.strip() if p.image_url else None,
                "photo_urls": [p.image_url.strip()] if p.image_url else [],
                "action_url": p.action_url.strip() if p.action_url else None,
                "action_type": p.action_type or "VIEW",
                "source": "LOCALLIFT_MANUAL",
                "created_at": now_iso,
                "updated_at": now_iso
            })

    if import_data.services:
        for s in import_data.services:
            new_id = f"serv-{uuid.uuid4().hex[:8]}"
            services.append({
                "id": new_id,
                "type": "service",
                "name": s.name.strip(),
                "description": s.description.strip() if s.description else None,
                "category": s.category.strip() if s.category else (profile.primary_category or "Services"),
                "price": s.price.strip() if s.price else None,
                "price_range": s.price_range.strip() if s.price_range else None,
                "image_url": None,
                "photo_urls": [],
                "action_url": s.action_url.strip() if s.action_url else None,
                "action_type": s.action_type or "BOOK",
                "source": "LOCALLIFT_MANUAL",
                "created_at": now_iso,
                "updated_at": now_iso
            })

    profile.products = products
    profile.services = services
    flag_modified(profile, "products")
    flag_modified(profile, "services")
    profile.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)

    return await get_products_services(project_id=project_id, current_user=current_user, db=db)


google_router = APIRouter(prefix="/google", tags=["Google Integrations"])
google_router.add_api_route("/gsc/{project_id}", get_gsc_data, methods=["GET"])
google_router.add_api_route("/gsc/{project_id}/sync", sync_gsc_data, methods=["POST"])
google_router.add_api_route("/ga4/{project_id}", get_ga4_data, methods=["GET"])
google_router.add_api_route("/ga4/{project_id}/sync", sync_ga4_data, methods=["POST"])
google_router.add_api_route("/gbp/{project_id}", get_gbp_profile, methods=["GET"])
google_router.add_api_route("/gbp/{project_id}/products-services", get_products_services, methods=["GET"])
google_router.add_api_route("/gbp/{project_id}/products-services/sync", sync_products_services, methods=["POST"])
google_router.add_api_route("/gbp/{project_id}/products", create_product, methods=["POST"])
google_router.add_api_route("/gbp/{project_id}/products/{product_id}", update_product, methods=["PUT"])
google_router.add_api_route("/gbp/{project_id}/products/{product_id}", delete_product, methods=["DELETE"])
google_router.add_api_route("/gbp/{project_id}/services", create_service, methods=["POST"])
google_router.add_api_route("/gbp/{project_id}/services/{service_id}", update_service, methods=["PUT"])
google_router.add_api_route("/gbp/{project_id}/services/{service_id}", delete_service, methods=["DELETE"])
google_router.add_api_route("/gbp/{project_id}/products-services/bulk-import", bulk_import_products_services, methods=["POST"])




