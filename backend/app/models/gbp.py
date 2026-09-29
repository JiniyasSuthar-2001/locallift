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
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    google_connection_id = Column(Integer, ForeignKey("google_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    google_account_id = Column(Integer, ForeignKey("google_accounts.id", ondelete="CASCADE"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    
    account_id = Column(String(255), nullable=True)
    account_resource_name = Column(String(255), nullable=True)
    location_name = Column(String(255), nullable=True)
    location_resource_name = Column(String(255), nullable=True, index=True)
    place_id = Column(String(255), nullable=True, index=True)
    maps_uri = Column(String(1000), nullable=True)
    
    business_name = Column(String(255), nullable=False)
    primary_category = Column(String(255), nullable=True, default="Local Business")
    additional_categories = Column(JSON, default=list)
    
    address = Column(String(500), nullable=True)
    storefront_address = Column(JSON, default=dict)
    address_lines = Column(JSON, default=list)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True)
    
    phone = Column(String(50), nullable=True)
    website_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    opening_hours = Column(JSON, default=dict)
    regular_hours = Column(JSON, default=dict)
    special_hours = Column(JSON, default=list)
    service_areas = Column(JSON, default=list)
    attributes = Column(JSON, default=dict)
    services = Column(JSON, default=list)
    products = Column(JSON, default=list)
    photos_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    
    completeness_score = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    status = Column(String(50), default="CONNECTED")
    sync_status = Column(String(50), default="idle")
    sync_error = Column(Text, nullable=True)
    
    # Performance metrics (Owner-Authorized; None if uncollected/disconnected)
    search_impressions = Column(Integer, nullable=True, default=None)
    maps_impressions = Column(Integer, nullable=True, default=None)
    website_clicks = Column(Integer, nullable=True, default=None)
    call_clicks = Column(Integer, nullable=True, default=None)
    direction_requests = Column(Integer, nullable=True, default=None)
    
    last_synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="gbp_profile")
    google_account = relationship("GoogleAccount", back_populates="gbp_profiles")
    google_connection = relationship("GoogleConnection", lazy="selectin")
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

class GooglePostObservation(Base):
    """
    Publicly observed Google business posts / updates.
    """
    __tablename__ = "google_post_observations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    business_identifier = Column(String(255), nullable=True)
    post_type = Column(String(50), default="UPDATE")  # UPDATE, OFFER, EVENT
    content_summary = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)
    published_at = Column(DateTime, nullable=True)
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    source = Column(String(100), default="Public Business Observation")

    project = relationship("Project", back_populates="post_observations")

class GoogleObservedChange(Base):
    """
    Publicly observed business profile attribute changes over time.
    """
    __tablename__ = "google_observed_changes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    source = Column(String(100), default="Public Search Observation")
    confidence = Column(String(50), default="Observed")

    project = relationship("Project", back_populates="observed_changes")


class PublicObservationSnapshot(Base):
    """
    Historical observation snapshot capturing the exact moment, completeness,
    and metadata when public Google Places / Maps data was retrieved.
    """
    __tablename__ = "public_observation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    provider = Column(String(100), default="Google Places API", nullable=False)
    place_id = Column(String(255), nullable=True, index=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    status = Column(String(50), default="FOUND", nullable=False)  # FOUND, NOT_FOUND, NOT_CONFIGURED, PROVIDER_ERROR, PARTIAL
    completeness = Column(String(50), default="COMPLETE", nullable=False)  # COMPLETE, PARTIAL, NOT_AVAILABLE
    fields_returned = Column(JSON, default=list)
    reviews_returned = Column(Integer, nullable=True, default=None)
    errors = Column(Text, nullable=True)
    provider_metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="public_observation_snapshots")


