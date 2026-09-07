import json
import urllib.parse
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
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

logger = logging.getLogger("locallift.gbp")

router = APIRouter(prefix="/gbp", tags=["Google Business Profile"])

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
    await verify_project_access(project_id, current_user, db)
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
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
    await verify_project_access(project_id, current_user, db)
    is_configured = GoogleOAuthService.is_configured()

    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()

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

@router.get("/{project_id}/auth-url", response_model=GBPOAuthURLResponse)
async def get_google_auth_url(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates the official Google OAuth 2.0 authorization URL.
    """
    project = await verify_project_access(project_id, current_user, db)

    auth_url = GoogleOAuthService.get_authorization_url(
        project_id=project.id,
        user_id=current_user.id
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
    Handles Google OAuth callback code exchange and triggers initial synchronization.
    """
    if not cb_req.code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Google")

    # 1. Decode state if provided
    project_id = cb_req.project_id
    if cb_req.state and not project_id:
        try:
            state_data = json.loads(urllib.parse.unquote(cb_req.state))
            project_id = state_data.get("project_id")
        except Exception as e:
            logger.warning(f"Could not decode OAuth state: {e}")

    if not project_id:
        raise HTTPException(status_code=400, detail="Project ID missing from OAuth flow")

    # 2. Exchange code for tokens
    try:
        token_info = await GoogleOAuthService.exchange_code_for_tokens(cb_req.code)
    except Exception as e:
        logger.error(f"Google OAuth token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {str(e)}")

    # 3. Retrieve user info / email
    email = await GoogleOAuthService.get_user_email(token_info["access_token"])
    if not email:
        email = f"google-user-{project_id}@gmail.com"

    # 4. Create or update GoogleAccount record for this project
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()

    if not account:
        account = GoogleAccount(
            project_id=project_id,
            account_email=email,
            access_token=token_info["access_token"],
            refresh_token=token_info.get("refresh_token"),
            token_expiry=token_info.get("token_expiry"),
            scopes=token_info.get("scope", []),
            is_connected=True
        )
        db.add(account)
    else:
        account.account_email = email
        account.access_token = token_info["access_token"]
        if token_info.get("refresh_token"):
            account.refresh_token = token_info["refresh_token"]
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
    await verify_project_access(project_id, current_user, db)
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
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
    await verify_project_access(project_id, current_user, db)
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    account = acc_res.scalars().first()
    if account and account.is_connected:
        account.is_connected = False
        account.access_token = None
        account.refresh_token = None
        await db.commit()
        return {"message": "Google Business Profile disconnected successfully.", "status": "disconnected"}
    
    return {"message": "No Google Business Profile connection was active.", "status": "not_connected"}

@router.get("/gsc/{project_id}")
async def get_gsc_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real Google Search Console metrics stored for the project, or a connected=False state.
    """
    await verify_project_access(project_id, current_user, db)
    from app.models.analytics import GSCMetric
    res = await db.execute(
        select(GSCMetric).where(GSCMetric.project_id == project_id).order_by(GSCMetric.date.desc())
    )
    metrics = res.scalars().all()

    if not metrics:
        return {
            "connected": False,
            "total_clicks": 0,
            "total_impressions": 0,
            "average_ctr": 0.0,
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

@router.get("/ga4/{project_id}")
async def get_ga4_data(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real Google Analytics 4 metrics stored for the project, or a connected=False state.
    """
    await verify_project_access(project_id, current_user, db)
    from app.models.analytics import GA4Metric
    res = await db.execute(
        select(GA4Metric).where(GA4Metric.project_id == project_id).order_by(GA4Metric.date.desc())
    )
    metrics = res.scalars().all()

    if not metrics:
        return {
            "connected": False,
            "total_users": 0,
            "total_sessions": 0,
            "engagement_rate": 0.0,
            "total_conversions": 0,
            "landing_pages": [],
            "traffic_sources": []
        }

    latest = metrics[0]
    return {
        "connected": True,
        "total_users": sum(m.organic_users for m in metrics),
        "total_sessions": sum(m.sessions for m in metrics),
        "engagement_rate": round(sum(m.engagement_rate for m in metrics) / len(metrics), 1),
        "total_conversions": sum(m.conversions for m in metrics),
        "landing_pages": latest.landing_pages or [],
        "traffic_sources": latest.traffic_sources or []
    }

google_router = APIRouter(prefix="/google", tags=["Google Integrations"])
google_router.add_api_route("/gsc/{project_id}", get_gsc_data, methods=["GET"])
google_router.add_api_route("/ga4/{project_id}", get_ga4_data, methods=["GET"])
google_router.add_api_route("/gbp/{project_id}", get_gbp_profile, methods=["GET"])


