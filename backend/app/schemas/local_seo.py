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

class CitationCreate(BaseModel):
    project_id: int
    directory_name: Optional[str] = None
    source_name: Optional[str] = None
    domain: Optional[str] = None
    listing_url: Optional[str] = None
    category: Optional[str] = "General Directory"
    domain_authority: Optional[int] = None
    status: Optional[str] = "listed"
    nap_status: Optional[str] = "match"

class CitationOut(BaseModel):
    id: int
    project_id: int
    source_name: str
    domain: str
    listing_url: Optional[str] = None
    domain_authority: Optional[int] = None
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

class CompetitorCreate(BaseModel):
    project_id: int
    name: str
    domain: Optional[str] = None
    gbp_name: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = 0


class NAPRecordOut(BaseModel):
    id: int
    project_id: int
    canonical_name: str
    canonical_address: str
    canonical_phone: str
    canonical_website: str
    nap_score: Optional[int] = None
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
    rating: Optional[float] = None
    reviews_count: int = 0
    local_visibility_score: Optional[int] = None
    top_keywords_count: int = 0
    avg_maps_rank: Optional[float] = None
    comparison_data: Dict[str, Any] = {}
    opportunities_found: List[Any] = []

    class Config:
        from_attributes = True

class SchemaRecordOut(BaseModel):
    id: int
    project_id: int
    page_url: str
    schema_type: str
    page_type: Optional[str] = "Homepage"
    business_type: Optional[str] = "LocalBusiness"
    is_valid: bool
    quality_score: Optional[int] = 85
    score_breakdown: Optional[Dict[str, Any]] = {}
    detected_types: List[str] = []
    applicable_schemas: Optional[Dict[str, Any]] = {}
    errors: List[str] = []
    warnings: List[str] = []
    missing_properties: Optional[List[str]] = []
    property_results: Optional[List[Dict[str, Any]]] = []
    recommendations: Optional[List[Dict[str, Any]]] = []
    schema_source: Optional[str] = "JSON-LD"
    schema_entities: Optional[List[Dict[str, Any]]] = []
    nap_status: Optional[str] = "Consistent"
    raw_json_ld: Optional[str] = None
    generated_json_ld: Optional[str] = None
    last_validated_at: datetime

    class Config:
        from_attributes = True

class SchemaGenerateRequest(BaseModel):
    business_name: str
    business_type: str = "LocalBusiness"
    url: str
    phone: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    opening_hours: Optional[List[Dict[str, Any]]] = None
    price_range: Optional[str] = None
    social_profiles: Optional[List[str]] = None
    service_name: Optional[str] = None
    service_description: Optional[str] = None
    breadcrumbs: Optional[List[Dict[str, str]]] = None
    include_graph: Optional[bool] = True

class SchemaValidateRequest(BaseModel):
    json_ld: str

class SchemaValidateResponse(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    entities: List[str] = []

class SchemaIntelligenceSummaryOut(BaseModel):
    project_id: int
    domain: str
    health_score: int
    score_breakdown: Dict[str, int]
    deductions: List[str] = []
    stats: Dict[str, int]
    tier_1_status: Dict[str, Dict[str, Any]]
    industry_type: str
    records: List[SchemaRecordOut]
    recommendations: List[Dict[str, Any]]
