from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class GoogleAccount(Base):
    __tablename__ = "google_accounts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    account_email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    scopes = Column(JSON, default=list)
    is_connected = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="google_accounts")
    gbp_profiles = relationship("GoogleBusinessProfile", back_populates="google_account", cascade="all, delete-orphan")

class GoogleBusinessProfile(Base):
    __tablename__ = "google_business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    google_account_id = Column(Integer, ForeignKey("google_accounts.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    
    account_id = Column(String(255), nullable=True)
    location_name = Column(String(255), nullable=True)
    business_name = Column(String(255), nullable=False)
    primary_category = Column(String(255), nullable=False)
    additional_categories = Column(JSON, default=list)
    
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    website_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    
    opening_hours = Column(JSON, default=dict)
    special_hours = Column(JSON, default=list)
    attributes = Column(JSON, default=dict)
    services = Column(JSON, default=list)
    products = Column(JSON, default=list)
    photos_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    
    completeness_score = Column(Integer, default=85)
    is_verified = Column(Boolean, default=True)
    
    # Performance metrics
    search_impressions = Column(Integer, default=0)
    maps_impressions = Column(Integer, default=0)
    website_clicks = Column(Integer, default=0)
    call_clicks = Column(Integer, default=0)
    direction_requests = Column(Integer, default=0)
    
    last_synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    google_account = relationship("GoogleAccount", back_populates="gbp_profiles")
    location = relationship("Location", back_populates="gbp_profiles")
    changes = relationship("GBPChange", back_populates="gbp_profile", cascade="all, delete-orphan")

class GBPChange(Base):
    __tablename__ = "gbp_changes"

    id = Column(Integer, primary_key=True, index=True)
    gbp_profile_id = Column(Integer, ForeignKey("google_business_profiles.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    gbp_profile = relationship("GoogleBusinessProfile", back_populates="changes")
