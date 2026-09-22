from pydantic import BaseModel, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime

class KeywordBase(BaseModel):
    keyword: str
    search_intent: Optional[str] = "Commercial"
    search_volume: Optional[int] = None
    difficulty: Optional[int] = None
    target_location: Optional[str] = None
    target_rank: Optional[int] = None
    business_relevance: Optional[str] = "High"

class KeywordCreate(KeywordBase):
    project_id: int

class KeywordOut(KeywordBase):
    id: int
    project_id: int
    current_rank: Optional[int] = None
    previous_rank: Optional[int] = None
    ranking_url: Optional[str] = None
    serp_type: str = "Local Pack"
    opportunity_score: Optional[str] = None
    last_checked_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class KeywordCheckResponse(BaseModel):
    keyword_id: int
    keyword: str
    target_domain: str
    current_rank: Optional[int] = None
    previous_rank: Optional[int] = None
    rank_movement: Optional[int] = None
    ranking_url: Optional[str] = None
    serp_type: str = "Local Pack"
    provider: str = "serpapi"
    status: str = "checked"  # checked, not_found, provider_error, not_configured
    error_message: Optional[str] = None
    last_checked_at: datetime

class KeywordCheckAllResponse(BaseModel):
    project_id: int
    checked_count: int
    not_found_count: int
    error_count: int
    provider: str
    results: List[KeywordCheckResponse]
    checked_at: datetime

class GeoGridScanOut(BaseModel):
    id: int
    scan_id: Optional[int] = None
    project_id: int
    keyword_id: int
    keyword: Optional[str] = None
    center_name: Optional[str] = "Business Location"
    center_lat: float
    center_lng: float
    radius_km: float
    grid_size: int
    average_rank: Optional[float] = None
    local_visibility_pct: float = 0.0
    grid_points: List[Any]
    points: Optional[List[Any]] = None
    scan_status: str
    total_points: int
    completed_points: Optional[int] = 0
    ranking_found_points: Optional[int] = 0
    not_found_points: Optional[int] = 0
    provider_error_points: Optional[int] = 0
    timeout_points: Optional[int] = 0
    successful_points: int
    failed_points: int
    provider: Optional[Dict[str, Any]] = None
    center: Optional[Dict[str, float]] = None
    scanned_at: datetime

    class Config:
        from_attributes = True

class GeoGridScanRequest(BaseModel):
    keyword_id: Optional[int] = None
    keyword: Optional[str] = None
    location_id: Optional[int] = None
    center_name: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: Optional[float] = 10.0
    grid_size: Optional[int] = 5

    @field_validator("center_lat")
    def validate_center_lat(cls, v):
        if v is not None and not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return v

    @field_validator("center_lng")
    def validate_center_lng(cls, v):
        if v is not None and not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return v
