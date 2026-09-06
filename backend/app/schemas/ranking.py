from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class KeywordBase(BaseModel):
    keyword: str
    search_intent: Optional[str] = "Commercial"
    search_volume: Optional[int] = 0
    difficulty: Optional[int] = 30
    target_location: Optional[str] = "City Center"
    target_rank: Optional[int] = 3
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
    opportunity_score: str = "HIGH"
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
    project_id: int
    keyword_id: int
    center_name: str
    center_lat: float
    center_lng: float
    radius_km: float
    grid_size: int
    average_rank: float
    local_visibility_pct: float
    grid_points: List[Any]
    scan_status: Optional[str] = "completed"
    total_points: Optional[int] = 25
    successful_points: Optional[int] = 25
    failed_points: Optional[int] = 0
    scanned_at: datetime

    class Config:
        from_attributes = True

class GeoGridScanRequest(BaseModel):
    keyword_id: Optional[int] = None
    center_name: Optional[str] = "City Center"
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: Optional[float] = 10.0
    grid_size: Optional[int] = 5
