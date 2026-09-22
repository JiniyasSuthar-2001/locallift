from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class SERPCapabilities(BaseModel):
    organic_search: bool = False
    local_search: bool = False
    maps_search: bool = False
    coordinate_search: bool = False
    geo_grid: bool = False

class SERPItem(BaseModel):
    position: int
    title: str
    link: str = ""
    domain: str = ""
    snippet: Optional[str] = None
    item_type: str = "organic"  # organic, local_pack, featured_snippet, ad
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    place_id: Optional[str] = None
    data_cid: Optional[str] = None

class SERPResponse(BaseModel):
    provider: str
    keyword: str
    location: Optional[str] = None
    organic_results: List[SERPItem] = Field(default_factory=list)
    local_pack_results: List[SERPItem] = Field(default_factory=list)
    total_results_count: int = 0
    search_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    primary_provider: Optional[str] = None
    primary_error: Optional[str] = None
    fallback_provider: Optional[str] = None
    fallback_result: Optional[str] = None
    final_state: Optional[str] = None

class SERPProvider(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> SERPCapabilities:
        """Returns explicitly declared provider capabilities."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has valid API credentials or endpoint configured."""
        pass

    @abstractmethod
    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        """Search a keyword and return normalized organic and local pack results."""
        pass

    @abstractmethod
    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        """Search Google Local/Maps at specific coordinates."""
        pass

    async def search_organic(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        """Unified method for organic web search."""
        return await self.search_keyword(keyword, location, country, language, device, num_results)

    async def search_local(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en"
    ) -> SERPResponse:
        """Unified method for local pack search."""
        return await self.search_keyword(keyword, location, country, language, num_results=20)

    async def search_maps(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en"
    ) -> SERPResponse:
        """Unified method for Google Maps search."""
        return await self.search_keyword(keyword, location, country, language, num_results=20)

    async def search_at_location(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        """Unified method for GPS coordinate-based local search."""
        return await self.search_local_grid_point(keyword, lat, lng, location_name, zoom)


class NotConfiguredSERPProvider(SERPProvider):
    """
    Safe provider returned when no SERP API key has been configured for the organization.
    Never attempts Docker or localhost calls. Returns a clean, user-facing error state.
    """

    @property
    def capabilities(self) -> SERPCapabilities:
        return SERPCapabilities()

    @property
    def is_configured(self) -> bool:
        return False

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        return SERPResponse(
            provider="not_configured",
            keyword=keyword,
            location=location,
            success=False,
            error_code="SERP_PROVIDER_NOT_CONFIGURED",
            error_message="SERP provider not configured. Add your SerpApi key in Settings to enable keyword tracking and Geo-Grid searches."
        )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        return SERPResponse(
            provider="not_configured",
            keyword=keyword,
            location=location_name,
            success=False,
            error_code="SERP_PROVIDER_NOT_CONFIGURED",
            error_message="SERP provider not configured. Add your SerpApi key in Settings to enable keyword tracking and Geo-Grid searches."
        )
