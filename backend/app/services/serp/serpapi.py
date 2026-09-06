import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem
from app.services.serp.matcher import DomainMatcher

logger = logging.getLogger("locallift.serp.serpapi")

class SerpApiProvider(SERPProvider):
    BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        """Executes a real Google Search query via SerpApi."""
        if not self.is_configured:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_NOT_CONFIGURED",
                error_message="SerpApi key is not configured. Set SERPAPI_KEY in .env."
            )

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "engine": "google",
            "q": keyword,
            "gl": country.lower() if country else "us",
            "hl": language.lower() if language else "en",
            "device": device,
            "num": min(num_results, 100),
            "output": "json"
        }
        if location:
            params["location"] = location

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                logger.info(f"Executing SERP lookup for keyword='{keyword}' location='{location}' gl='{country}'")
                response = await client.get(self.BASE_URL, params=params)

                if response.status_code in (401, 403):
                    logger.error("SerpApi authentication error.")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code="SERP_PROVIDER_AUTH_ERROR",
                        error_message="Invalid or unauthorized SerpApi key."
                    )

                if response.status_code == 429:
                    logger.warning("SerpApi rate limit reached.")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code="SERP_PROVIDER_RATE_LIMIT",
                        error_message="SerpApi account quota exceeded or rate limited."
                    )

                if response.status_code != 200:
                    logger.error(f"SerpApi returned status {response.status_code}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message=f"SerpApi error: HTTP {response.status_code}"
                    )

                data = response.json()
                return self._parse_google_serp_response(data, keyword, location)

        except httpx.TimeoutException:
            logger.error("SerpApi request timed out.")
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_TIMEOUT",
                error_message="SERP request timed out."
            )
        except Exception as e:
            logger.error(f"SerpApi request failed: {str(e)}")
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_EXCEPTION",
                error_message=f"SERP lookup failed: {str(e)[:150]}"
            )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        """Executes a Google Maps / Local search for a discrete geo-grid coordinate."""
        if not self.is_configured:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=False,
                error_code="SERP_PROVIDER_NOT_CONFIGURED",
                error_message="SerpApi key is not configured. Set SERPAPI_KEY in .env."
            )

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "engine": "google_maps",
            "q": keyword,
            "ll": f"@{lat},{lng},{zoom}z",
            "type": "search",
            "output": "json"
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                logger.info(f"Executing Geo-Grid point search keyword='{keyword}' coords=({lat}, {lng})")
                response = await client.get(self.BASE_URL, params=params)

                if response.status_code in (401, 403):
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_AUTH_ERROR",
                        error_message="Invalid SerpApi credentials."
                    )

                if response.status_code == 429:
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_RATE_LIMIT",
                        error_message="Rate limited on Geo-Grid query."
                    )

                if response.status_code != 200:
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message=f"HTTP {response.status_code}"
                    )

                data = response.json()
                return self._parse_google_maps_response(data, keyword, f"@{lat},{lng}")

        except httpx.TimeoutException:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=False,
                error_code="SERP_PROVIDER_TIMEOUT",
                error_message="Geo-Grid request timed out."
            )
        except Exception as e:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=False,
                error_code="SERP_PROVIDER_EXCEPTION",
                error_message=str(e)[:150]
            )

    def _parse_google_serp_response(self, data: Dict[str, Any], keyword: str, location: Optional[str]) -> SERPResponse:
        organic_items: List[SERPItem] = []
        local_items: List[SERPItem] = []

        # 1. Parse Organic results
        raw_organic = data.get("organic_results", [])
        for pos, item in enumerate(raw_organic, 1):
            link = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            domain = DomainMatcher.normalize_host(link)

            organic_items.append(
                SERPItem(
                    position=item.get("position", pos),
                    title=title,
                    link=link,
                    domain=domain,
                    snippet=snippet,
                    item_type="organic"
                )
            )

        # 2. Parse Local Pack results if present
        raw_local = data.get("local_results", {}).get("places", [])
        if not raw_local and isinstance(data.get("local_results"), list):
            raw_local = data.get("local_results")

        for pos, place in enumerate(raw_local, 1):
            link = place.get("links", {}).get("website") or place.get("website") or place.get("link") or ""
            title = place.get("title", "")
            address = place.get("address", "")
            phone = place.get("phone", "")
            rating = place.get("rating")
            reviews = place.get("reviews")
            domain = DomainMatcher.normalize_host(link)

            local_items.append(
                SERPItem(
                    position=place.get("position", pos),
                    title=title,
                    link=link,
                    domain=domain,
                    item_type="local_pack",
                    rating=float(rating) if rating is not None else None,
                    reviews_count=int(reviews) if reviews is not None else None,
                    phone=phone,
                    address=address
                )
            )

        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            location=location,
            organic_results=organic_items,
            local_pack_results=local_items,
            total_results_count=len(organic_items) + len(local_items),
            search_timestamp=datetime.now(timezone.utc),
            success=True,
            raw_data=data
        )

    def _parse_google_maps_response(self, data: Dict[str, Any], keyword: str, location: Optional[str]) -> SERPResponse:
        local_items: List[SERPItem] = []
        raw_places = data.get("local_results", [])

        for pos, place in enumerate(raw_places, 1):
            link = place.get("website") or place.get("link") or ""
            title = place.get("title", "")
            address = place.get("address", "")
            phone = place.get("phone", "")
            rating = place.get("rating")
            reviews = place.get("reviews")
            domain = DomainMatcher.normalize_host(link)

            local_items.append(
                SERPItem(
                    position=place.get("position", pos),
                    title=title,
                    link=link,
                    domain=domain,
                    item_type="local_pack",
                    rating=float(rating) if rating is not None else None,
                    reviews_count=int(reviews) if reviews is not None else None,
                    phone=phone,
                    address=address
                )
            )

        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            location=location,
            organic_results=[],
            local_pack_results=local_items,
            total_results_count=len(local_items),
            search_timestamp=datetime.now(timezone.utc),
            success=True,
            raw_data=data
        )
