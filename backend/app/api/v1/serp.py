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
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.openserp import OpenSERPProvider

logger = logging.getLogger("locallift.api.serp")
router = APIRouter(prefix="/serp", tags=["serp"])


class SERPConfigResponse(BaseModel):
    provider: str = "serpapi"
    base_url: Optional[str] = None
    auth_mode: str = "api_key"
    has_key: bool = False
    masked_key: Optional[str] = None
    connection_status: str = "not_configured"
    capabilities: Dict[str, bool] = {
        "organic_search": False,
        "local_search": False,
        "maps_search": False,
        "coordinate_search": False,
        "geo_grid": False
    }
    status_message: Optional[str] = None
    last_tested_at: Optional[datetime] = None


class SERPSaveConfigRequest(BaseModel):
    provider: str = "serpapi"
    base_url: Optional[str] = None
    auth_mode: Optional[str] = "api_key"
    api_key: Optional[str] = None


class SERPTestConnectionRequest(BaseModel):
    provider: Optional[str] = "serpapi"
    base_url: Optional[str] = None
    api_key: Optional[str] = None


def _mask_key(raw_key: str) -> str:
    if not raw_key:
        return ""
    clean = raw_key.strip()
    if len(clean) <= 6:
        return "••••••••"
    return f"••••••••{clean[-4:]}"


