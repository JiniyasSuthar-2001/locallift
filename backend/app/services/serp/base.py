from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class SERPItem(BaseModel):
    position: int
    title: str
    link: str
    domain: str
    snippet: Optional[str] = None
    item_type: str = "organic"  # organic, local_pack, featured_snippet, ad
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    phone: Optional[str] = None
    address: Optional[str] = None

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

class SERPProvider(ABC):
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

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has valid API credentials configured."""
        pass


class NotConfiguredSERPProvider(SERPProvider):
    """
    Safe provider returned when no SERP API key has been configured for the organization.
    Never attempts Docker or localhost calls. Returns a clean, user-facing error state.
    """

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
            error_code="SERP_API_KEY_REQUIRED",
            error_message="SERP provider not configured. Add your SerpApi API key in Settings to enable keyword tracking and Geo-Grid searches."
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
            error_code="SERP_API_KEY_REQUIRED",
            error_message="SERP provider not configured. Add your SerpApi API key in Settings to enable keyword tracking and Geo-Grid searches."
        )

