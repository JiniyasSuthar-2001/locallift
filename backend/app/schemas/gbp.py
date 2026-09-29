from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class GBPProfileOut(BaseModel):
    id: int
    google_account_id: int
    location_id: Optional[int] = None
    account_id: Optional[str] = None
    location_name: Optional[str] = None
    business_name: str
    primary_category: str
    additional_categories: List[str] = []
    address: Optional[str] = None
    phone: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    opening_hours: Dict[str, Any] = {}
    special_hours: List[Any] = []
    attributes: Dict[str, Any] = {}
    services: List[str] = []
    products: List[str] = []
    photos_count: int = 0
    posts_count: int = 0
    completeness_score: int = 0
    is_verified: bool = False
    search_impressions: Optional[int] = None
    maps_impressions: Optional[int] = None
    website_clicks: Optional[int] = None
    call_clicks: Optional[int] = None
    direction_requests: Optional[int] = None
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GBPChangeOut(BaseModel):
    id: int
    gbp_profile_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    detected_at: datetime

    class Config:
        from_attributes = True

class GBPOAuthURLResponse(BaseModel):
    auth_url: str
    is_configured: bool
    redirect_uri: str

class GBPOAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None
    project_id: Optional[int] = None

class GBPStatusResponse(BaseModel):
    is_connected: bool
    is_configured: bool
    account_email: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    profiles_count: int = 0
    message: Optional[str] = None

class GBPSyncResponse(BaseModel):
    message: str
    status: str
    profiles_synced: int
    changes_detected: int
    last_synced_at: datetime


class ProductOrServiceItemOut(BaseModel):
    id: str
    type: str  # "product" or "service"
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    price_range: Optional[str] = None
    image_url: Optional[str] = None
    photo_urls: Optional[List[str]] = []
    action_url: Optional[str] = None
    action_type: Optional[str] = None
    source: str = "GOOGLE_BUSINESS_PROFILE"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    price_range: Optional[str] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    action_type: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    price_range: Optional[str] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    action_type: Optional[str] = None


class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    price_range: Optional[str] = None
    action_url: Optional[str] = None
    action_type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    price_range: Optional[str] = None
    action_url: Optional[str] = None
    action_type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class BulkProductsServicesImport(BaseModel):
    products: Optional[List[ProductCreate]] = []
    services: Optional[List[ServiceCreate]] = []


class ProductsServicesResponseOut(BaseModel):
    business_name: str
    place_id: Optional[str] = None
    is_connected: bool = False
    connected_account: Optional[str] = None
    total_products: int = 0
    total_services: int = 0
    last_synced_at: Optional[str] = None
    sync_status: Optional[str] = "NOT_SYNCED"  # SYNCED, PARTIAL, FAILED, NOT_AVAILABLE, CACHED, NOT_SYNCED
    sync_message: Optional[str] = None
    can_sync: bool = False
    items: List[ProductOrServiceItemOut] = []


