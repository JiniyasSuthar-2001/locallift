from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    primary_category = Column(String(255), default="Local Business")
    additional_categories = Column(JSON, default=list)
    country = Column(String(50), default="United States")
    health_score = Column(Integer, default=78)
    
    # Detailed sub-scores
    technical_score = Column(Integer, default=85)
    onpage_score = Column(Integer, default=80)
    local_score = Column(Integer, default=75)
    gbp_score = Column(Integer, default=70)
    reviews_score = Column(Integer, default=88)
    citations_score = Column(Integer, default=72)
    keywords_score = Column(Integer, default=80)
    maps_score = Column(Integer, default=74)
    status = Column(String(50), default="active")  # active, archived
    is_archived = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="projects")
    client = relationship("Client", back_populates="projects")
    locations = relationship("Location", back_populates="project", cascade="all, delete-orphan")
    websites = relationship("Website", back_populates="project", cascade="all, delete-orphan")
    seo_audits = relationship("SEOAudit", back_populates="project", cascade="all, delete-orphan")
    seo_issues = relationship("SEOIssue", back_populates="project", cascade="all, delete-orphan")
    seo_tasks = relationship("SEOTask", back_populates="project", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="project", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="project", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="project", cascade="all, delete-orphan")
    nap_records = relationship("NAPRecord", back_populates="project", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="project", cascade="all, delete-orphan")
    schema_records = relationship("SchemaRecord", back_populates="project", cascade="all, delete-orphan")
    google_accounts = relationship("GoogleAccount", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")
    geo_grid_scans = relationship("GeoGridScan", back_populates="project", cascade="all, delete-orphan")
    team_memberships = relationship("ProjectMembership", back_populates="project", cascade="all, delete-orphan")
    invitations = relationship("ProjectInvitation", back_populates="project", cascade="all, delete-orphan")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), default="United States")
    phone = Column(String(50), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    place_id = Column(String(255), nullable=True)
    service_areas = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="locations")
    gbp_profiles = relationship("GoogleBusinessProfile", back_populates="location")

class Website(Base):
    __tablename__ = "websites"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(500), nullable=False)
    sitemap_url = Column(String(500), nullable=True)
    robots_url = Column(String(500), nullable=True)
    status = Column(String(50), default="ready")  # ready, crawling, completed, failed
    pages_crawled = Column(Integer, default=0)
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="websites")
    pages = relationship("WebsitePage", back_populates="website", cascade="all, delete-orphan")
