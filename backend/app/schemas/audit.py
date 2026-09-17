from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime

class WebsitePageOut(BaseModel):
    id: int
    website_id: int
    url: str
    status_code: int
    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1: Optional[str] = None
    h2_list: List[str] = []
    word_count: int = 0
    canonical_url: Optional[str] = None
    is_indexable: bool = True
    load_time_ms: int = 0
    schema_types: List[str] = []
    images_count: int = 0
    missing_alt_count: int = 0
    internal_links_count: int = 0
    external_links_count: int = 0
    broken_links: List[str] = []
    issues_detected: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class SEOIssueBase(BaseModel):
    category: str
    severity: str
    title: str
    evidence: Optional[str] = None
    why_it_matters: Optional[str] = None
    recommended_solution: Optional[str] = None
    action_type: Optional[str] = "manual_fix"
    affected_url: Optional[str] = None
    status: Optional[str] = "open"

class SEOIssueCreate(SEOIssueBase):
    project_id: int
    audit_id: Optional[int] = None

class SEOIssueOut(SEOIssueBase):
    id: int
    project_id: int
    audit_id: Optional[int] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SEOAuditOut(BaseModel):
    id: int
    project_id: int
    audit_type: str
    overall_score: int
    pages_analyzed: int
    critical_issues: int
    warnings: int
    opportunities: int
    passed_checks: int
    summary: Optional[str] = None
    details: Dict[str, Any] = {}
    created_at: datetime
    issues: List[SEOIssueOut] = []

    class Config:
        from_attributes = True

class CrawlRequest(BaseModel):
    url: str
    max_pages: Optional[int] = 25
    respect_robots: Optional[bool] = True
    crawl_delay_ms: Optional[int] = 200
    follow_redirects: Optional[bool] = True
    allow_local_dev: Optional[bool] = False
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    max_depth: Optional[int] = 5
    enable_js_rendering: Optional[bool] = False
    check_external_links: Optional[bool] = True
    max_external_links: Optional[int] = 50

class AuditJobOut(BaseModel):
    id: int
    project_id: int
    organization_id: Optional[int] = None
    job_type: str
    status: str
    crawler_status: Optional[str] = "queued"
    progress: float
    current_stage: str
    
    pages_discovered: int = 0
    pages_crawled: int = 0
    pages_processed: int = 0
    pages_failed: int = 0
    pages_blocked: int = 0
    links_discovered: int = 0
    links_checked: int = 0
    broken_links_found: int = 0
    js_pages_rendered: int = 0
    sitemap_urls_discovered: int = 0
    robots_blocked_count: int = 0
    ssrf_blocked_count: int = 0
    
    broken_link_check_status: str = "not_started"
    broken_link_check_error: Optional[str] = None
    links_skipped: int = 0
    runtime_limit_reached: bool = False
    redirect_limit_reached: bool = False
    browser_rendering_unavailable: bool = False
    
    start_url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    options_snapshot: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

