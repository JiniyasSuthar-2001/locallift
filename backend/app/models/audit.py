import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from app.database import Base

class IssueSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    OPPORTUNITY = "opportunity"
    INFO = "info"

class IssueStatus(str, enum.Enum):
    OPEN = "open"
    IN_TASK = "in_task"
    RESOLVED = "resolved"
    IGNORED = "ignored"

class TaskStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    IGNORED = "ignored"
    RECHECK_REQUIRED = "recheck_required"

class TaskPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class WebsitePage(Base):
    __tablename__ = "website_pages"

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1000), nullable=False, index=True)
    status_code = Column(Integer, default=200)
    title = Column(String(500), nullable=True)
    meta_description = Column(Text, nullable=True)
    h1 = Column(String(500), nullable=True)
    h2_list = Column(JSON, default=list)
    word_count = Column(Integer, default=0)
    canonical_url = Column(String(1000), nullable=True)
    is_indexable = Column(Boolean, default=True)
    load_time_ms = Column(Integer, default=0)
    schema_types = Column(JSON, default=list)
    images_count = Column(Integer, default=0)
    missing_alt_count = Column(Integer, default=0)
    internal_links_count = Column(Integer, default=0)
    external_links_count = Column(Integer, default=0)
    broken_links = Column(JSON, default=list)
    issues_detected = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    website = relationship("Website", back_populates="pages")

class SEOAudit(Base):
    __tablename__ = "seo_audits"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    audit_type = Column(String(50), default="technical")  # technical, local, gbp, schema
    overall_score = Column(Integer, default=80)
    pages_analyzed = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    opportunities = Column(Integer, default=0)
    passed_checks = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="seo_audits")
    issues = relationship("SEOIssue", back_populates="audit", cascade="all, delete-orphan")

class SEOIssue(Base):
    __tablename__ = "seo_issues"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("seo_audits.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    category = Column(String(50), default="Technical SEO")  # Technical, On-Page, Local, GBP, Schema, Performance
    severity = Column(Enum(IssueSeverity), default=IssueSeverity.WARNING)
    title = Column(String(255), nullable=False)
    evidence = Column(Text, nullable=True)
    why_it_matters = Column(Text, nullable=True)
    recommended_solution = Column(Text, nullable=True)
    action_type = Column(String(100), default="manual_fix")  # generate_schema, add_service, fix_meta, etc.
    affected_url = Column(String(1000), nullable=True)
    status = Column(Enum(IssueStatus), default=IssueStatus.OPEN)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    audit = relationship("SEOAudit", back_populates="issues")
    project = relationship("Project", back_populates="seo_issues")
    tasks = relationship("SEOTask", back_populates="issue")

class SEOTask(Base):
    __tablename__ = "seo_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    issue_id = Column(Integer, ForeignKey("seo_issues.id", ondelete="SET NULL"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    category = Column(String(50), default="General SEO")
    status = Column(Enum(TaskStatus), default=TaskStatus.OPEN)
    
    evidence = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="seo_tasks")
    issue = relationship("SEOIssue", back_populates="tasks")
    assigned_to = relationship("User", back_populates="assigned_tasks")
