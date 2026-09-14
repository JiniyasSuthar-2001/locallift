import logging
from typing import Optional
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


class FallbackSERPProvider(SERPProvider):
    """
    Composite SERP Provider that attempts the primary provider first,
    and falls back to secondary provider if primary fails and fallback is enabled.
    """

    def __init__(self, primary: SERPProvider, secondary: Optional[SERPProvider] = None):
        self.primary = primary
        self.secondary = secondary

    @property
    def is_configured(self) -> bool:
        return self.primary.is_configured or (self.secondary is not None and self.secondary.is_configured)

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
        if res.success:
            return res

        if self.secondary and self.secondary.is_configured:
            logger.warning(
                f"SERP_PRIMARY_PROVIDER_FAILED: Provider '{self.primary.__class__.__name__}' "
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
            logger.info(f"SERP_FALLBACK_USED: Provider '{self.secondary.__class__.__name__}' executed fallback search.")
            return fallback_res

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
        if res.success:
            return res

        if self.secondary and self.secondary.is_configured:
            logger.warning(
                f"SERP_PRIMARY_PROVIDER_FAILED: Local grid search with primary failed ({res.error_code}). Invoking fallback."
            )
            fallback_res = await self.secondary.search_local_grid_point(
                keyword=keyword,
                lat=lat,
                lng=lng,
                location_name=location_name,
                zoom=zoom
            )
            logger.info(f"SERP_FALLBACK_USED: Local grid search fallback executed via '{self.secondary.__class__.__name__}'.")
            return fallback_res

        return res


async def get_organization_serp_provider(
    db: AsyncSession,
    organization_id: int
) -> SERPProvider:
    """
    Retrieves the SERP Provider configured specifically for an organization.
    1. Checks OrganizationSERPConfig in DB. Decrypts organization SerpApi key if present.
    2. Fallback to global settings.SERPAPI_KEY if organization config missing.
    3. If provider is openserp and base_url is specified, uses OpenSERPProvider.
    4. Otherwise returns NotConfiguredSERPProvider (Never attempts Docker or localhost:7000).
    """
    env = getattr(settings, "ENVIRONMENT", "production").lower()
    if env == "testing":
        return MockSERPProvider()

    stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == organization_id)
    res = await db.execute(stmt)
    serp_config = res.scalars().first()

    if serp_config and serp_config.enabled:
        provider_name = (serp_config.provider or "serpapi").lower()
        if provider_name == "serpapi":
            raw_key = decrypt_token(serp_config.api_key) if serp_config.api_key else ""
            if raw_key:
                logger.info(f"[SERP] provider=serpapi configured=true organization_id={organization_id}")
                return SerpApiProvider(api_key=raw_key)
        elif provider_name == "openserp":
            base_url = settings.OPENSERP_BASE_URL
            if base_url:
                logger.info(f"[SERP] provider=openserp organization_id={organization_id}")
                return OpenSERPProvider(base_url=base_url)

    global_serpapi_key = getattr(settings, "SERPAPI_KEY", "")
    if global_serpapi_key:
        logger.info(f"[SERP] provider=serpapi_global_fallback organization_id={organization_id}")
        return SerpApiProvider(api_key=global_serpapi_key)

    logger.debug(f"[SERP] provider=not_configured organization_id={organization_id}")
    return NotConfiguredSERPProvider()


def get_serp_provider(
    provider_type: Optional[str] = None,
    allow_fallback: bool = True,
    api_key: Optional[str] = None
) -> SERPProvider:
    """
    Synchronous/static factory function for backwards compatibility & unit tests.
    Default is SerpApiProvider if key provided, else NotConfiguredSERPProvider.
    """
    env = getattr(settings, "ENVIRONMENT", "production").lower()
    if provider_type == "mock":
        if env in ["production", "staging"]:
            raise RuntimeError(f"Mock SERP provider is strictly prohibited in environment '{env}'.")
        return MockSERPProvider()

    if env == "testing":
        return MockSERPProvider()

    selected = (provider_type or getattr(settings, "SERP_PROVIDER", "serpapi")).lower()

    if selected == "serpapi":
        key = api_key or getattr(settings, "SERPAPI_KEY", "")
        if key:
            return SerpApiProvider(api_key=key)
        return NotConfiguredSERPProvider()

    if selected == "openserp":
        base_url = getattr(settings, "OPENSERP_BASE_URL", "")
        if base_url:
            return OpenSERPProvider(base_url=base_url)
        return NotConfiguredSERPProvider()

    return NotConfiguredSERPProvider()
