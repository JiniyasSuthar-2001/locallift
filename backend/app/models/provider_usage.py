from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class ProviderUsageRecord(Base):
    """
    Authoritative Resource & Point Accounting Model.
    Tracks every external provider/token/point-consuming operation by project and job.
    Enables project-level vs. organization-wide usage analysis and quota tracking.
    """
    __tablename__ = "provider_usage_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("scan_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    provider = Column(String(50), nullable=False, index=True)  # serpapi, openserp, gemini, google_places, etc.
    operation = Column(String(100), nullable=False)  # keyword_serp_search, geo_grid_point, citation_query, etc.
    units_consumed = Column(Integer, default=1, nullable=False)
    cost_estimate = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="success", nullable=False)  # success, failed, cancelled
    details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    project = relationship("Project")
    organization = relationship("Organization")
    job = relationship("ScanJob", back_populates="usage_records")
