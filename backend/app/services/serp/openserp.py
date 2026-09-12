import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx

from app.config import settings
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem

logger = logging.getLogger("locallift.serp.openserp")


class OpenSERPProvider(SERPProvider):
    """
    Self-hosted OpenSERP provider (https://openserp.org / https://github.com/karust/openserp).
    Connects to a self-hosted OpenSERP microservice instance on Docker/local network.
    Does not require any third-party API key.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        default_engine: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None
    ):
        self.base_url = (base_url or getattr(settings, "OPENSERP_BASE_URL", "http://127.0.0.1:7000")).rstrip("/")
        self.timeout = timeout or getattr(settings, "OPENSERP_TIMEOUT", 30)
        self.default_engine = default_engine or getattr(settings, "OPENSERP_DEFAULT_ENGINE", "google")
        self._custom_client = client

    @property
    def is_configured(self) -> bool:
        """Self-hosted OpenSERP requires only a valid base URL; no API key is required."""
        return bool(self.base_url)

    async def check_health(self) -> Dict[str, Any]:
        """
        Performs a health check against the OpenSERP server.
        Returns connection status, latency, and details.
        """
        if not self.is_configured:
            return {
                "status": "NOT CONFIGURED",
                "provider": "openserp",
                "base_url": self.base_url,
                "message": "OpenSERP base URL is not configured."
            }

        start_time = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # OpenSERP provides /ready or root endpoint
                res = await client.get(f"{self.base_url}/ready")
                latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                if res.status_code == 200:
                    return {
                        "status": "CONNECTED",
                        "provider": "openserp",
                        "base_url": self.base_url,
                        "default_engine": self.default_engine,
                        "latency_ms": round(latency_ms, 2),
                        "message": "OpenSERP server is running and ready."
                    }
                else:
                    return {
                        "status": "UNAVAILABLE",
                        "provider": "openserp",
                        "base_url": self.base_url,
                        "status_code": res.status_code,
                        "message": f"OpenSERP server returned HTTP {res.status_code}."
                    }
        except httpx.TimeoutException:
            return {
                "status": "TIMEOUT",
                "provider": "openserp",
                "base_url": self.base_url,
                "message": f"Connection to OpenSERP timed out after 5 seconds."
            }
        except Exception as e:
            return {
                "status": "UNAVAILABLE",
                "provider": "openserp",
                "base_url": self.base_url,
                "message": f"Could not connect to OpenSERP server at {self.base_url}: {str(e)}"
            }

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        """
        Queries OpenSERP for organic search results.
        Maps location, country, language, and search depth into normalized SERPResponse.
        """
        if not self.is_configured:
            return SERPResponse(
                provider="openserp",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_NOT_CONFIGURED",
                error_message="OpenSERP base URL is not configured."
            )

        query_text = keyword
        if location and location.strip():
            # Include localized context if location is specified
            query_text = f"{keyword} {location}".strip()

        params = {
            "text": query_text,
            "limit": min(num_results, 100),
            "lang": language or "en"
        }
        if country:
            params["region"] = country.lower()

        engine = self.default_engine.lower() if self.default_engine else "google"
        endpoint = f"{self.base_url}/{engine}/search"

        try:
            if self._custom_client:
                response = await self._custom_client.get(endpoint, params=params, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(endpoint, params=params)

            if response.status_code == 429:
                logger.warning(f"OpenSERP rate limit reached for keyword: {keyword}")
                return SERPResponse(
                    provider="openserp",
                    keyword=keyword,
                    location=location,
                    success=False,
                    error_code="SERP_PROVIDER_RATE_LIMIT",
                    error_message="Search engine rate limit or CAPTCHA detected by OpenSERP."
                )
            elif response.status_code in (403, 401):
                logger.warning(f"OpenSERP request blocked (HTTP {response.status_code}) for keyword: {keyword}")
                return SERPResponse(
                    provider="openserp",
                    keyword=keyword,
                    location=location,
                    success=False,
                    error_code="SERP_PROVIDER_BLOCKED",
                    error_message=f"Search engine request blocked (HTTP {response.status_code})."
                )
            elif response.status_code != 200:
                logger.error(f"OpenSERP HTTP error {response.status_code}: {response.text}")
                return SERPResponse(
                    provider="openserp",
                    keyword=keyword,
                    location=location,
                    success=False,
                    error_code="SERP_PROVIDER_HTTP_ERROR",
                    error_message=f"OpenSERP returned HTTP {response.status_code}."
                )

            data = response.json()
            return self._normalize_openserp_response(data, keyword=keyword, location=location)

        except httpx.TimeoutException:
            logger.warning(f"OpenSERP request timed out for keyword: {keyword}")
            return SERPResponse(
                provider="openserp",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_TIMEOUT",
                error_message=f"OpenSERP query timed out after {self.timeout} seconds."
            )
        except Exception as e:
            logger.error(f"OpenSERP query failed for keyword '{keyword}': {e}")
            return SERPResponse(
                provider="openserp",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_UNAVAILABLE",
                error_message=f"OpenSERP connection failed: {str(e)}"
            )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        """
        Executes a localized search for a GeoGrid coordinate point using OpenSERP.
        """
        loc_str = location_name or f"{lat:.5f},{lng:.5f}"
        return await self.search_keyword(
            keyword=keyword,
            location=loc_str,
            country="us",
            language="en"
        )

    def _normalize_openserp_response(
        self,
        data: Any,
        keyword: str,
        location: Optional[str]
    ) -> SERPResponse:
        """
        Normalizes raw OpenSERP output into the standard SERPResponse and SERPItem model.
        OpenSERP can return a list of items or a dict with a 'results' key.
        """
        raw_items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            raw_items = data.get("results") or data.get("items") or []

        organic_results: List[SERPItem] = []
        local_pack_results: List[SERPItem] = []

        for idx, item in enumerate(raw_items, 1):
            title = item.get("title") or ""
            link = item.get("url") or item.get("link") or ""
            snippet = item.get("description") or item.get("snippet") or ""

            # Extract domain cleanly
            domain = ""
            if link:
                try:
                    parsed = urllib.parse.urlparse(link)
                    domain = parsed.netloc.lower()
                    if domain.startswith("www."):
                        domain = domain[4:]
                except Exception:
                    domain = ""

            pos = item.get("rank") or item.get("position") or idx

            serp_item = SERPItem(
                position=int(pos),
                title=title,
                link=link,
                domain=domain,
                snippet=snippet,
                item_type="organic"
            )
            organic_results.append(serp_item)

        return SERPResponse(
            provider="openserp",
            keyword=keyword,
            location=location,
            organic_results=organic_results,
            local_pack_results=local_pack_results,
            total_results_count=len(organic_results),
            success=True,
            raw_data={"count": len(raw_items)}
        )
