from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ReviewOut(BaseModel):
    id: int
    project_id: int
    source: str
    author_name: str
    author_photo_url: Optional[str] = None
    rating: int
    review_text: Optional[str] = None
    review_date: datetime
    response_text: Optional[str] = None
    response_status: str  # unanswered, drafted, approved, published
    response_date: Optional[datetime] = None
    sentiment: str  # positive, neutral, negative
    sentiment_score: float
    topics: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewDraftResponse(BaseModel):
    review_id: int
    custom_tone: Optional[str] = "professional_friendly"

class ReviewApprovePublish(BaseModel):
    response_text: str

class CitationOut(BaseModel):
    id: int
    project_id: int
    source_name: str
    domain: str
    listing_url: Optional[str] = None
    domain_authority: int
    category: str
    status: str  # listed, missing, incorrect, pending
    nap_status: str  # consistent, mismatch, missing
    found_name: Optional[str] = None
    found_address: Optional[str] = None
    found_phone: Optional[str] = None
    found_website: Optional[str] = None
    last_checked_at: datetime

    class Config:
        from_attributes = True

class NAPRecordOut(BaseModel):
    id: int
    project_id: int
    canonical_name: str
    canonical_address: str
    canonical_phone: str
    canonical_website: str
    nap_score: int
    total_checked: int
    consistent_count: int
    mismatches_count: int
    mismatches_data: List[Any] = []
    last_audit_date: datetime

    class Config:
        from_attributes = True

class CompetitorOut(BaseModel):
    id: int
    project_id: int
    name: str
    domain: str
    gbp_name: Optional[str] = None
    rating: float
    reviews_count: int
    local_visibility_score: int
    top_keywords_count: int
    avg_maps_rank: Optional[float] = 3.5
    comparison_data: Dict[str, Any] = {}
    opportunities_found: List[Any] = []

    class Config:
        from_attributes = True

class SchemaRecordOut(BaseModel):
    id: int
    project_id: int
    page_url: str
    schema_type: str
    is_valid: bool
    detected_types: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []
    raw_json_ld: Optional[str] = None
    generated_json_ld: Optional[str] = None
    last_validated_at: datetime

    class Config:
        from_attributes = True

class SchemaGenerateRequest(BaseModel):
    business_name: str
    business_type: str = "LocalBusiness"
    url: str
    phone: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str = "US"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    opening_hours: Optional[List[str]] = ["Mo-Fr 08:00-18:00"]
    price_range: Optional[str] = "$$"
