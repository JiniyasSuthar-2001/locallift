import logging
from typing import Optional
from app.config import settings
from app.services.serp.base import SERPProvider, SERPResponse
from app.services.serp.openserp import OpenSERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.mock_provider import MockSERPProvider

logger = logging.getLogger("locallift.serp.factory")


class FallbackSERPProvider(SERPProvider):
    """
    Composite SERP Provider that attempts the primary provider first (OpenSERP),
    and falls back to secondary provider (SerpApi) if primary fails and fallback is enabled.
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

        # If primary failed and fallback secondary is configured, try fallback
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


def get_serp_provider(
    provider_type: Optional[str] = None,
    allow_fallback: bool = True
) -> SERPProvider:
    """
    Factory function to retrieve the configured SERP Provider.
    - Default is self-hosted OpenSERPProvider.
    - If SERP_FALLBACK_PROVIDER is 'serpapi' and allow_fallback is True, wraps in FallbackSERPProvider.
    - MockSERPProvider is strictly restricted to test environments (ENVIRONMENT == 'testing').
    """
    selected = (provider_type or getattr(settings, "SERP_PROVIDER", "openserp")).lower()

    if selected == "mock":
        env = getattr(settings, "ENVIRONMENT", "production").lower()
        if env != "testing":
            raise RuntimeError(
                f"CRITICAL: MockSERPProvider is strictly prohibited in '{env}' mode. "
                "Mock SERP data is reserved exclusively for the 'testing' environment. "
                "Configure OpenSERP or SerpApi."
            )
        return MockSERPProvider()

    if selected == "serpapi":
        api_key = getattr(settings, "SERPAPI_KEY", "")
        return SerpApiProvider(api_key=api_key)

    # Primary: OpenSERP
    openserp_prov = OpenSERPProvider(
        base_url=getattr(settings, "OPENSERP_BASE_URL", "http://127.0.0.1:7000"),
        timeout=getattr(settings, "OPENSERP_TIMEOUT", 30),
        default_engine=getattr(settings, "OPENSERP_DEFAULT_ENGINE", "google")
    )

    fallback_choice = getattr(settings, "SERP_FALLBACK_PROVIDER", "").lower()
    if allow_fallback and fallback_choice == "serpapi":
        serpapi_key = getattr(settings, "SERPAPI_KEY", "")
        fallback_prov = SerpApiProvider(api_key=serpapi_key) if serpapi_key else None
        return FallbackSERPProvider(primary=openserp_prov, secondary=fallback_prov)

    return openserp_prov
