from typing import Optional
from app.config import settings
from app.services.serp.base import SERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.mock_provider import MockSERPProvider

def get_serp_provider(provider_type: Optional[str] = None) -> SERPProvider:
    """
    Factory function to retrieve the configured SERP Provider.
    Defaults to SerpApiProvider initialized with settings.SERPAPI_KEY.
    MockSERPProvider is strictly restricted to test environments (ENVIRONMENT == 'testing').
    """
    selected = (provider_type or getattr(settings, "SERP_PROVIDER", "serpapi")).lower()

    if selected == "mock":
        env = getattr(settings, "ENVIRONMENT", "production").lower()
        if env != "testing":
            raise RuntimeError(
                f"CRITICAL: MockSERPProvider is strictly prohibited in '{env}' mode. "
                "Mock SERP data is reserved exclusively for the 'testing' environment. "
                "Configure SERPAPI_KEY or use the default unconfigured SerpApiProvider."
            )
        return MockSERPProvider()

    # Default to SerpApi (fails closed honestly with SERP_PROVIDER_NOT_CONFIGURED if SERPAPI_KEY is empty)
    api_key = getattr(settings, "SERPAPI_KEY", "")
    return SerpApiProvider(api_key=api_key)


