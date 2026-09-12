import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.services.serp.openserp import OpenSERPProvider
from app.services.serp.factory import get_serp_provider

logger = logging.getLogger("locallift.api.serp")
router = APIRouter(prefix="/serp", tags=["serp"])


class SERPHealthResponse(BaseModel):
    provider: str
    status: str
    base_url: str
    default_engine: str
    fallback_provider: Optional[str] = None
    fallback_configured: bool = False
    latency_ms: Optional[float] = None
    message: str


class SERPTestRequest(BaseModel):
    base_url: Optional[str] = None
    engine: Optional[str] = "google"


@router.get("/health", response_model=SERPHealthResponse)
async def get_serp_health(
    current_user: User = Depends(get_current_user)
) -> SERPHealthResponse:
    """
    Checks the connectivity and status of the primary OpenSERP provider.
    Accessible to authenticated users.
    """
    prov = OpenSERPProvider()
    health = await prov.check_health()
    
    fallback_name = getattr(settings, "SERP_FALLBACK_PROVIDER", "serpapi")
    has_serpapi_key = bool(getattr(settings, "SERPAPI_KEY", ""))

    return SERPHealthResponse(
        provider="openserp",
        status=health.get("status", "UNAVAILABLE"),
        base_url=prov.base_url,
        default_engine=prov.default_engine,
        fallback_provider=fallback_name if fallback_name else None,
        fallback_configured=has_serpapi_key,
        latency_ms=health.get("latency_ms"),
        message=health.get("message", "")
    )


@router.get("/config")
async def get_serp_config(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Returns non-sensitive SERP provider configuration details.
    """
    return {
        "provider": settings.SERP_PROVIDER,
        "base_url": settings.OPENSERP_BASE_URL,
        "timeout": settings.OPENSERP_TIMEOUT,
        "default_engine": settings.OPENSERP_DEFAULT_ENGINE,
        "fallback_provider": settings.SERP_FALLBACK_PROVIDER,
        "has_fallback_key": bool(settings.SERPAPI_KEY)
    }


@router.post("/test-connection")
async def test_serp_connection(
    req: SERPTestRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Tests live connection to a specified OpenSERP base URL.
    """
    url = req.base_url or settings.OPENSERP_BASE_URL
    prov = OpenSERPProvider(base_url=url, default_engine=req.engine or "google")
    health = await prov.check_health()
    return health
