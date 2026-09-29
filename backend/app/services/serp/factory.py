import logging
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.core.security import decrypt_token
from app.models.connections import OrganizationSERPConfig
from app.services.serp.base import SERPProvider, SERPResponse, NotConfiguredSERPProvider
from app.services.serp.openserp import OpenSERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.mock_provider import MockSERPProvider

logger = logging.getLogger("locallift.serp.factory")


NON_RETRYABLE_ERRORS = {
    "SERP_PROVIDER_AUTH_ERROR",
    "SERP_PROVIDER_NOT_CONFIGURED",
    "SERP_API_KEY_REQUIRED",
    "PROVIDER_GEO_GRID_UNSUPPORTED",
    "UNSUPPORTED_FEATURE",
    "INVALID_API_KEY",
    "QUOTA_EXHAUSTED",
}


class FallbackSERPProvider(SERPProvider):
    """
    Composite SERP Provider that attempts the primary provider first,
    and falls back to secondary provider ONLY for retryable errors (timeouts, 5xx, transient errors).
    """

    def __init__(self, primary: SERPProvider, secondary: Optional[SERPProvider] = None):
        self.primary = primary
        self.secondary = secondary

    @property
    def is_configured(self) -> bool:
        return self.primary.is_configured or (self.secondary is not None and self.secondary.is_configured)

    @property
    def capabilities(self):
        return self.primary.capabilities

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        res = await self.primary.search_keyword(
            keyword=keyword,
            location=location,
            country=country,
            language=language,
            device=device,
            num_results=num_results
        )
        res.primary_provider = self.primary.__class__.__name__
        if res.success:
            res.final_state = "success"
            return res

        res.primary_error = f"{res.error_code}: {res.error_message}"
        is_non_retryable = res.error_code in NON_RETRYABLE_ERRORS

        if not is_non_retryable and self.secondary and self.secondary.is_configured:
            logger.warning(
                f"SERP_PRIMARY_PROVIDER_FAILED (retryable): Provider '{self.primary.__class__.__name__}' "
                f"failed with code '{res.error_code}': {res.error_message}. Invoking fallback."
            )
            fallback_res = await self.secondary.search_keyword(
                keyword=keyword,
                location=location,
                country=country,
                language=language,
                device=device,
                num_results=num_results
            )
            fallback_res.primary_provider = self.primary.__class__.__name__
            fallback_res.primary_error = res.primary_error
            fallback_res.fallback_provider = self.secondary.__class__.__name__
            fallback_res.fallback_result = "success" if fallback_res.success else fallback_res.error_code
            fallback_res.final_state = "success" if fallback_res.success else (fallback_res.error_code or "provider_error")
            logger.info(f"SERP_FALLBACK_USED: Provider '{self.secondary.__class__.__name__}' executed fallback search.")
            return fallback_res

        res.final_state = res.error_code or "provider_error"
        return res

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        res = await self.primary.search_local_grid_point(
            keyword=keyword,
            lat=lat,
            lng=lng,
            location_name=location_name,
            zoom=zoom
        )
        res.primary_provider = self.primary.__class__.__name__
        if res.success:
            res.final_state = "success"
            return res

        res.primary_error = f"{res.error_code}: {res.error_message}"
        is_non_retryable = res.error_code in NON_RETRYABLE_ERRORS

        if not is_non_retryable and self.secondary and self.secondary.is_configured:
            logger.warning(
                f"SERP_PRIMARY_PROVIDER_FAILED (retryable): Local grid search with primary failed ({res.error_code}). Invoking fallback."
            )
            fallback_res = await self.secondary.search_local_grid_point(
                keyword=keyword,
                lat=lat,
                lng=lng,
                location_name=location_name,
                zoom=zoom
            )
            fallback_res.primary_provider = self.primary.__class__.__name__
            fallback_res.primary_error = res.primary_error
            fallback_res.fallback_provider = self.secondary.__class__.__name__
            fallback_res.fallback_result = "success" if fallback_res.success else fallback_res.error_code
            fallback_res.final_state = "success" if fallback_res.success else (fallback_res.error_code or "provider_error")
            logger.info(f"SERP_FALLBACK_USED: Local grid search fallback executed via '{self.secondary.__class__.__name__}'.")
            return fallback_res

        res.final_state = res.error_code or "provider_error"
        return res


from app.services.serp.registry import SERPProviderRegistry
from app.services.serp.adapters.base import SERPProviderAdapter


class AdapterSERPProviderWrapper(SERPProvider):
    """
    Seamless bridge that exposes any registered SERPProviderAdapter as a standard SERPProvider.
    """

    def __init__(self, adapter: SERPProviderAdapter, credentials: dict):
        self.adapter = adapter
        self.credentials = credentials

    @property
    def capabilities(self):
        return self.adapter.capabilities

    @property
    def is_configured(self) -> bool:
        return bool(self.credentials) and self.adapter.provider_id != "not_configured"

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        return await self.adapter.search_keyword(
            keyword=keyword,
            credentials=self.credentials,
            location=location,
            country=country,
            language=language,
            device=device,
            num_results=num_results
        )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        return await self.adapter.search_local_grid_point(
            keyword=keyword,
            credentials=self.credentials,
            lat=lat,
            lng=lng,
            location_name=location_name,
            zoom=zoom
        )


async def get_organization_serp_provider(
    db: Any,
    organization_id: Any
) -> SERPProvider:
    """
    Retrieves the SERP Provider configured specifically for an organization via the SERPProviderRegistry.
    """
    # Defensive handling if callers pass (organization_id, db)
    if isinstance(db, int) and not isinstance(organization_id, int):
        db, organization_id = organization_id, db

    adapter, credentials, config = await SERPProviderRegistry.resolve_for_org(db, organization_id)
    if adapter.provider_id == "not_configured" or not credentials:
        logger.debug(f"[SERP] provider=not_configured organization_id={organization_id}")
        return NotConfiguredSERPProvider()

    logger.info(f"[SERP] provider={adapter.provider_id} configured=true organization_id={organization_id}")
    return AdapterSERPProviderWrapper(adapter, credentials)


def get_serp_provider(
    provider_type: Optional[str] = None,
    allow_fallback: bool = True,
    api_key: Optional[str] = None
) -> SERPProvider:
    """
    Synchronous/static factory function for backwards compatibility & unit tests.
    """
    env = getattr(settings, "ENVIRONMENT", "production").lower()
    if provider_type == "mock":
        if env in ["production", "staging"]:
            raise RuntimeError(f"Mock SERP provider is strictly prohibited in environment '{env}'.")
        return MockSERPProvider()

    selected = (provider_type or getattr(settings, "SERP_PROVIDER", "serpapi")).lower()
    adapter = SERPProviderRegistry.get_adapter(selected)

    if selected == "serpapi" and api_key:
        return SerpApiProvider(api_key=api_key)
    elif selected == "openserp":
        base_url = getattr(settings, "OPENSERP_BASE_URL", "")
        if base_url:
            return OpenSERPProvider(base_url=base_url)

    if api_key:
        return AdapterSERPProviderWrapper(adapter, {"api_key": api_key})

    return NotConfiguredSERPProvider()
