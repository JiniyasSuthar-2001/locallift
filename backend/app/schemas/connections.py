from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class GoogleAdsAccountOut(BaseModel):
    id: int
    customer_id: str
    name: str
    currency_code: str
    time_zone: str
    status: str
    is_linked: bool
    created_at: datetime

    class Config:
        from_attributes = True

class GoogleSearchConsolePropertyOut(BaseModel):
    id: int
    site_url: str
    permission_level: str
    is_linked: bool
    created_at: datetime

    class Config:
        from_attributes = True

class GoogleAnalyticsPropertyOut(BaseModel):
    id: int
    property_id: str
    display_name: str
    account_name: str
    is_linked: bool
    created_at: datetime

    class Config:
        from_attributes = True

class DiscoveredGBPLocation(BaseModel):
    account_id: str
    location_id: str
    business_name: str
    primary_category: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website_url: Optional[str] = None
    is_verified: bool = False
    is_imported: bool = False

class GoogleConnectionStatusOut(BaseModel):
    is_connected: bool
    account_email: Optional[str] = None
    status: str
    scopes: List[str] = []
    last_sync_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    gbp_locations_count: int = 0
    ads_accounts_count: int = 0
    search_console_properties_count: int = 0
    analytics_properties_count: int = 0
    ads_accounts: List[GoogleAdsAccountOut] = []
    search_console_properties: List[GoogleSearchConsolePropertyOut] = []
    analytics_properties: List[GoogleAnalyticsPropertyOut] = []
    discovered_gbp_locations: List[DiscoveredGBPLocation] = []

class ImportResourcesRequest(BaseModel):
    project_id: Optional[int] = None
    selected_gbp_locations: Optional[List[DiscoveredGBPLocation]] = []
    selected_search_console_urls: Optional[List[str]] = []
    create_new_projects: bool = True

class ImportResourcesResponse(BaseModel):
    success: bool
    created_projects_count: int
    imported_locations_count: int
    imported_websites_count: int
    message: str

class PublicMapsImportRequest(BaseModel):
    maps_url: Optional[str] = None
    google_maps_url: Optional[str] = None
    business_name: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    target_category: Optional[str] = None
    project_id: Optional[int] = None

    def get_url(self) -> str:
        return (self.maps_url or self.google_maps_url or "").strip()

    def get_business_name(self) -> Optional[str]:
        return (self.business_name or self.name or "").strip() or None

    def get_category(self) -> Optional[str]:
        return (self.category or self.target_category or "").strip() or None

class PublicBusinessListingOut(BaseModel):
    id: int
    organization_id: int
    project_id: Optional[int] = None
    place_id: Optional[str] = None
    name: str
    formatted_address: Optional[str] = None
    phone: Optional[str] = None
    website_url: Optional[str] = None
    primary_category: str
    rating: Optional[float] = None
    review_count: int
    maps_url: Optional[str] = None
    is_managed: bool
    monitoring_status: str
    created_at: datetime

    class Config:
        from_attributes = True
