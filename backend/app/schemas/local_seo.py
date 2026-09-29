from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ReviewOut(BaseModel):
    id: int
    project_id: int
    external_review_id: Optional[str] = None
    source: str
    author_name: str
    author_photo_url: Optional[str] = None
    author_uri: Optional[str] = None
    rating: Optional[int] = None
    review_text: Optional[str] = None
    review_date: Optional[datetime] = None
    published_at: Optional[str] = None
    relative_publish_time_description: Optional[str] = None
    google_maps_uri: Optional[str] = None
    category: Optional[str] = None
    category_confidence: Optional[float] = None
    response_text: Optional[str] = None
    response_status: Optional[str] = "unanswered"  # unanswered, drafted, approved, published
    response_date: Optional[datetime] = None
    sentiment: Optional[str] = None  # positive, neutral, negative, or None
    sentiment_score: Optional[float] = None
    topics: Optional[Any] = []
    topic_list: Optional[List[str]] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PublicPlaceInfo(BaseModel):
    place_id: str
    name: str
    formatted_address: Optional[str] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    maps_url: Optional[str] = None
    website_url: Optional[str] = None
    last_synced_at: Optional[str] = None
    connected_google_account: Optional[str] = None


class PublicReviewSummary(BaseModel):
    total_google_reviews: int = 0
    reviews_available: int = 0
    average_rating: Optional[float] = None
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    categories_breakdown: Dict[str, int] = {}
    reviews_ordering: str = "Google Relevance"
    last_synced_at: Optional[str] = None
    connected_google_account: Optional[str] = None
    places_api_configured: bool = True
    has_place_id: bool = True


class PublicReviewsResponse(BaseModel):
    status: str
    error: Optional[str] = None
    place: Optional[PublicPlaceInfo] = None
    reviews: List[ReviewOut] = []
    summary: Optional[PublicReviewSummary] = None


class PlaceSelectRequest(BaseModel):
    project_id: int
    place_id: str
    name: Optional[str] = None
    formatted_address: Optional[str] = None
    maps_url: Optional[str] = None
    website_url: Optional[str] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ReviewDraftResponse(BaseModel):
    review_id: int
    custom_tone: Optional[str] = "professional_friendly"


class ReviewApprovePublish(BaseModel):
    response_text: str
    action: Optional[str] = "approved"

class CitationCreate(BaseModel):
    project_id: int
    directory_name: Optional[str] = None
    source_name: Optional[str] = None
    domain: Optional[str] = None
    listing_url: Optional[str] = None
    category: Optional[str] = "General Directory"
    domain_authority: Optional[int] = None
    status: Optional[str] = "NOT_VERIFIED"
    nap_status: Optional[str] = "not_checked"
    citation_type: Optional[str] = "USER_PROVIDED"
    verification_status: Optional[str] = "NOT_VERIFIED"
    confidence: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None
    source_type: Optional[str] = "manual"

class CitationOut(BaseModel):
    id: int
    project_id: int
    source_name: str
    domain: str
    listing_url: Optional[str] = None
    domain_authority: Optional[int] = None  # None if unknown, never fake 50
    category: str
    status: str  # listed, missing, incorrect, pending
    nap_status: str  # consistent, mismatch, missing
    citation_type: Optional[str] = "USER_PROVIDED"
    verification_status: Optional[str] = "NOT_VERIFIED"
    confidence: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = {}
    source_type: Optional[str] = "manual"
    found_name: Optional[str] = None
    found_address: Optional[str] = None
    found_phone: Optional[str] = None
    found_website: Optional[str] = None
    last_checked_at: datetime

    class Config:
        from_attributes = True

class CitationDistributionOut(BaseModel):
    health_score: int
    total_directories: int
    total_citations: Optional[int] = 0
    submitted_count: int
    approved_count: int
    verified_count: Optional[int] = 0
    observed_count: Optional[int] = 0
    mismatch_count: Optional[int] = 0
    unable_to_verify_count: Optional[int] = 0
    pending_count: int
    rejected_count: int
    failed_count: int
    nap_consistency_pct: int
    missing_count: int
    completion_pct: int
    last_scanned_at: Optional[datetime] = None
    canonical_profile: Optional[Dict[str, Any]] = None
    nap_comparisons: Optional[List[Dict[str, Any]]] = []
    citations: List[CitationOut]