def _get_provider_capabilities(provider_type: str, is_active: bool) -> Dict[str, bool]:
    if not is_active:
        return {
            "organic_search": False,
            "local_search": False,
            "maps_search": False,
            "coordinate_search": False,
            "geo_grid": False
        }
    p_name = provider_type.lower()
    if p_name == "serpapi":
        prov = SerpApiProvider(api_key="valid_dummy_key")
        caps = prov.capabilities
        return caps.model_dump()
    elif p_name == "openserp":
        prov = OpenSERPProvider(base_url="http://localhost:7000")
        caps = prov.capabilities
        return caps.model_dump()
    return {
        "organic_search": False,
        "local_search": False,
        "maps_search": False,
        "coordinate_search": False,
        "geo_grid": False
    }


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
            base_url=None,
            auth_mode="api_key",
            has_key=False,
            masked_key=None,
            connection_status="not_configured",
            capabilities=_get_provider_capabilities("serpapi", is_active=False),
            status_message="SERP API key not configured.",
            last_tested_at=None
        )

    raw_key = decrypt_token(serp_config.api_key) if serp_config.api_key else ""
    is_active = serp_config.connection_status == "connected"
    caps = _get_provider_capabilities(serp_config.provider or "serpapi", is_active=is_active)

    return SERPConfigResponse(
        provider=serp_config.provider or "serpapi",
        base_url=serp_config.base_url,
        auth_mode=serp_config.auth_mode or "api_key",
        has_key=bool(raw_key),
        masked_key=_mask_key(raw_key) if raw_key else None,
        connection_status=serp_config.connection_status or "not_configured",
        capabilities=caps,
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

    provider_choice = (req.provider or "serpapi").lower()
    clean_key = req.api_key.strip().strip("'\"").strip() if req.api_key else ""

    # If submitted key is masked (contains '•' or '*'), preserve existing decrypted stored key
    if clean_key and any(c in clean_key for c in ("•", "*")) and serp_config and serp_config.api_key:
        decrypted_existing = decrypt_token(serp_config.api_key)
        if decrypted_existing:
            clean_key = decrypted_existing.strip().strip("'\"").strip()

    enc_key = encrypt_token(clean_key) if clean_key else None
    base_url_val = (req.base_url or "").strip() or None

    is_configured_state = False
    if provider_choice == "openserp":
        is_configured_state = bool(base_url_val or getattr(settings, "OPENSERP_BASE_URL", None))
    else:
        is_configured_state = bool(clean_key)

    if not serp_config:
        serp_config = OrganizationSERPConfig(
            organization_id=org_id,
            provider=provider_choice,
            base_url=base_url_val,
            auth_mode=req.auth_mode or ("none" if provider_choice == "openserp" else "api_key"),
            api_key=enc_key,
            connection_status="connected" if is_configured_state else "not_configured",
            status_message="SERP settings saved successfully." if is_configured_state else "No API Key / Base URL provided.",
            last_tested_at=datetime.now(timezone.utc) if is_configured_state else None
        )
        db.add(serp_config)
    else:
        serp_config.provider = provider_choice
        serp_config.base_url = base_url_val
        serp_config.auth_mode = req.auth_mode or ("none" if provider_choice == "openserp" else "api_key")
        if clean_key:
            serp_config.api_key = enc_key
            serp_config.connection_status = "connected"
            serp_config.status_message = "API Key saved successfully."
            serp_config.last_tested_at = datetime.now(timezone.utc)
        elif provider_choice == "openserp" and is_configured_state:
            serp_config.connection_status = "connected"
            serp_config.status_message = "OpenSERP base URL configured."
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
        configured=is_configured_state
    )

    raw_key = decrypt_token(serp_config.api_key) if serp_config.api_key else ""
    caps = _get_provider_capabilities(serp_config.provider, is_active=(serp_config.connection_status == "connected"))
    return SERPConfigResponse(
        provider=serp_config.provider,
        base_url=serp_config.base_url,
        auth_mode=serp_config.auth_mode or "api_key",
        has_key=bool(raw_key),
        masked_key=_mask_key(raw_key) if raw_key else None,
        connection_status=serp_config.connection_status,
        capabilities=caps,
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
    Tests live connection to SerpApi or OpenSERP using organization credentials.
    """
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids and not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    org_id = org_ids[0] if org_ids else None
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    log_user_action(request, "TEST_SERP_CONNECTION", user_id=current_user.id, organization_id=org_id, status="started")

    # Load existing config for default fallback
    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    provider_choice = (req.provider or (serp_config.provider if serp_config else "serpapi")).lower()

    if provider_choice == "openserp":
        target_base_url = (req.base_url or (serp_config.base_url if serp_config else None) or getattr(settings, "OPENSERP_BASE_URL", "http://127.0.0.1:7000")).rstrip("/")
        prov = OpenSERPProvider(base_url=target_base_url)
        health = await prov.check_health()
        is_conn = health.get("status") == "CONNECTED"
        status_str = "connected" if is_conn else "error"
        msg_str = health.get("message", "OpenSERP test completed.")
        await _update_serp_status(db, org_id, status_str, msg_str)
        return {
            "status": status_str,
            "success": is_conn,
            "provider": "openserp",
            "base_url": target_base_url,
            "capabilities": prov.capabilities.model_dump(),
            "message": msg_str
        }

    # SerpApi test logic
    target_key = req.api_key.strip().strip("'\"").strip() if req.api_key else ""
    if not target_key or any(c in target_key for c in ("•", "*")):
        if serp_config and serp_config.api_key:
            decrypted = decrypt_token(serp_config.api_key)
            if decrypted:
                target_key = decrypted.strip().strip("'\"").strip()

    if not target_key:
        global_key = getattr(settings, "SERPAPI_KEY", "")
        if global_key:
            target_key = global_key.strip().strip("'\"").strip()

    if not target_key:
        logger.warning(f"[SERP] connection_test status=not_configured user={current_user.id} organization={org_id}")
        return {
            "status": "not_configured",
            "success": False,
            "provider": "serpapi",
            "capabilities": _get_provider_capabilities("serpapi", is_active=False),
            "error_code": "SERP_API_KEY_REQUIRED",
            "message": "SERP provider not configured. Please enter your SerpApi API key."
        }

    test_params = {
        "engine": "google",
        "q": "test",
        "num": 1,
        "api_key": target_key
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get("https://serpapi.com/search.json", params=test_params, headers=headers)
            raw_json = {}
            try:
                raw_json = resp.json()
            except Exception:
                pass

            api_error = raw_json.get("error") if isinstance(raw_json, dict) else None

            if resp.status_code == 200:
                if api_error:
                    err_msg = str(api_error)
                    status_code = "invalid_key" if ("api_key" in err_msg.lower() or "invalid" in err_msg.lower() or "key" in err_msg.lower()) else "error"
                    await _update_serp_status(db, org_id, status_code, f"SerpApi error: {err_msg}")
                    return {
                        "status": status_code,
                        "success": False,
                        "provider": "serpapi",
                        "capabilities": _get_provider_capabilities("serpapi", is_active=False),
                        "message": f"SerpApi test failed: {err_msg}"
                    }

                await _update_serp_status(db, org_id, "connected", "SerpApi account verified and active.")
                return {
                    "status": "connected",
                    "success": True,
                    "provider": "serpapi",
                    "capabilities": _get_provider_capabilities("serpapi", is_active=True),
                    "message": "SerpApi connection test passed successfully!"
                }
            elif resp.status_code in (401, 403):
                detail_msg = str(api_error) if api_error else f"HTTP {resp.status_code}: Invalid API key or access forbidden."
                await _update_serp_status(db, org_id, "invalid_key", f"SerpApi authentication failed: {detail_msg}")
                return {
                    "status": "invalid_key",
                    "success": False,
                    "provider": "serpapi",
                    "capabilities": _get_provider_capabilities("serpapi", is_active=False),
                    "error_code": "INVALID_API_KEY",
                    "message": f"SerpApi authentication failed: {detail_msg}"
                }
            elif resp.status_code == 429:
                detail_msg = str(api_error) if api_error else "SerpApi search quota exceeded."
                await _update_serp_status(db, org_id, "quota_exceeded", detail_msg)
                return {
                    "status": "quota_exceeded",
                    "success": False,
                    "provider": "serpapi",
                    "capabilities": _get_provider_capabilities("serpapi", is_active=False),
                    "error_code": "QUOTA_EXCEEDED",
                    "message": f"Your SerpApi account limit reached: {detail_msg}"
                }
            else:
                msg = str(api_error) if api_error else f"SerpApi returned HTTP {resp.status_code}"
                await _update_serp_status(db, org_id, "error", msg)
                return {
                    "status": "error",
                    "success": False,
                    "provider": "serpapi",
                    "capabilities": _get_provider_capabilities("serpapi", is_active=False),
                    "message": msg
                }
    except Exception as e:
        logger.error(f"[SERP] connection_test status=error organization={org_id} error={e}")
        return {
            "status": "error",
            "success": False,
            "provider": "serpapi",
            "capabilities": _get_provider_capabilities("serpapi", is_active=False),
            "message": f"Unable to reach SerpApi: {str(e)}"
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
