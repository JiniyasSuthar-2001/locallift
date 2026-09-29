import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class JobType(str, enum.Enum):
    KEYWORD_RANK = "keyword_rank"
    GEO_GRID = "geo_grid"
    CITATION_DISCOVERY = "citation_discovery"
    WEBSITE_AUDIT = "website_audit"
    INTELLIGENCE_SCAN = "intelligence_scan"


class ScanJob(Base):
    """
    Central Authoritative Background Scan Job Model.
    Tracks all long-running asynchronous scans with strict project ownership,
    5-minute execution ceiling, cancellation controls, and metric accounting.
    """
    __tablename__ = "scan_jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    job_type = Column(String(50), nullable=False, index=True)  # JobType enum value
    status = Column(String(50), default=JobStatus.QUEUED.value, nullable=False, index=True)
    provider = Column(String(50), nullable=True)
    current_stage = Column(String(255), default="Queued for execution")

    # Item Counters
    total_items = Column(Integer, default=0, nullable=False)
    processed_items = Column(Integer, default=0, nullable=False)
    successful_items = Column(Integer, default=0, nullable=False)
    failed_items = Column(Integer, default=0, nullable=False)
    not_found_items = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)

    # Resource Accounting
    token_usage = Column(Integer, default=0, nullable=False)
    point_usage = Column(Integer, default=0, nullable=False)
    progress_pct = Column(Float, default=0.0, nullable=False)

    # Job Parameters and Output Summary
    parameters = Column(JSON, default=dict)
    results_summary = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)

    # Lifecycle Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project")
    organization = relationship("Organization")
    user = relationship("User")
    usage_records = relationship("ProviderUsageRecord", back_populates="job", cascade="all, delete-orphan")
