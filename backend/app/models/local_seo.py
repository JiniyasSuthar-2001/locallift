import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from app.database import Base


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    OBSERVED = "OBSERVED"
    USER_PROVIDED = "USER_PROVIDED"
    DETECTED = "DETECTED"
    INFERRED = "INFERRED"
    NOT_VERIFIED = "NOT_VERIFIED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FindingStatus(str, enum.Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    NOT_VERIFIED = "NOT_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class CitationType(str, enum.Enum):
    EXISTING_VERIFIED = "EXISTING_VERIFIED"
    OBSERVED = "OBSERVED"
    USER_PROVIDED = "USER_PROVIDED"
    MISSING_OPPORTUNITY = "MISSING_OPPORTUNITY"
    NAP_CONFLICT = "NAP_CONFLICT"
    DUPLICATE = "DUPLICATE"
    NOT_VERIFIED = "NOT_VERIFIED"


class BusinessProfile(Base):
    """
    Canonical business profile for a project.
    Single source of truth for business identity, NAP, categories, coordinates, and local audit verification.
    """
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    business_name = Column(String(255), nullable=False)
    website = Column(String(500), nullable=True)
    primary_phone = Column(String(50), nullable=True)
    primary_address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    primary_category = Column(String(255), nullable=True)
    additional_categories = Column(JSON, default=list)
    service_area = Column(JSON, default=list)
    place_id = Column(String(255), nullable=True)
    maps_url = Column(String(1000), nullable=True)
    
    source = Column(String(50), default="USER_PROVIDED")  # USER_PROVIDED, GBP_SYNC, CRAWL_DETECTED
    verification_status = Column(String(50), default="NOT_VERIFIED")  # Uses VerificationStatus enum values
    last_verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="business_profile")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("uq_reviews_proj_src_ext_id", "project_id", "source", "external_review_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    external_review_id = Column(String(255), nullable=True, index=True)
    source = Column(String(50), default="Google", index=True)  # Google Places API, Google Business Profile, Facebook, Yelp
    author_name = Column(String(255), nullable=False)
    author_photo_url = Column(String(500), nullable=True)
    rating = Column(Integer, nullable=True, default=None)
    review_text = Column(Text, nullable=True)
    review_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    update_time = Column(DateTime, nullable=True)
    provider_url = Column(String(1000), nullable=True)
    provider_metadata = Column(JSON, default=dict)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    raw_provider_reference = Column(String(500), nullable=True)
    collection_status = Column(String(50), default="active")  # active, NO_LONGER_RETURNED_BY_PROVIDER
    access_mode = Column(String(50), default="PUBLIC")  # PUBLIC, OWNER_AUTHORIZED
    verification_status = Column(String(50), default="OBSERVED")  # OBSERVED, VERIFIED, NOT_VERIFIED
    
    # AI Response drafting with human approval
    response_text = Column(Text, nullable=True)
    response_status = Column(String(50), default="unanswered")  # unanswered, drafted, approved, published
    response_date = Column(DateTime, nullable=True)
    
    # Sentiment & NLP Topics (None if not analyzed)
    sentiment = Column(String(50), nullable=True, default=None)  # positive, neutral, negative, or None
    sentiment_score = Column(Float, nullable=True, default=None)
    topics = Column(JSON, default=list)  # ["Service Quality", "Staff", "Pricing"]
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="reviews")



class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    source_name = Column(String(255), nullable=False)  # Yelp, YellowPages, Bing Places, Apple Maps, etc.
    domain = Column(String(255), nullable=False)
    listing_url = Column(String(1000), nullable=True)
    domain_authority = Column(Integer, nullable=True, default=None)  # Truth in data: None if unknown, never fake 50
    category = Column(String(100), default="General Directory")
    
    status = Column(String(50), default="NOT_VERIFIED")  # listed, missing, incorrect, pending, NOT_VERIFIED
    nap_status = Column(String(50), default="not_checked")  # consistent, mismatch, missing, not_checked
    
    # Provenance & evidence tracking
    citation_type = Column(String(50), default="USER_PROVIDED")  # CitationType values
    verification_status = Column(String(50), default="NOT_VERIFIED")  # VerificationStatus values
    confidence = Column(Float, nullable=True)
    evidence = Column(JSON, default=dict)
    source_type = Column(String(50), default="manual")  # manual, public_search, directory_crawl
    
    found_name = Column(String(255), nullable=True)
    found_address = Column(String(500), nullable=True)
    found_phone = Column(String(50), nullable=True)
    found_website = Column(String(500), nullable=True)
    
    last_checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="citations")


class NAPRecord(Base):
    __tablename__ = "nap_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    canonical_name = Column(String(255), nullable=False)
    canonical_address = Column(String(500), nullable=False)
    canonical_phone = Column(String(50), nullable=False)
    canonical_website = Column(String(500), nullable=False)
    
    nap_score = Column(Integer, nullable=True, default=None)
    total_checked = Column(Integer, default=0)
    consistent_count = Column(Integer, default=0)
    mismatches_count = Column(Integer, default=0)
    
    mismatches_data = Column(JSON, default=list)
    last_audit_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="nap_records")


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    gbp_name = Column(String(255), nullable=True)
    place_id = Column(String(255), nullable=True)
    categories = Column(JSON, default=list)
    gbp_status = Column(String(50), nullable=True)
    
    rating = Column(Float, nullable=True, default=None)
    reviews_count = Column(Integer, default=0)
    citations_count = Column(Integer, default=0)
    backlinks_count = Column(Integer, default=0)
    local_visibility_score = Column(Integer, nullable=True, default=None)
    geo_grid_share_pct = Column(Float, nullable=True)
    top_keywords_count = Column(Integer, default=0)
    tracked_keywords_overlap = Column(JSON, default=list)
    avg_maps_rank = Column(Float, nullable=True, default=None)
    
    comparison_data = Column(JSON, default=dict)
    opportunities_found = Column(JSON, default=list)
    
    # Benchmarking & Discovery Provenance
    source = Column(String(50), default="manual")  # "manual", "geogrid", "manual_and_geogrid"
    website = Column(String(500), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    best_rank = Column(Integer, nullable=True)
    worst_rank = Column(Integer, nullable=True)
    grid_appearances = Column(Integer, default=0)
    keywords_found = Column(JSON, default=list)
    scans_data = Column(JSON, default=list)
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="competitors")


class SchemaRecord(Base):
    __tablename__ = "schema_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    page_url = Column(String(1000), nullable=False)
    schema_type = Column(String(100), default="LocalBusiness")  # LocalBusiness, Organization, Service, FAQPage
    page_type = Column(String(100), default="Homepage")
    business_type = Column(String(100), default="LocalBusiness")
    is_valid = Column(Boolean, default=True)
    quality_score = Column(Integer, default=0)
    score_breakdown = Column(JSON, default=dict)
    
    detected_types = Column(JSON, default=list)
    applicable_schemas = Column(JSON, default=dict)
    errors = Column(JSON, default=list)
    warnings = Column(JSON, default=list)
    missing_properties = Column(JSON, default=list)
    property_results = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    
    schema_source = Column(String(50), default="JSON-LD")  # JSON-LD, Microdata, RDFa, Generated
    schema_entities = Column(JSON, default=list)
    nap_status = Column(String(50), default="Consistent")  # Consistent, Mismatch, Not Applicable
    
    raw_json_ld = Column(Text, nullable=True)
    generated_json_ld = Column(Text, nullable=True)
    last_validated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="schema_records")

