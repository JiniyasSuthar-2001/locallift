import json
import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.core.deps import get_current_user, get_user_organization_ids
from app.core.security import encrypt_token, decrypt_token
from app.models.user import User
from app.models.connections import OrganizationSERPConfig
from app.core.audit_logger import log_user_action
from app.services.serp.registry import SERPProviderRegistry
from app.services.serp.adapters.base import (
    SERPProviderAdapter,
    SERPNormalizedAccountInfo,
    SERPConnectionStatus,
    SERPUsageModel
)

logger = logging.getLogger("locallift.api.serp")
router = APIRouter(prefix="/serp", tags=["serp"])


# --- Schemas ---

class SERPConfigResponse(BaseModel):
    provider: str = "serpapi"
    provider_name: str = "SerpApi"
    base_url: Optional[str] = None
    auth_mode: str = "api_key"
    has_key: bool = False
    masked_key: Optional[str] = None
    masked_credentials: Dict[str, str] = Field(default_factory=dict)
    connection_status: str = "not_configured"
    status_message: Optional[str] = None
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    account_info: Dict[str, Any] = Field(default_factory=dict)
    usage_info: Dict[str, Any] = Field(default_factory=dict)
    last_tested_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None


class SERPSaveConfigRequest(BaseModel):
    provider: str = "serpapi"
    base_url: Optional[str] = None
    auth_mode: Optional[str] = "api_key"
    api_key: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None  # Dynamic multi-field credentials e.g. {"login": "...", "password": "..."}
    organization_id: Optional[int] = None


class SERPTestConnectionRequest(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    organization_id: Optional[int] = None


async def _resolve_org_id(user: User, db: AsyncSession, requested_org_id: Optional[int] = None) -> int:
    """
    Resolves and validates the active organization for the authenticated user.
    Strictly verifies organization membership to prevent cross-tenant access.
    """
    from app.models.user import OrganizationMember, Organization
    if requested_org_id is not None:
        if user.is_superuser:
            return requested_org_id
        mem_res = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == requested_org_id
            )
        )
        if not mem_res.scalars().first():
            raise HTTPException(status_code=403, detail="User does not have access to this organization.")
        return requested_org_id

    mem_res = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    mem = mem_res.scalars().first()
    if not mem:
        if user.is_superuser:
            org_res = await db.execute(select(Organization).limit(1))
            first_org = org_res.scalars().first()
            if first_org:
                return first_org.id
        raise HTTPException(status_code=400, detail="User has no associated organization.")
    return mem.organization_id


def _mask_value(raw_val: str) -> str:
    if not raw_val:
        return ""
    clean = raw_val.strip()
    if len(clean) <= 6:
        return "••••••••"
    return f"••••••••{clean[-4:]}"


