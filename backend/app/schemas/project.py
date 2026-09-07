from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class LocationBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "United States"
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None

class LocationCreate(LocationBase):
    pass

class LocationOut(LocationBase):
    id: int
    project_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    name: str
    domain: str
    primary_category: Optional[str] = "Local Business"
    additional_categories: Optional[List[str]] = []
    country: Optional[str] = "United States"

class ProjectCreate(ProjectBase):
    organization_id: Optional[int] = None
    client_id: Optional[int] = None
    location: Optional[LocationCreate] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    primary_category: Optional[str] = None
    additional_categories: Optional[List[str]] = None
    country: Optional[str] = None
    client_id: Optional[int] = None

class ProjectOut(ProjectBase):
    id: int
    organization_id: int
    client_id: Optional[int] = None
    health_score: int
    technical_score: int
    onpage_score: int
    local_score: int
    gbp_score: int
    reviews_score: int
    citations_score: int
    keywords_score: int
    maps_score: int
    created_at: datetime
    updated_at: datetime
    locations: List[LocationOut] = []
    additional_categories: List[str] = []

    class Config:
        from_attributes = True

class DashboardSummaryOut(BaseModel):
    health_score: int
    scores: dict
    counts: dict
    recent_issues: List[Any]
    recent_tasks: List[Any]
    recent_reviews: List[Any]
    top_keywords: List[Any]
    gbp_summary: Optional[dict]
    gsc_summary: Optional[dict]
