import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem, SERPCapabilities
from app.services.serp.matcher import DomainMatcher
from app.services.serp.normalizer import SERPNormalizer

logger = logging.getLogger("locallift.serp.serpapi")

class SerpApiProvider(SERPProvider):
    BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or "").strip().strip("'\"").strip()

    @property
    def capabilities(self) -> SERPCapabilities:
        if not self.is_configured:
            return SERPCapabilities()
        return SERPCapabilities(
            organic_search=True,
            local_search=True,
            maps_search=True,
            coordinate_search=True,
            geo_grid=True
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5 and not any(c in self.api_key for c in ("•", "*")))

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

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                logger.info(f"Executing SERP lookup for keyword='{keyword}' location='{location}' gl='{country}'")
                response = await client.get(self.BASE_URL, params=params, headers=headers)

                raw_json = {}
                try:
                    raw_json = response.json()
                except Exception:
                    pass

                api_err = raw_json.get("error") if isinstance(raw_json, dict) else None

                if response.status_code in (401, 403):
                    err_detail = str(api_err) if api_err else "SerpApi authentication error."
                    logger.error(f"SerpApi authentication error: {err_detail}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code="SERP_PROVIDER_AUTH_ERROR",
                        error_message=f"SerpApi rejected the API key: {err_detail}"
                    )

                if response.status_code == 429:
                    logger.warning("SerpApi rate limit reached.")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code="SERP_PROVIDER_RATE_LIMIT",
                        error_message="SerpApi rate limit reached. Please wait and try again."
                    )

                if response.status_code >= 500:
                    logger.error(f"SerpApi returned server status {response.status_code}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message="SerpApi is temporarily unavailable. Please try again shortly."
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
                error_message="SerpApi did not respond in time. Please try again."
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

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                logger.info(f"Executing Geo-Grid point search keyword='{keyword}' coords=({lat}, {lng})")
                response = await client.get(self.BASE_URL, params=params, headers=headers)

                raw_json = {}
                try:
                    raw_json = response.json()
                except Exception:
                    pass

                api_err = raw_json.get("error") if isinstance(raw_json, dict) else None

                if response.status_code in (401, 403):
                    err_detail = str(api_err) if api_err else "SerpApi authentication error."
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_AUTH_ERROR",
                        error_message=f"SerpApi rejected the API key: {err_detail}"
                    )

                if response.status_code == 429:
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_RATE_LIMIT",
                        error_message="SerpApi rate limit reached. Please wait and try again."
                    )

                if response.status_code >= 500:
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message="SerpApi is temporarily unavailable. Please try again shortly."
                    )

                if response.status_code != 200:
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=f"@{lat},{lng}",
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message=f"SerpApi error: HTTP {response.status_code}"
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
            place_id = place.get("place_id") or place.get("data_id")
            data_cid = place.get("data_cid") or str(place.get("cid", "")) or None
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
                    address=address,
                    place_id=place_id,
                    data_cid=data_cid
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
            place_id = place.get("place_id") or place.get("data_id")
            data_cid = place.get("data_cid") or str(place.get("cid", "")) or None
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
                    address=address,
                    place_id=place_id,
                    data_cid=data_cid
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
