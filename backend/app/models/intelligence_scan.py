import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class ScanStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StageStatus(str, enum.Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    SKIPPED = "SKIPPED"


class ProjectIntelligenceScan(Base):
    """
    Central Local SEO Intelligence Scan lifecycle model.
    Tracks asynchronous execution across all 13 modules for a single project.
    """
    __tablename__ = "project_intelligence_scans"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(50), default=ScanStatus.QUEUED.value, index=True)
    current_stage = Column(String(100), default="queued")
    current_stage_label = Column(String(255), default="Scan queued for execution")
    progress_pct = Column(Float, default=0.0)
    completed_stages_count = Column(Integer, default=0)
    total_stages_count = Column(Integer, default=13)

    # JSON map of all module stages: { stage_key: { label, status, started_at, completed_at, records_found, records_saved, message, error } }
    stages = Column(JSON, default=dict)

    error_summary = Column(Text, nullable=True)
    results_summary = Column(JSON, default=dict)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", backref="intelligence_scans")
