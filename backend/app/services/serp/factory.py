from typing import Optional
from app.config import settings
from app.services.serp.base import SERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.mock_provider import MockSERPProvider

def get_serp_provider(provider_type: Optional[str] = None) -> SERPProvider:
    """
    Factory function to retrieve the configured SERP Provider.
    Defaults to SerpApiProvider initialized with settings.SERPAPI_KEY.
    """
    selected = (provider_type or getattr(settings, "SERP_PROVIDER", "serpapi")).lower()

    if selected == "mock":
        env = getattr(settings, "ENVIRONMENT", "production").lower()
        if env == "production":
            raise RuntimeError("CRITICAL: MockSERPProvider is strictly prohibited in production mode. Configure SERPAPI_KEY.")
        return MockSERPProvider()

    # Default to SerpApi
    api_key = getattr(settings, "SERPAPI_KEY", "")
    return SerpApiProvider(api_key=api_key)

