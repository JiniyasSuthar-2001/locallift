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
    search_impressions: int = 0
    maps_impressions: int = 0
    website_clicks: int = 0
    call_clicks: int = 0
    direction_requests: int = 0
    last_synced_at: datetime
    created_at: datetime

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
