import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.core.deps import get_current_user, get_user_organization_ids
from app.core.security import encrypt_token, decrypt_token
from app.models.user import User
from app.models.connections import OrganizationSERPConfig
from app.core.audit_logger import log_user_action

logger = logging.getLogger("locallift.api.serp")
router = APIRouter(prefix="/serp", tags=["serp"])


class SERPConfigResponse(BaseModel):
    provider: str = "serpapi"
    has_key: bool = False
    masked_key: Optional[str] = None
    connection_status: str = "not_configured"
    status_message: Optional[str] = None
    last_tested_at: Optional[datetime] = None


class SERPSaveConfigRequest(BaseModel):
    provider: str = "serpapi"
    api_key: Optional[str] = None


class SERPTestConnectionRequest(BaseModel):
    provider: Optional[str] = "serpapi"
    api_key: Optional[str] = None


def _mask_key(raw_key: str) -> str:
    if not raw_key:
        return ""
    clean = raw_key.strip()
    if len(clean) <= 6:
        return "••••••••"
    return f"••••••••{clean[-4:]}"


@router.get("/config", response_model=SERPConfigResponse)
async def get_serp_configuration(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SERPConfigResponse:
    """
    Returns organization-specific SERP configuration without exposing raw API keys.
    """
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids and not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    org_id = org_ids[0] if org_ids else None
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    log_user_action(request, "OPEN_SERP_SETTINGS", user_id=current_user.id, organization_id=org_id)

    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    if not serp_config:
        return SERPConfigResponse(
            provider="serpapi",
            has_key=False,
            masked_key=None,
            connection_status="not_configured",
            status_message="SERP API key not configured.",
            last_tested_at=None
        )

    raw_key = decrypt_token(serp_config.api_key) if serp_config.api_key else ""
    return SERPConfigResponse(
        provider=serp_config.provider or "serpapi",
        has_key=bool(raw_key),
        masked_key=_mask_key(raw_key) if raw_key else None,
        connection_status=serp_config.connection_status or "not_configured",
        status_message=serp_config.status_message,
        last_tested_at=serp_config.last_tested_at
    )


@router.post("/config", response_model=SERPConfigResponse)
async def save_serp_configuration(
    request: Request,
    req: SERPSaveConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SERPConfigResponse:
    """
    Saves or updates organization SERP provider credentials.
    API keys are encrypted at rest using AES-256 Fernet tokens.
    """
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids and not current_user.is_superuser:
        log_user_action(request, "SAVE_SERP_CONFIGURATION", user_id=current_user.id, status="failed", error="NO_ORG")
        raise HTTPException(status_code=400, detail="User has no associated organization")
    org_id = org_ids[0] if org_ids else None
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    clean_key = req.api_key.strip() if req.api_key else ""
    enc_key = encrypt_token(clean_key) if clean_key else None

    if not serp_config:
        serp_config = OrganizationSERPConfig(
            organization_id=org_id,
            provider=req.provider or "serpapi",
            api_key=enc_key,
            connection_status="connected" if clean_key else "not_configured",
            status_message="API Key saved successfully." if clean_key else "No API Key provided.",
            last_tested_at=datetime.now(timezone.utc) if clean_key else None
        )
        db.add(serp_config)
    else:
        serp_config.provider = req.provider or "serpapi"
        if clean_key:
            serp_config.api_key = enc_key
            serp_config.connection_status = "connected"
            serp_config.status_message = "API Key saved successfully."
            serp_config.last_tested_at = datetime.now(timezone.utc)
        elif req.api_key == "":
            serp_config.api_key = None
            serp_config.connection_status = "not_configured"
            serp_config.status_message = "SERP API Key removed."

    await db.commit()
    await db.refresh(serp_config)

    log_user_action(
        request,
        "SAVE_SERP_CONFIGURATION",
        user_id=current_user.id,
        organization_id=org_id,
        status="success",
        provider=serp_config.provider,
        configured=bool(clean_key)
    )

    return SERPConfigResponse(
        provider=serp_config.provider,
        has_key=bool(clean_key),
        masked_key=_mask_key(clean_key) if clean_key else None,
        connection_status=serp_config.connection_status,
        status_message=serp_config.status_message,
        last_tested_at=serp_config.last_tested_at
    )


@router.post("/test-connection")
async def test_serp_connection(
    request: Request,
    req: SERPTestConnectionRequest = SERPTestConnectionRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Tests live connection to SerpApi using encrypted organization credentials.
    """
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids and not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    org_id = org_ids[0] if org_ids else None
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    log_user_action(request, "TEST_SERP_CONNECTION", user_id=current_user.id, organization_id=org_id, status="started")

    # Determine key to test
    target_key = req.api_key.strip() if req.api_key else ""
    if not target_key:
        stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
        res = await db.execute(stmt)
        serp_config = res.scalars().first()
        if serp_config and serp_config.api_key:
            target_key = decrypt_token(serp_config.api_key) or ""

    if not target_key:
        # Check global fallback
        target_key = getattr(settings, "SERPAPI_KEY", "")

    if not target_key:
        logger.warning(f"[SERP] connection_test status=not_configured user={current_user.id} organization={org_id}")
        return {
            "status": "not_configured",
            "success": False,
            "error_code": "SERP_API_KEY_REQUIRED",
            "message": "SERP provider not configured. Please enter your SerpApi API key."
        }

    # Execute real lightweight test query to SerpApi
    test_params = {
        "engine": "google",
        "q": "test",
        "num": 1,
        "api_key": target_key
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://serpapi.com/search.json", params=test_params)
            
            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    err_msg = str(data.get("error"))
                    status_code = "invalid_key" if "api_key" in err_msg.lower() or "invalid" in err_msg.lower() else "error"
                    await _update_serp_status(db, org_id, status_code, err_msg)
                    logger.warning(f"[SERP] connection_test status={status_code} organization={org_id}")
                    return {
                        "status": status_code,
                        "success": False,
                        "message": f"SerpApi test failed: {err_msg}"
                    }

                await _update_serp_status(db, org_id, "connected", "SerpApi account verified and active.")
                logger.info(f"[SERP] connection_test status=success organization={org_id}")
                return {
                    "status": "connected",
                    "success": True,
                    "message": "SerpApi connection test passed successfully!"
                }
            elif resp.status_code in (401, 403):
                await _update_serp_status(db, org_id, "invalid_key", "SerpApi authentication failed. Invalid API key.")
                logger.warning(f"[SERP] connection_test status=invalid_key organization={org_id}")
                return {
                    "status": "invalid_key",
                    "success": False,
                    "error_code": "INVALID_API_KEY",
                    "message": "SerpApi authentication failed. Please verify your API key."
                }
            elif resp.status_code == 429:
                await _update_serp_status(db, org_id, "quota_exceeded", "SerpApi search quota exceeded.")
                logger.warning(f"[SERP] connection_test status=quota_exceeded organization={org_id}")
                return {
                    "status": "quota_exceeded",
                    "success": False,
                    "error_code": "QUOTA_EXCEEDED",
                    "message": "Your SerpApi account has reached its available search limit."
                }
            else:
                msg = f"SerpApi returned HTTP {resp.status_code}"
                await _update_serp_status(db, org_id, "error", msg)
                return {
                    "status": "error",
                    "success": False,
                    "message": msg
                }
    except Exception as e:
        logger.error(f"[SERP] connection_test status=error organization={org_id} error={e}")
        return {
            "status": "error",
            "success": False,
            "message": "Unable to reach the SERP provider. Please check network connectivity."
        }


async def _update_serp_status(db: AsyncSession, org_id: int, status_str: str, message_str: str):
    try:
        stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
        res = await db.execute(stmt)
        cfg = res.scalars().first()
        if cfg:
            cfg.connection_status = status_str
            cfg.status_message = message_str
            cfg.last_tested_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to update SERP status in DB: {e}")
