from typing import Optional, List, Dict
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem
from app.services.serp.matcher import DomainMatcher

class MockSERPProvider(SERPProvider):
    """
    Mock SERP Provider used for automated testing.
    Allows configuring preset results and simulated error conditions.
    """
    def __init__(self, preset_results: Optional[List[Dict]] = None, simulate_error: Optional[str] = None):
        self.preset_results = preset_results or []
        self.simulate_error = simulate_error

    @property
    def is_configured(self) -> bool:
        return True

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        if self.simulate_error == "timeout":
            return SERPResponse(
                provider="mock",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_TIMEOUT",
                error_message="Mock timeout."
            )
        if self.simulate_error == "rate_limit":
            return SERPResponse(
                provider="mock",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_RATE_LIMIT",
                error_message="Mock rate limit."
            )

        organic_items: List[SERPItem] = []
        local_items: List[SERPItem] = []

        if self.preset_results:
            for idx, res in enumerate(self.preset_results, 1):
                link = res.get("link", f"https://example{idx}.com")
                domain = DomainMatcher.normalize_host(link)
                item = SERPItem(
                    position=res.get("position", idx),
                    title=res.get("title", f"Result {idx}"),
                    link=link,
                    domain=domain,
                    snippet=res.get("snippet", ""),
                    item_type=res.get("type", "organic")
                )
                if item.item_type == "local_pack":
                    local_items.append(item)
                else:
                    organic_items.append(item)

        # When no preset results are provided, return clean empty lists (never inject fake fallback domains)
        return SERPResponse(
            provider="mock",
            keyword=keyword,
            location=location,
            organic_results=organic_items,
            local_pack_results=local_items,
            total_results_count=len(organic_items) + len(local_items),
            search_timestamp=datetime.now(timezone.utc),
            success=True
        )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        return await self.search_keyword(keyword, location=f"@{lat},{lng}")
