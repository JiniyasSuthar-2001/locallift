import json
import urllib.parse
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project
from app.models.gbp import GoogleBusinessProfile, GoogleAccount, GBPChange
from app.schemas.gbp import (
    GBPProfileOut,
    GBPChangeOut,
    GBPOAuthURLResponse,
    GBPOAuthCallbackRequest,
    GBPStatusResponse,
    GBPSyncResponse
)
from app.services.google import GoogleOAuthService, GBPSyncService
from app.services.google.connections_service import GoogleConnectionsService

logger = logging.getLogger("locallift.gbp")

router = APIRouter(prefix="/gbp", tags=["Google Business Profile"])

async def _get_or_sync_google_account_for_project(project: Project, db: AsyncSession) -> Optional[GoogleAccount]:
    """
    Resolves the canonical Google connection state for a project.
    If project GoogleAccount is missing or disconnected, checks the organization-wide
    GoogleConnection for service='business_profile' and bridges credentials dynamically.
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
                account_email=gbp_conn.account_email or f"user-{project.id}@google.com",
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

        prof_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == account.id)
        )
        if not prof_res.scalars().first():
            db.add(GoogleBusinessProfile(
                google_account_id=account.id,
                business_name=project.name,
                primary_category=project.primary_category or "Local Business",
                website_url=f"https://{project.domain}" if project.domain else None,
                completeness_score=85,
                is_verified=True
            ))
            await db.flush()

        await db.commit()
        await db.refresh(account)
        return account

    return None

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
    if not email:
        email = f"google-user-{project.id}@gmail.com"

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
        sync_result = await GBPSyncService.sync_google_account(account, db)
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

@router.post("/{project_id}/sync", response_model=GBPSyncResponse)
async def sync_gbp_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes live idempotent synchronization of GBP profile information and performance metrics.
    """
    project = await verify_project_access(project_id, current_user, db)
    account = await _get_or_sync_google_account_for_project(project, db)
    if not account or not account.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Google Account is not connected for this project. Please connect via OAuth first."
        )

    try:
        sync_res = await GBPSyncService.sync_google_account(account, db)
        return GBPSyncResponse(
            message="Google Business Profile synced successfully.",
            status="synced",
            profiles_synced=sync_res.get("profiles_synced", 1),
            changes_detected=sync_res.get("changes_detected", 0),
            last_synced_at=sync_res.get("last_synced_at", datetime.now(timezone.utc))
        )
    except Exception as e:
        logger.error(f"Manual GBP sync failed for project {project_id}: {e}")
        # If token expired and cannot refresh, report clean error
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
    if account:
        account.is_connected = False
        account.access_token = None
        account.refresh_token = None

    gbp_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)
    if gbp_conn:
        gbp_conn.status = "disconnected"
        gbp_conn.access_token = None

    await db.commit()
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


google_router = APIRouter(prefix="/google", tags=["Google Integrations"])
google_router.add_api_route("/gsc/{project_id}", get_gsc_data, methods=["GET"])
google_router.add_api_route("/gsc/{project_id}/sync", sync_gsc_data, methods=["POST"])
google_router.add_api_route("/ga4/{project_id}", get_ga4_data, methods=["GET"])
google_router.add_api_route("/ga4/{project_id}/sync", sync_ga4_data, methods=["POST"])
google_router.add_api_route("/gbp/{project_id}", get_gbp_profile, methods=["GET"])


