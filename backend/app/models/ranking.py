from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
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
    
    center_name = Column(String(255), default="City Center")
    center_lat = Column(Float, nullable=False)
    center_lng = Column(Float, nullable=False)
    radius_km = Column(Float, default=10.0)
    grid_size = Column(Integer, default=5)  # 5x5 grid
    
    average_rank = Column(Float, nullable=True)
    local_visibility_pct = Column(Float, default=0.0)
    
    # Real execution statistics
    scan_status = Column(String(50), default="completed")  # completed, completed_with_errors, failed
    total_points = Column(Integer, default=25)
    successful_points = Column(Integer, default=0)
    failed_points = Column(Integer, default=0)
    
    # Grid pins matrix data
    grid_points = Column(JSON, default=list)
    scanned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="geo_grid_scans")
    keyword_rel = relationship("Keyword", back_populates="grid_scans")