class CitationStatusUpdate(BaseModel):
    status: str
    nap_status: Optional[str] = None
    listing_url: Optional[str] = None

class CompetitorCreate(BaseModel):
    project_id: int
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    gbp_name: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = 0
    place_id: Optional[str] = None
    categories: Optional[List[str]] = []
    category: Optional[str] = None
    gbp_status: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = "manual"


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
    website: Optional[str] = None
    gbp_name: Optional[str] = None
    place_id: Optional[str] = None
    categories: List[str] = []
    gbp_status: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: int = 0
    citations_count: int = 0
    backlinks_count: int = 0
    local_visibility_score: Optional[int] = None
    geo_grid_share_pct: Optional[float] = None
    top_keywords_count: int = 0
    tracked_keywords_overlap: List[str] = []
    avg_maps_rank: Optional[float] = None
    source: str = "manual"
    address: Optional[str] = None
    phone: Optional[str] = None
    best_rank: Optional[int] = None
    worst_rank: Optional[int] = None
    grid_appearances: int = 0
    keywords_found: List[str] = []
    scans_data: List[Dict[str, Any]] = []
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    comparison_data: Dict[str, Any] = {}
    opportunities_found: List[Any] = []

    class Config:
        from_attributes = True


class CompetitorCandidateOut(BaseModel):
    title: str
    domain: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    place_id: Optional[str] = None
    source: str = "local_pack"
    position: Optional[int] = None
    category: Optional[str] = None
    is_already_tracked: bool = False


class CompetitorSearchRequest(BaseModel):
    project_id: int
    query: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None


class CompetitorSearchResponse(BaseModel):
    query: str
    location: Optional[str] = None
    total_found: int
    results: List[CompetitorCandidateOut] = []



class BusinessProfileBase(BaseModel):
    business_name: str
    website: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    primary_category: Optional[str] = None
    additional_categories: List[str] = []
    service_area: List[str] = []
    place_id: Optional[str] = None
    maps_url: Optional[str] = None


class BusinessProfileCreate(BusinessProfileBase):
    project_id: int
    source: Optional[str] = "USER_PROVIDED"
    verification_status: Optional[str] = "NOT_VERIFIED"


class BusinessProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    website: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    primary_category: Optional[str] = None
    additional_categories: Optional[List[str]] = None
    service_area: Optional[List[str]] = None
    place_id: Optional[str] = None
    maps_url: Optional[str] = None
    source: Optional[str] = None
    verification_status: Optional[str] = None


class BusinessProfileOut(BusinessProfileBase):
    id: int
    project_id: int
    source: str
    verification_status: str
    last_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

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
    quality_score: Optional[int] = None
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
    business_name: Optional[str] = None
    business_type: str = "LocalBusiness"
    url: Optional[str] = None
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
    # Universal support
    custom_properties: Optional[Dict[str, Any]] = None
    connected_entities: Optional[List[Dict[str, Any]]] = None

class SchemaValidateRequest(BaseModel):
    json_ld: str
    project_id: Optional[int] = None

class SchemaValidateUrlRequest(BaseModel):
    url: str
    project_id: Optional[int] = None

class SchemaDraftSaveRequest(BaseModel):
    project_id: int
    page_url: str
    schema_type: str
    generated_json_ld: str
    entities: Optional[List[Dict[str, Any]]] = None

class SchemaValidateResponse(BaseModel):
    is_valid: bool
    syntax_valid: Optional[bool] = True
    errors: List[str] = []
    warnings: List[str] = []
    entities: List[str] = []
    rich_results: Optional[List[Dict[str, Any]]] = []
    nap_status: Optional[str] = "Consistent"

class SchemaIntelligenceSummaryOut(BaseModel):
    project_id: int
    domain: str
    health_score: int
    score_breakdown: Dict[str, int]
    deductions: List[str] = []
    stats: Dict[str, int]
    tier_1_status: Dict[str, Dict[str, Any]]
    tier1_coverage: Optional[List[Dict[str, Any]]] = None
    industry_type: str
    records: List[SchemaRecordOut]
    recommendations: List[Dict[str, Any]]