@router.get("/providers")
async def list_available_serp_providers(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Returns list of active, supported SERP providers and their credential schemas for dynamic form rendering.
    """
    return SERPProviderRegistry.list_available_providers()


@router.get("/config", response_model=SERPConfigResponse)
async def get_serp_configuration(
    request: Request,
    org_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SERPConfigResponse:
    """
    Returns organization-specific SERP configuration, masked credentials, capabilities,
    and cached provider account & usage information. Never exposes raw secrets.
    """
    active_org_id = await _resolve_org_id(current_user, db, org_id)
    log_user_action(request, "OPEN_SERP_SETTINGS", user_id=current_user.id, organization_id=active_org_id)

    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == active_org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    if not serp_config:
        adapter = SERPProviderRegistry.get_adapter("serpapi")
        return SERPConfigResponse(
            provider="serpapi",
            provider_name=adapter.display_name,
            base_url=None,
            auth_mode="api_key",
            has_key=False,
            masked_key=None,
            masked_credentials={},
            connection_status="not_configured",
            capabilities=adapter.capabilities.dict(),
            account_info={},
            usage_info={"model": "not_configured", "usage_available": False},
            status_message="Connect your SERP provider account in Settings.",
            last_tested_at=None,
            last_synced_at=None
        )

    provider_id = serp_config.provider or "serpapi"
    adapter = SERPProviderRegistry.get_adapter(provider_id)
    unpacked_creds = SERPProviderRegistry.unpack_credentials(serp_config)

    raw_key = unpacked_creds.get("api_key", "")
    masked_creds = {}
    for k, v in unpacked_creds.items():
        if isinstance(v, str):
            masked_creds[k] = _mask_value(v) if k in ["api_key", "password", "secret", "token"] else v

    return SERPConfigResponse(
        provider=provider_id,
        provider_name=adapter.display_name,
        base_url=serp_config.base_url,
        auth_mode=serp_config.auth_mode or "api_key",
        has_key=bool(raw_key or unpacked_creds),
        masked_key=_mask_value(raw_key) if raw_key else None,
        masked_credentials=masked_creds,
        connection_status=serp_config.connection_status or "not_configured",
        status_message=serp_config.status_message,
        capabilities=serp_config.capabilities or adapter.capabilities.dict(),
        account_info=serp_config.account_info or {},
        usage_info=serp_config.usage_info or {"model": "not_configured", "usage_available": False},
        last_tested_at=serp_config.last_tested_at,
        last_synced_at=serp_config.last_synced_at
    )


@router.post("/config", response_model=SERPConfigResponse)
async def save_serp_configuration(
    request: Request,
    req: SERPSaveConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SERPConfigResponse:
    """
    Saves or updates organization SERP provider credentials (encrypted at rest).
    Automatically inspects the external provider account to retrieve real plan & usage data.
    Never returns raw credentials to the client.
    """
    org_id = await _resolve_org_id(current_user, db, req.organization_id)

    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    provider_choice = (req.provider or "serpapi").lower()
    adapter = SERPProviderRegistry.get_adapter(provider_choice)

    # Build clean credentials dict from request or preserve existing if masked
    existing_creds = SERPProviderRegistry.unpack_credentials(serp_config) if serp_config else {}
    submitted_creds: Dict[str, Any] = dict(req.credentials or {})

    if req.api_key:
        submitted_creds["api_key"] = req.api_key.strip().strip("'\"")
    if req.base_url:
        submitted_creds["base_url"] = req.base_url.strip()

    # Un-mask any preserved fields
    for k, v in submitted_creds.items():
        if isinstance(v, str) and any(c in v for c in ("•", "*")):
            if k in existing_creds:
                submitted_creds[k] = existing_creds[k]

    # Clean empty values
    clean_creds = {k: v.strip() if isinstance(v, str) else v for k, v in submitted_creds.items() if v is not None and v != ""}

    # Encrypt primary api_key and any extra credentials
    enc_api_key = encrypt_token(clean_creds.get("api_key", "")) if clean_creds.get("api_key") else None
    extra_creds_to_save = {k: v for k, v in clean_creds.items() if k not in ["api_key", "base_url"]}
    enc_extra = encrypt_token(json.dumps(extra_creds_to_save)) if extra_creds_to_save else None
    base_url_val = clean_creds.get("base_url")

    # Run live account inspection & validation
    account_info_norm = await adapter.get_account_info(clean_creds)

    now = datetime.now(timezone.utc)
    if not serp_config:
        serp_config = OrganizationSERPConfig(
            organization_id=org_id,
            provider=provider_choice,
            base_url=base_url_val,
            auth_mode=req.auth_mode or "api_key",
            api_key=enc_api_key,
            credentials_extra=enc_extra,
            capabilities=adapter.capabilities.dict(),
            account_info=account_info_norm.account.dict(),
            usage_info=account_info_norm.usage.dict(),
            connection_status=account_info_norm.connection_status,
            status_message=account_info_norm.status_message,
            last_tested_at=now,
            last_synced_at=now,
            last_sync_error=account_info_norm.sync_error
        )
        db.add(serp_config)
    else:
        serp_config.provider = provider_choice
        serp_config.base_url = base_url_val
        serp_config.auth_mode = req.auth_mode or "api_key"
        serp_config.api_key = enc_api_key
        serp_config.credentials_extra = enc_extra
        serp_config.capabilities = adapter.capabilities.dict()
        serp_config.account_info = account_info_norm.account.dict()
        serp_config.usage_info = account_info_norm.usage.dict()
        serp_config.connection_status = account_info_norm.connection_status
        serp_config.status_message = account_info_norm.status_message
        serp_config.last_tested_at = now
        serp_config.last_synced_at = now
        serp_config.last_sync_error = account_info_norm.sync_error

    await db.commit()
    await db.refresh(serp_config)

    log_user_action(
        request,
        "SAVE_SERP_CONFIGURATION",
        user_id=current_user.id,
        organization_id=org_id,
        status="success",
        provider=serp_config.provider,
        connection_status=serp_config.connection_status
    )

    unpacked_creds = SERPProviderRegistry.unpack_credentials(serp_config)
    raw_key = unpacked_creds.get("api_key", "")
    masked_creds = {k: _mask_value(v) if k in ["api_key", "password", "secret", "token"] else v for k, v in unpacked_creds.items() if isinstance(v, str)}

    return SERPConfigResponse(
        provider=serp_config.provider,
        provider_name=adapter.display_name,
        base_url=serp_config.base_url,
        auth_mode=serp_config.auth_mode or "api_key",
        has_key=bool(raw_key or unpacked_creds),
        masked_key=_mask_value(raw_key) if raw_key else None,
        masked_credentials=masked_creds,
        connection_status=serp_config.connection_status,
        status_message=serp_config.status_message,
        capabilities=serp_config.capabilities or adapter.capabilities.dict(),
        account_info=serp_config.account_info or {},
        usage_info=serp_config.usage_info or {},
        last_tested_at=serp_config.last_tested_at,
        last_synced_at=serp_config.last_synced_at
    )


@router.post("/test-connection")
async def test_serp_connection(
    request: Request,
    req: SERPTestConnectionRequest = SERPTestConnectionRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Tests live connection to the configured SERP provider, retrieves authoritative account info,
    and updates database metadata without executing unnecessary search credits.
    """
    org_id = await _resolve_org_id(current_user, db, req.organization_id)
    log_user_action(request, "TEST_SERP_CONNECTION", user_id=current_user.id, organization_id=org_id, status="started")

    # Load existing configuration
    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    provider_id = (req.provider or (serp_config.provider if serp_config else "serpapi")).lower()
    adapter = SERPProviderRegistry.get_adapter(provider_id)

    # Resolve credentials to test
    existing_creds = SERPProviderRegistry.unpack_credentials(serp_config) if serp_config else {}
    test_creds: Dict[str, Any] = dict(req.credentials or {})
    if req.api_key:
        test_creds["api_key"] = req.api_key.strip().strip("'\"")
    if req.base_url:
        test_creds["base_url"] = req.base_url.strip()

    # Fill in unmasked stored values if testing existing masked key
    for k, v in test_creds.items():
        if isinstance(v, str) and any(c in v for c in ("•", "*")) and k in existing_creds:
            test_creds[k] = existing_creds[k]

    if not test_creds:
        test_creds = existing_creds

    if not test_creds and adapter.provider_id != "not_configured":
        return {
            "status": "not_configured",
            "success": False,
            "provider": adapter.provider_id,
            "provider_name": adapter.display_name,
            "message": f"Credentials required to test {adapter.display_name} connection."
        }

    # Fetch normalized account & usage info from provider
    account_info_norm = await adapter.get_account_info(test_creds)
    now = datetime.now(timezone.utc)

    # Persist updated status and usage if config exists
    if serp_config:
        serp_config.connection_status = account_info_norm.connection_status
        serp_config.status_message = account_info_norm.status_message
        serp_config.account_info = account_info_norm.account.dict()
        serp_config.usage_info = account_info_norm.usage.dict()
        serp_config.capabilities = adapter.capabilities.dict()
        serp_config.last_tested_at = now
        serp_config.last_synced_at = now
        serp_config.last_sync_error = account_info_norm.sync_error
        await db.commit()

    is_success = account_info_norm.connection_status == SERPConnectionStatus.CONNECTED.value

    return {
        "status": account_info_norm.connection_status,
        "success": is_success,
        "provider": adapter.provider_id,
        "provider_name": adapter.display_name,
        "message": account_info_norm.status_message or ("Connection verified successfully!" if is_success else "Connection test failed."),
        "account": account_info_norm.account.dict(),
        "usage": account_info_norm.usage.dict(),
        "capabilities": adapter.capabilities.dict(),
        "last_synced_at": now.isoformat()
    }


@router.post("/refresh-usage")
async def refresh_serp_usage(
    request: Request,
    org_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Explicitly synchronizes external SERP provider account usage and plan details.
    """
    active_org_id = await _resolve_org_id(current_user, db, org_id)

    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == active_org_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    if not serp_config or not serp_config.enabled:
        return {
            "success": False,
            "status": "not_configured",
            "message": "SERP provider not configured for this organization.",
            "usage": {"model": "not_configured", "usage_available": False}
        }

    adapter = SERPProviderRegistry.get_adapter(serp_config.provider)
    creds = SERPProviderRegistry.unpack_credentials(serp_config)

    account_info_norm = await adapter.get_account_info(creds)
    now = datetime.now(timezone.utc)

    serp_config.connection_status = account_info_norm.connection_status
    serp_config.status_message = account_info_norm.status_message
    serp_config.account_info = account_info_norm.account.dict()
    serp_config.usage_info = account_info_norm.usage.dict()
    serp_config.last_synced_at = now
    serp_config.last_sync_error = account_info_norm.sync_error
    await db.commit()

    return {
        "success": account_info_norm.connection_status == SERPConnectionStatus.CONNECTED.value,
        "provider": adapter.provider_id,
        "provider_name": adapter.display_name,
        "account": serp_config.account_info,
        "usage": serp_config.usage_info,
        "last_synced_at": now.isoformat(),
        "message": "Usage metrics refreshed from provider." if account_info_norm.connection_status == "connected" else account_info_norm.status_message
    }
