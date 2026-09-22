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

class AuditJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FETCHING_ROBOTS = "fetching_robots"
    READING_SITEMAPS = "reading_sitemaps"
    DISCOVERING = "discovering"
    CRAWLING = "crawling"
    CHECKING_LINKS = "checking_links"
    SAVING = "saving"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    BLOCKED_BY_ROBOTS = "blocked_by_robots"
    BLOCKED_BY_PROTECTION = "blocked_by_protection"
    FAILED = "failed"

class AuditJob(Base):
    __tablename__ = "audit_jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    job_type = Column(String(50), default="website_audit")
    status = Column(Enum(AuditJobStatus), default=AuditJobStatus.QUEUED, nullable=False)
    crawler_status = Column(String(100), default="queued")
    progress = Column(Float, default=0.0)
    current_stage = Column(String(200), default="Queued for execution")
    
    # Detailed diagnostic counters
    pages_discovered = Column(Integer, default=0)
    pages_crawled = Column(Integer, default=0)
    pages_processed = Column(Integer, default=0)
    pages_failed = Column(Integer, default=0)
    pages_blocked = Column(Integer, default=0)
    links_discovered = Column(Integer, default=0)
    links_checked = Column(Integer, default=0)
    broken_links_found = Column(Integer, default=0)
    js_pages_rendered = Column(Integer, default=0)
    sitemap_urls_discovered = Column(Integer, default=0)
    robots_blocked_count = Column(Integer, default=0)
    ssrf_blocked_count = Column(Integer, default=0)
    
    broken_link_check_status = Column(String(50), default="not_started")
    broken_link_check_error = Column(Text, nullable=True)
    links_skipped = Column(Integer, default=0)
    runtime_limit_reached = Column(Boolean, default=False)
    redirect_limit_reached = Column(Boolean, default=False)
    browser_rendering_unavailable = Column(Boolean, default=False)
    
    start_url = Column(String(1000), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # Session snapshot configuration used for this crawl
    options_snapshot = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project")


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


class LocalAuditRun(Base):
    """
    Project-scoped Local SEO Audit execution run across all 20 local audit categories.
    """
    __tablename__ = "local_audit_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    framework_version = Column(String(50), default="local_seo_v1")
    status = Column(String(50), default="completed")  # running, completed, completed_with_warnings, failed
    
    # Truth in scoring: None if insufficient data sources are available
    overall_score = Column(Integer, nullable=True, default=None)
    category_scores = Column(JSON, default=dict)  # {"google_business_profile": 85, "nap_consistency": 90, ...}
    findings_summary = Column(JSON, default=dict)  # {"total": 24, "pass": 18, "fail": 3, "not_verified": 3}
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="local_audit_runs")
    findings = relationship("LocalAuditFinding", back_populates="audit_run", cascade="all, delete-orphan")


class LocalAuditFinding(Base):
    """
    Individual evidence-backed finding from a Local SEO Audit run.
    Traceable to source, verification status, and confidence.
    """
    __tablename__ = "local_audit_findings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    audit_run_id = Column(Integer, ForeignKey("local_audit_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    category = Column(String(100), nullable=False, index=True)  # One of 20 categories
    check_key = Column(String(100), nullable=False, index=True)  # e.g. "gbp_claimed", "nap_phone_match"
    title = Column(String(255), nullable=False)
    
    status = Column(String(50), default="NOT_VERIFIED")  # PASS, PARTIAL, FAIL, NOT_VERIFIED, NOT_APPLICABLE, ERROR
    severity = Column(String(50), default="warning")  # critical, warning, opportunity, info
    score_impact = Column(Float, default=0.0)  # Points awarded or deducted
    
    evidence = Column(Text, nullable=True)
    source = Column(String(100), nullable=True)  # GBP API, Website Crawl, Directory Citation, SERP
    source_url = Column(String(1000), nullable=True)
    verification_status = Column(String(50), default="NOT_VERIFIED")  # Uses VerificationStatus enum values
    confidence = Column(String(50), default="HIGH")  # HIGH, MEDIUM, LOW
    
    recommendation = Column(Text, nullable=True)
    action_type = Column(String(100), default="manual_action")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit_run = relationship("LocalAuditRun", back_populates="findings")
    project = relationship("Project")

