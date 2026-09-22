from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    keyword = Column(String(255), nullable=False)
    search_intent = Column(String(50), default="Commercial")  # Informational, Commercial, Navigational, Transactional
    search_volume = Column(Integer, nullable=True, default=None)
    difficulty = Column(Integer, nullable=True, default=None)
    target_location = Column(String(255), nullable=True)
    
    current_rank = Column(Integer, nullable=True)
    previous_rank = Column(Integer, nullable=True)
    target_rank = Column(Integer, nullable=True, default=None)
    ranking_url = Column(String(1000), nullable=True)
    serp_type = Column(String(50), default="Local Pack")  # Local Pack, Organic, Featured Snippet
    
    opportunity_score = Column(String(20), nullable=True, default=None)  # HIGH, MEDIUM, LOW
    business_relevance = Column(String(20), default="High")
    
    last_checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="keywords")
    rank_history = relationship("KeywordRanking", back_populates="keyword_rel", cascade="all, delete-orphan")
    grid_scans = relationship("GeoGridScan", back_populates="keyword_rel", cascade="all, delete-orphan")

class KeywordRanking(Base):
    __tablename__ = "keyword_rankings"

    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    location_name = Column(String(255), nullable=False)
    rank_position = Column(Integer, nullable=True)
    serp_type = Column(String(50), default="Local Pack")
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    keyword_rel = relationship("Keyword", back_populates="rank_history")

class GeoGridScan(Base):
    __tablename__ = "geo_grid_scans"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    
    center_name = Column(String(255), nullable=True, default=None)
    center_lat = Column(Float, nullable=False)
    center_lng = Column(Float, nullable=False)
    radius_km = Column(Float, default=10.0)
    grid_size = Column(Integer, default=5)  # 5x5 grid
    
    average_rank = Column(Float, nullable=True)
    local_visibility_pct = Column(Float, default=0.0)
    
    # Real execution statistics
    scan_status = Column(String(50), default="completed")  # completed, completed_with_errors, failed
    total_points = Column(Integer, default=25)
    completed_points = Column(Integer, default=0)
    ranking_found_points = Column(Integer, default=0)
    not_found_points = Column(Integer, default=0)
    provider_error_points = Column(Integer, default=0)
    timeout_points = Column(Integer, default=0)
    successful_points = Column(Integer, default=0)
    failed_points = Column(Integer, default=0)
    
    # Grid pins matrix data (JSON cache for legacy/fast rendering)
    grid_points = Column(JSON, default=list)
    scanned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="geo_grid_scans")
    keyword_rel = relationship("Keyword", back_populates="grid_scans")
    point_results = relationship("GeoGridPointResult", back_populates="scan", cascade="all, delete-orphan")


class GeoGridPointResult(Base):
    __tablename__ = "geo_grid_point_results"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("geo_grid_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False, index=True)
    
    point_number = Column(Integer, nullable=False)  # 0 to 24
    row = Column(Integer, nullable=True)
    col = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    keyword = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)  # SUCCESS, NOT_FOUND, PROVIDER_ERROR, TIMEOUT
    rank = Column(Integer, nullable=True)
    
    matched_business = Column(String(255), nullable=True)
    matched_place_id = Column(String(255), nullable=True)
    matched_domain = Column(String(255), nullable=True)
    ranking_url = Column(String(1000), nullable=True)
    
    searched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("scan_id", "point_number", name="uq_geo_grid_scan_point"),
    )

    scan = relationship("GeoGridScan", back_populates="point_results")
    project = relationship("Project")
    keyword_rel = relationship("Keyword")

class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    country = Column(String(10), default="us")
    language = Column(String(10), default="en")
    device = Column(String(20), default="desktop")
    provider = Column(String(50), nullable=False)
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    position = Column(Integer, nullable=True)
    ranking_url = Column(String(1000), nullable=True)
    serp_features = Column(JSON, default=list)
    status = Column(String(50), default="success")  # success, failed, error
    error_message = Column(Text, nullable=True)

    keyword_rel = relationship("Keyword")
