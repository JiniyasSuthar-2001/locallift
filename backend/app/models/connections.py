from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class GoogleConnection(Base):
    __tablename__ = "google_connections"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    
    account_email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    scopes = Column(JSON, default=list)
    
    status = Column(String(50), default="connected")  # connected, disconnected, expired, error
    last_sync_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sync_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization")
    project = relationship("Project")
    ads_accounts = relationship("GoogleAdsAccount", back_populates="connection", cascade="all, delete-orphan")
    search_console_properties = relationship("GoogleSearchConsoleProperty", back_populates="connection", cascade="all, delete-orphan")
    analytics_properties = relationship("GoogleAnalyticsProperty", back_populates="connection", cascade="all, delete-orphan")

class GoogleAdsAccount(Base):
    __tablename__ = "google_ads_accounts"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("google_connections.id", ondelete="CASCADE"), nullable=False)
    
    customer_id = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    currency_code = Column(String(10), default="USD")
    time_zone = Column(String(50), default="America/New_York")
    status = Column(String(50), default="ENABLED")
    is_linked = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    connection = relationship("GoogleConnection", back_populates="ads_accounts")

class GoogleSearchConsoleProperty(Base):
    __tablename__ = "google_search_console_properties"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("google_connections.id", ondelete="CASCADE"), nullable=False)
    
    site_url = Column(String(500), nullable=False, index=True)
    permission_level = Column(String(50), default="siteOwner")  # siteOwner, siteFullUser, siteRestrictedUser
    is_linked = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    connection = relationship("GoogleConnection", back_populates="search_console_properties")

class GoogleAnalyticsProperty(Base):
    __tablename__ = "google_analytics_properties"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("google_connections.id", ondelete="CASCADE"), nullable=False)
    
    property_id = Column(String(50), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    account_name = Column(String(255), nullable=False)
    is_linked = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    connection = relationship("GoogleConnection", back_populates="analytics_properties")

class PublicBusinessListing(Base):
    __tablename__ = "public_business_listings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    
    place_id = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    formatted_address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    website_url = Column(String(500), nullable=True)
    primary_category = Column(String(255), default="Local Business")
    
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True, default=None)
    maps_url = Column(String(1000), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    is_managed = Column(Boolean, default=False)
    monitoring_status = Column(String(50), default="active")  # active, paused
    last_checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization")
    project = relationship("Project")
