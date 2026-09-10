from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    source = Column(String(50), default="Google")  # Google, Facebook, Yelp
    author_name = Column(String(255), nullable=False)
    author_photo_url = Column(String(500), nullable=True)
    rating = Column(Integer, default=5)
    review_text = Column(Text, nullable=True)
    review_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # AI Response drafting with human approval
    response_text = Column(Text, nullable=True)
    response_status = Column(String(50), default="unanswered")  # unanswered, drafted, approved, published
    response_date = Column(DateTime, nullable=True)
    
    # Sentiment & NLP Topics
    sentiment = Column(String(50), default="positive")  # positive, neutral, negative
    sentiment_score = Column(Float, default=0.9)
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
    domain_authority = Column(Integer, nullable=True, default=None)
    category = Column(String(100), default="General Directory")
    
    status = Column(String(50), default="listed")  # listed, missing, incorrect, pending
    nap_status = Column(String(50), default="consistent")  # consistent, mismatch, missing
    
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
    
    rating = Column(Float, nullable=True, default=None)
    reviews_count = Column(Integer, default=0)
    local_visibility_score = Column(Integer, nullable=True, default=None)
    top_keywords_count = Column(Integer, default=0)
    avg_maps_rank = Column(Float, nullable=True, default=None)
    
    comparison_data = Column(JSON, default=dict)
    opportunities_found = Column(JSON, default=list)
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
