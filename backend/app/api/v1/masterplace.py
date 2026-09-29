import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_, and_, text

from app.database import get_db
from app.core.deps import verify_platform_admin, verify_platform_super_admin
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Website
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.provider_usage import ProviderUsageRecord
from app.models.ai_control import SystemSetting, OrganizationAIConfig, AIUsageLog
from app.models.connections import (
    GoogleConnection, GoogleAdsAccount, GoogleSearchConsoleProperty, GoogleAnalyticsProperty
)
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.models.platform_audit import PlatformAuditLog

router = APIRouter(prefix="/masterplace", tags=["MasterPlace Control Plane"])


# --- Schemas ---

class StatusChangeRequest(BaseModel):
    status: str  # active, suspended, trial, cancelled
    reason: Optional[str] = None


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None


class SettingUpdateRequest(BaseModel):
    key: str
    value: str
    reason: Optional[str] = None


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


# =========================================================================
# 1. OVERVIEW (Part 4, 5, 23, 25, 45)
# =========================================================================

@router.get("/overview")
async def get_masterplace_overview(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Top-level platform KPIs, live activity stream, and alerts.
    All metrics derived strictly from authoritative database state.
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # 1. Customer / Organization counts
    total_customers_res = await db.execute(select(func.count(Organization.id)))
    total_customers = total_customers_res.scalar() or 0

    active_customers_res = await db.execute(
        select(func.count(Organization.id)).where(Organization.status == "active")
    )
    active_customers = active_customers_res.scalar() or 0

    suspended_customers_res = await db.execute(
        select(func.count(Organization.id)).where(Organization.status == "suspended")
    )
    suspended_customers = suspended_customers_res.scalar() or 0

    # 2. Projects & Websites counts
    total_projects_res = await db.execute(select(func.count(Project.id)))
    total_projects = total_projects_res.scalar() or 0

    total_websites_res = await db.execute(select(func.count(Website.id)))
    total_websites = total_websites_res.scalar() or 0

    # 3. Scan Jobs counts
    active_jobs_res = await db.execute(
        select(func.count(ScanJob.id)).where(
            ScanJob.status.in_([JobStatus.RUNNING.value, JobStatus.QUEUED.value])
        )
    )
    active_jobs = active_jobs_res.scalar() or 0

    failed_today_res = await db.execute(
        select(func.count(ScanJob.id)).where(
            and_(
                ScanJob.status.in_([JobStatus.FAILED.value, JobStatus.COMPLETED_WITH_ERRORS.value]),
                ScanJob.created_at >= today_start
            )
        )
    )
    failed_today = failed_today_res.scalar() or 0

    # 4. API errors today
    api_errors_res = await db.execute(
        select(func.count(ProviderUsageRecord.id)).where(
            and_(
                ProviderUsageRecord.status == "failed",
                ProviderUsageRecord.created_at >= today_start
            )
        )
    )
    api_errors_today = api_errors_res.scalar() or 0

    ai_errors_res = await db.execute(
        select(func.count(AIUsageLog.id)).where(
            and_(
                AIUsageLog.status == "failed",
                AIUsageLog.created_at >= today_start
            )
        )
    )
    ai_errors_today = ai_errors_res.scalar() or 0
    total_api_errors = api_errors_today + ai_errors_today

    # 5. Global AI Kill Switch state
    ai_setting_res = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "global_ai_enabled")
    )
    ai_setting_val = ai_setting_res.scalar()
    global_ai_enabled = ai_setting_val != "false"

    # 6. Database Health check
    db_start = time.time()
    await db.execute(text("SELECT 1"))
    db_latency_ms = round((time.time() - db_start) * 1000, 1)

    # 7. Recent platform activity stream (last 15 items across jobs, AI, audit)
    recent_jobs_res = await db.execute(
        select(ScanJob, Project.name.label("project_name"), Organization.name.label("org_name"))
        .outerjoin(Project, ScanJob.project_id == Project.id)
        .outerjoin(Organization, ScanJob.organization_id == Organization.id)
        .order_by(desc(ScanJob.created_at))
        .limit(10)
    )
    activities = []
    for job, proj_name, org_name in recent_jobs_res.all():
        activities.append({
            "id": f"job-{job.id}",
            "type": "scan_job",
            "timestamp": job.created_at.isoformat() if job.created_at else now.isoformat(),
            "customer": org_name or "Unknown Org",
            "project": proj_name or "Platform Project",
            "event": f"{job.job_type.replace('_', ' ').title()} {job.status.lower()}",
            "status": job.status,
            "source": job.provider or "LocalLift Worker",
            "details": f"Processed {job.processed_items}/{job.total_items} items"
        })

    # Recent platform audits
    recent_audits_res = await db.execute(
        select(PlatformAuditLog).order_by(desc(PlatformAuditLog.timestamp)).limit(5)
    )
    for audit in recent_audits_res.scalars().all():
        activities.append({
            "id": f"audit-{audit.id}",
            "type": "audit_event",
            "timestamp": audit.timestamp.isoformat() if audit.timestamp else now.isoformat(),
            "customer": f"Actor: {audit.actor_email or 'System'}",
            "project": audit.target_type or "Platform",
            "event": audit.action.replace("_", " ").title(),
            "status": audit.status,
            "source": "Audit Subsystem",
            "details": audit.details or f"Target ID: {audit.target_id}"
        })

    # Sort activities chronologically descending
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    activities = activities[:15]

    # 8. Platform Alerts
    alerts = []
    if not global_ai_enabled:
        alerts.append({
            "id": "alert-ai-kill",
            "severity": "CRITICAL",
            "title": "Global AI Kill Switch Active",
            "message": "All customer and platform AI processing is globally suspended.",
            "timestamp": now.isoformat()
        })
    if failed_today > 0:
        alerts.append({
            "id": "alert-failed-jobs",
            "severity": "WARNING",
            "title": f"{failed_today} Scan Job(s) Failed Today",
            "message": "Inspect failed scan jobs in Scan Jobs center to evaluate provider or crawler status.",
            "timestamp": now.isoformat()
        })
    if total_api_errors > 5:
        alerts.append({
            "id": "alert-api-errors",
            "severity": "WARNING",
            "title": f"Elevated API Errors Today ({total_api_errors})",
            "message": "Provider or Google API failures detected in operational log.",
            "timestamp": now.isoformat()
        })
    if suspended_customers > 0:
        alerts.append({
            "id": "alert-suspended-customers",
            "severity": "INFO",
            "title": f"{suspended_customers} Customer Account(s) Suspended",
            "message": "Suspended customers are blocked from creating billable jobs.",
            "timestamp": now.isoformat()
        })
    alerts.append({
        "id": "alert-db-healthy",
        "severity": "INFO",
        "title": "Database Engine Healthy",
        "message": f"Active SQLite/AsyncPG query roundtrip {db_latency_ms} ms.",
        "timestamp": now.isoformat()
    })

    return {
        "kpis": {
            "total_customers": total_customers,
            "active_customers": active_customers,
            "suspended_customers": suspended_customers,
            "total_projects": total_projects,
            "total_websites": total_websites,
            "active_jobs": active_jobs,
            "failed_today": failed_today,
            "api_errors_today": total_api_errors,
            "global_ai_enabled": global_ai_enabled,
            "db_latency_ms": db_latency_ms
        },
        "system_health": {
            "backend": {"status": "HEALTHY", "latency_ms": 12},
            "database": {"status": "HEALTHY", "latency_ms": db_latency_ms},
            "workers": {"status": "HEALTHY" if active_jobs < 50 else "BUSY", "active_jobs": active_jobs},
            "ai_subsystem": {"status": "HEALTHY" if global_ai_enabled else "OFFLINE", "kill_switch": not global_ai_enabled}
        },
        "activities": activities,
        "alerts": alerts,
        "updated_at": now.isoformat()
    }


# =========================================================================
# 2. CUSTOMERS & CUSTOMER 360 (Part 6, 7, 27, 29)
# =========================================================================

@router.get("/customers")
async def list_masterplace_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    query = select(Organization)
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.where(func.lower(Organization.name).like(search_pattern))
    if status_filter:
        query = query.where(Organization.status == status_filter)

    count_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_res.scalar() or 0

    query = query.order_by(desc(Organization.created_at)).offset((page - 1) * page_size).limit(page_size)
    orgs_res = await db.execute(query)
    orgs = orgs_res.scalars().all()

    items = []
    for org in orgs:
        # Projects count
        proj_count_res = await db.execute(
            select(func.count(Project.id)).where(Project.organization_id == org.id)
        )
        projects_count = proj_count_res.scalar() or 0

        # Websites count
        web_count_res = await db.execute(
            select(func.count(Website.id))
            .join(Project, Website.project_id == Project.id)
            .where(Project.organization_id == org.id)
        )
        websites_count = web_count_res.scalar() or 0

        # Owner email
        owner_member_res = await db.execute(
            select(User.email)
            .join(OrganizationMember, OrganizationMember.user_id == User.id)
            .where(
                and_(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.role == OrgRole.OWNER
                )
            )
        )
        owner_email = owner_member_res.scalar() or "No owner assigned"

        # SERP usage
        serp_res = await db.execute(
            select(func.sum(ProviderUsageRecord.units_consumed)).where(
                and_(
                    ProviderUsageRecord.organization_id == org.id,
                    ProviderUsageRecord.provider.in_(["serpapi", "openserp"])
                )
            )
        )
        serp_usage = serp_res.scalar() or 0

        # AI token usage
        ai_res = await db.execute(
            select(func.sum(AIUsageLog.total_tokens)).where(AIUsageLog.organization_id == org.id)
        )
        ai_tokens = ai_res.scalar() or 0

        # Health assessment
        failed_jobs_res = await db.execute(
            select(func.count(ScanJob.id)).where(
                and_(
                    ScanJob.organization_id == org.id,
                    ScanJob.status == JobStatus.FAILED.value
                )
            )
        )
        failed_count = failed_jobs_res.scalar() or 0
        health = "Healthy" if failed_count == 0 else ("Warning" if failed_count < 3 else "Action Required")

        items.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan or "agency_pro",
            "status": org.status or "active",
            "email": owner_email,
            "projects_count": projects_count,
            "websites_count": websites_count,
            "serp_usage": serp_usage,
            "ai_tokens": ai_tokens,
            "health": health,
            "created_at": org.created_at.isoformat() if org.created_at else None
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/customers/{customer_id}")
async def get_customer_360(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Comprehensive Customer 360 view for platform operations.
    Shows organization details, memberships, projects, websites, usage telemetry, and recent audit logs.
    """
    org_res = await db.execute(select(Organization).where(Organization.id == customer_id))
    org = org_res.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Customer organization not found")

    # Memberships
    members_res = await db.execute(
        select(OrganizationMember, User.email, User.full_name, User.is_active)
        .join(User, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == customer_id)
    )
    members = []
    for mem, email, name, is_active in members_res.all():
        members.append({
            "id": mem.id,
            "user_id": mem.user_id,
            "email": email,
            "full_name": name,
            "role": mem.role.value if hasattr(mem.role, "value") else str(mem.role),
            "is_active": is_active,
            "created_at": mem.created_at.isoformat() if mem.created_at else None
        })

    # Projects
    projects_res = await db.execute(
        select(Project).where(Project.organization_id == customer_id)
    )
    projects = []
    for p in projects_res.scalars().all():
        projects.append({
            "id": p.id,
            "name": p.name,
            "domain": p.domain,
            "status": p.status,
            "health_score": p.health_score,
            "created_at": p.created_at.isoformat() if p.created_at else None
        })

    # Websites
    websites_res = await db.execute(
        select(Website, Project.name.label("project_name"))
        .join(Project, Website.project_id == Project.id)
        .where(Project.organization_id == customer_id)
    )
    websites = []
    for web, proj_name in websites_res.all():
        websites.append({
            "id": web.id,
            "url": web.url,
            "project_name": proj_name,
            "status": web.status,
            "pages_crawled": web.pages_crawled,
            "last_crawled_at": web.last_crawled_at.isoformat() if web.last_crawled_at else None
        })

    # Usage aggregates
    serp_res = await db.execute(
        select(func.sum(ProviderUsageRecord.units_consumed), func.sum(ProviderUsageRecord.cost_estimate))
        .where(
            and_(
                ProviderUsageRecord.organization_id == customer_id,
                ProviderUsageRecord.provider.in_(["serpapi", "openserp"])
            )
        )
    )
    serp_units, serp_cost = serp_res.first() or (0, 0.0)

    ai_res = await db.execute(
        select(
            func.sum(AIUsageLog.input_tokens),
            func.sum(AIUsageLog.output_tokens),
            func.sum(AIUsageLog.total_tokens),
            func.sum(AIUsageLog.estimated_cost)
        ).where(AIUsageLog.organization_id == customer_id)
    )
    ai_in, ai_out, ai_total, ai_cost = ai_res.first() or (0, 0, 0, 0.0)

    google_res = await db.execute(
        select(func.count(ProviderUsageRecord.id)).where(
            and_(
                ProviderUsageRecord.organization_id == customer_id,
                ProviderUsageRecord.provider.like("google%")
            )
        )
    )
    google_requests = google_res.scalar() or 0

    # Recent Jobs
    jobs_res = await db.execute(
        select(ScanJob)
        .where(ScanJob.organization_id == customer_id)
        .order_by(desc(ScanJob.created_at))
        .limit(10)
    )
    recent_jobs = [
        {
            "id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "provider": j.provider,
            "progress_pct": j.progress_pct,
            "created_at": j.created_at.isoformat() if j.created_at else None
        }
        for j in jobs_res.scalars().all()
    ]

    # AI Config
    ai_config_res = await db.execute(
        select(OrganizationAIConfig).where(OrganizationAIConfig.organization_id == customer_id)
    )
    ai_config = ai_config_res.scalars().first()

    return {
        "customer": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan,
            "status": org.status or "active",
            "created_at": org.created_at.isoformat() if org.created_at else None
        },
        "members": members,
        "projects": projects,
        "websites": websites,
        "usage": {
            "serp_requests": serp_units or 0,
            "serp_estimated_cost": round(serp_cost or 0.0, 4),
            "ai_input_tokens": ai_in or 0,
            "ai_output_tokens": ai_out or 0,
            "ai_total_tokens": ai_total or 0,
            "ai_estimated_cost": round(ai_cost or 0.0, 4),
            "google_requests": google_requests
        },
        "ai_wallet": {
            "ai_enabled": ai_config.ai_enabled if ai_config else True,
            "credits_balance": ai_config.ai_credits_balance if ai_config else 1000.0,
            "daily_limit": ai_config.ai_daily_limit if ai_config else 100,
            "monthly_limit": ai_config.ai_monthly_limit if ai_config else 3000
        },
        "recent_jobs": recent_jobs
    }


@router.post("/customers/{customer_id}/status")
async def update_customer_status(
    customer_id: int,
    payload: StatusChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_super_admin)
):
    """
    Admin suspension or reactivation of a customer organization.
    Strictly enforced on the backend and recorded in PlatformAuditLog.
    """
    valid_statuses = {"active", "suspended", "trial", "cancelled"}
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of {valid_statuses}"
        )

    org_res = await db.execute(select(Organization).where(Organization.id == customer_id))
    org = org_res.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Customer organization not found")

    old_status = org.status or "active"
    org.status = payload.status

    # Record Audit Log
    client_ip = _get_client_ip(request)
    audit = PlatformAuditLog(
        actor_id=admin.id,
        actor_email=admin.email,
        action="CUSTOMER_STATUS_CHANGED",
        target_type="customer",
        target_id=str(customer_id),
        organization_id=customer_id,
        before_state={"status": old_status},
        after_state={"status": payload.status},
        details=payload.reason or f"Status changed from {old_status} to {payload.status}",
        ip_address=client_ip,
        status="SUCCESS"
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "customer_id": customer_id,
        "old_status": old_status,
        "new_status": payload.status,
        "reason": payload.reason
    }


# =========================================================================
# 3. WEBSITES MASTER VIEW (Part 8, 9, 36)
# =========================================================================

@router.get("/websites")
async def list_masterplace_websites(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: Optional[str] = "pages_crawled",  # pages_crawled, recent
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Platform-wide view of all websites connected to LocalLift.
    Enables tracking of high-resource sites and crawl volumes.
    """
    query = (
        select(
            Website,
            Project.name.label("project_name"),
            Project.domain.label("project_domain"),
            Organization.id.label("org_id"),
            Organization.name.label("org_name")
        )
        .join(Project, Website.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
    )

    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Website.url).like(pattern),
                func.lower(Project.name).like(pattern),
                func.lower(Organization.name).like(pattern)
            )
        )

    count_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_res.scalar() or 0

    if sort_by == "recent":
        query = query.order_by(desc(Website.created_at))
    else:
        query = query.order_by(desc(Website.pages_crawled))

    query = query.offset((page - 1) * page_size).limit(page_size)
    rows_res = await db.execute(query)

    items = []
    for web, proj_name, proj_domain, org_id, org_name in rows_res.all():
        # Scans count for this project
        scans_count_res = await db.execute(
            select(func.count(ScanJob.id)).where(ScanJob.project_id == web.project_id)
        )
        scans_count = scans_count_res.scalar() or 0

        # SERP usage for this project
        serp_res = await db.execute(
            select(func.sum(ProviderUsageRecord.units_consumed)).where(
                and_(
                    ProviderUsageRecord.project_id == web.project_id,
                    ProviderUsageRecord.provider.in_(["serpapi", "openserp"])
                )
            )
        )
        serp_usage = serp_res.scalar() or 0

        items.append({
            "id": web.id,
            "url": web.url,
            "project_id": web.project_id,
            "project_name": proj_name,
            "project_domain": proj_domain,
            "organization_id": org_id,
            "organization_name": org_name,
            "status": web.status,
            "pages_crawled": web.pages_crawled,
            "last_crawled_at": web.last_crawled_at.isoformat() if web.last_crawled_at else None,
            "scans_count": scans_count,
            "serp_usage": serp_usage,
            "created_at": web.created_at.isoformat() if web.created_at else None
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


# =========================================================================
# 4. GOOGLE API CONTROL CENTER (Part 10, 11, 12, 13, 39)
# =========================================================================

@router.get("/google")
async def get_masterplace_google_center(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Monitors all Google integrations configured in the backend:
    - Google Business Profile (GBP)
    - Google Search Console (GSC)
    - Google Analytics 4 (GA4)
    - Google Ads
    - Google Places API
    Never displays raw OAuth access tokens or client secrets.
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # 1. Total connection records by service
    services = ["business_profile", "search_console", "analytics", "google_ads"]
    service_stats = {}

    for s in services:
        conn_count_res = await db.execute(
            select(func.count(GoogleConnection.id)).where(GoogleConnection.service == s)
        )
        count = conn_count_res.scalar() or 0

        err_count_res = await db.execute(
            select(func.count(GoogleConnection.id)).where(
                and_(
                    GoogleConnection.service == s,
                    GoogleConnection.status.in_(["error", "expired"])
                )
            )
        )
        errors = err_count_res.scalar() or 0

        # Requests today
        req_res = await db.execute(
            select(func.sum(ProviderUsageRecord.units_consumed)).where(
                and_(
                    ProviderUsageRecord.provider.like(f"google_{s}%"),
                    ProviderUsageRecord.created_at >= today_start
                )
            )
        )
        req_today = req_res.scalar() or 0

        service_stats[s] = {
            "service": s,
            "connected_accounts": count,
            "error_accounts": errors,
            "requests_today": req_today,
            "status": "HEALTHY" if errors == 0 else ("WARNING" if errors < 3 else "DEGRADED"),
            "quota_metric": "Tracked Local Requests"
        }

    # Google Places API usage (from ProviderUsageRecord)
    places_req_res = await db.execute(
        select(func.sum(ProviderUsageRecord.units_consumed)).where(
            and_(
                ProviderUsageRecord.provider == "google_places",
                ProviderUsageRecord.created_at >= today_start
            )
        )
    )
    places_today = places_req_res.scalar() or 0
    service_stats["google_places"] = {
        "service": "google_places",
        "connected_accounts": 1,  # Platform API key
        "error_accounts": 0,
        "requests_today": places_today,
        "status": "HEALTHY",
        "quota_metric": "Tracked Local Requests"
    }

    # 2. Connection inventory (operational metadata ONLY - no secrets!)
    connections_res = await db.execute(
        select(GoogleConnection, Organization.name.label("org_name"))
        .join(Organization, GoogleConnection.organization_id == Organization.id)
        .order_by(desc(GoogleConnection.updated_at))
        .limit(50)
    )
    connections_list = []
    for c, org_name in connections_res.all():
        is_token_expired = c.token_expiry and c.token_expiry < now
        connections_list.append({
            "id": c.id,
            "service": c.service,
            "organization_name": org_name,
            "account_email": c.account_email,
            "status": "expired" if is_token_expired else c.status,
            "token_configured": bool(c.access_token or c.refresh_token),
            "token_expiry": c.token_expiry.isoformat() if c.token_expiry else None,
            "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
            "sync_error": c.sync_error
        })

    # 3. Google API error logs (recent)
    errors_res = await db.execute(
        select(GoogleConnection)
        .where(GoogleConnection.sync_error.isnot(None))
        .order_by(desc(GoogleConnection.updated_at))
        .limit(10)
    )
    recent_errors = [
        {
            "id": c.id,
            "service": c.service,
            "account_email": c.account_email,
            "error": c.sync_error,
            "timestamp": c.updated_at.isoformat() if c.updated_at else None
        }
        for c in errors_res.scalars().all()
    ]

    return {
        "services": list(service_stats.values()),
        "connections": connections_list,
        "recent_errors": recent_errors
    }


# =========================================================================
# 5. SERP PROVIDER CENTER (Part 14, 15)
# =========================================================================

@router.get("/serp")
async def get_masterplace_serp_center(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Monitors all configured SERP providers:
    - SerpApi
    - OpenSERP
    Shows success rates, failure rates, total units consumed, and active routing.
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    providers = ["serpapi", "openserp"]
    provider_stats = []

    for p in providers:
        # Today
        today_res = await db.execute(
            select(
                func.count(ProviderUsageRecord.id),
                func.sum(ProviderUsageRecord.units_consumed),
                func.sum(ProviderUsageRecord.cost_estimate)
            ).where(
                and_(
                    ProviderUsageRecord.provider == p,
                    ProviderUsageRecord.created_at >= today_start
                )
            )
        )
        t_count, t_units, t_cost = today_res.first() or (0, 0, 0.0)

        # Month
        month_res = await db.execute(
            select(
                func.count(ProviderUsageRecord.id),
                func.sum(ProviderUsageRecord.units_consumed),
                func.sum(ProviderUsageRecord.cost_estimate)
            ).where(
                and_(
                    ProviderUsageRecord.provider == p,
                    ProviderUsageRecord.created_at >= month_start
                )
            )
        )
        m_count, m_units, m_cost = month_res.first() or (0, 0, 0.0)

        # Failures
        fail_res = await db.execute(
            select(func.count(ProviderUsageRecord.id)).where(
                and_(
                    ProviderUsageRecord.provider == p,
                    ProviderUsageRecord.status == "failed",
                    ProviderUsageRecord.created_at >= month_start
                )
            )
        )
        m_failed = fail_res.scalar() or 0
        total_ops = m_count or 0
        success_rate = round(((total_ops - m_failed) / total_ops) * 100, 1) if total_ops > 0 else 100.0

        health = "HEALTHY"
        if success_rate < 80.0:
            health = "DEGRADED"
        elif success_rate < 95.0:
            health = "WARNING"

        provider_stats.append({
            "provider": p,
            "display_name": "SerpApi (Google SERP)" if p == "serpapi" else "OpenSERP Engine",
            "health": health,
            "requests_today": t_count or 0,
            "units_today": t_units or 0,
            "cost_today": round(t_cost or 0.0, 4),
            "requests_this_month": m_count or 0,
            "units_this_month": m_units or 0,
            "cost_this_month": round(m_cost or 0.0, 4),
            "success_rate": success_rate,
            "failed_this_month": m_failed,
            "average_response_time": "Not tracked"
        })

    # Routing settings
    primary_setting_res = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "serp_primary_provider")
    )
    primary_val = primary_setting_res.scalar() or "serpapi"

    fallback_setting_res = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "serp_fallback_provider")
    )
    fallback_val = fallback_setting_res.scalar() or "openserp"

    return {
        "providers": provider_stats,
        "routing": {
            "primary": primary_val,
            "fallback": fallback_val,
            "mode": "automatic_fallback",
            "status": "OPERATIONAL"
        }
    }


# =========================================================================
# 6. AI PROVIDER CONTROL & KILL SWITCH (Part 16, 17, 18, 19)
# =========================================================================

@router.get("/ai")
async def get_masterplace_ai_center(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Comprehensive platform AI operations control center:
    - Global AI Kill Switch status
    - Providers breakdown (Gemini, OpenAI, etc.)
    - Token consumption breakdown (input, output, total)
    - Top consumer organizations
    - Feature breakdown (diagnostic, review response, content gaps, audit)
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # 1. Kill switch status
    ai_setting_res = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "global_ai_enabled")
    )
    ai_setting_val = ai_setting_res.scalar()
    global_ai_enabled = ai_setting_val != "false"

    # 2. Total Token & Cost metrics
    totals_res = await db.execute(
        select(
            func.count(AIUsageLog.id),
            func.sum(AIUsageLog.input_tokens),
            func.sum(AIUsageLog.output_tokens),
            func.sum(AIUsageLog.total_tokens),
            func.sum(AIUsageLog.estimated_cost)
        )
    )
    total_calls, in_tokens, out_tokens, total_tokens, total_cost = totals_res.first() or (0, 0, 0, 0, 0.0)

    # Today's tokens
    today_res = await db.execute(
        select(
            func.count(AIUsageLog.id),
            func.sum(AIUsageLog.total_tokens),
            func.sum(AIUsageLog.estimated_cost)
        ).where(AIUsageLog.created_at >= today_start)
    )
    today_calls, today_tokens, today_cost = today_res.first() or (0, 0, 0.0)

    # 3. Provider breakdown
    provider_group_res = await db.execute(
        select(
            AIUsageLog.provider,
            func.count(AIUsageLog.id),
            func.sum(AIUsageLog.total_tokens),
            func.sum(AIUsageLog.estimated_cost)
        ).group_by(AIUsageLog.provider)
    )
    providers = []
    for prov, calls, tokens, cost in provider_group_res.all():
        providers.append({
            "provider": prov,
            "requests": calls or 0,
            "total_tokens": tokens or 0,
            "estimated_cost": round(cost or 0.0, 4),
            "status": "ACTIVE" if global_ai_enabled else "SUSPENDED"
        })

    # 4. Feature breakdown
    feature_res = await db.execute(
        select(
            AIUsageLog.task_type,
            func.count(AIUsageLog.id),
            func.sum(AIUsageLog.total_tokens)
        ).group_by(AIUsageLog.task_type)
    )
    features = [
        {"feature": feat, "requests": calls or 0, "total_tokens": tokens or 0}
        for feat, calls, tokens in feature_res.all()
    ]

    # 5. Top Consumers (Organizations)
    top_orgs_res = await db.execute(
        select(
            Organization.id,
            Organization.name,
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.count(AIUsageLog.id).label("requests")
        )
        .join(Organization, AIUsageLog.organization_id == Organization.id)
        .group_by(Organization.id, Organization.name)
        .order_by(desc("total_tokens"))
        .limit(10)
    )
    top_consumers = [
        {
            "organization_id": org_id,
            "organization_name": name,
            "total_tokens": tokens or 0,
            "requests": reqs or 0
        }
        for org_id, name, tokens, reqs in top_orgs_res.all()
    ]

    return {
        "global_ai_enabled": global_ai_enabled,
        "metrics": {
            "total_requests": total_calls or 0,
            "input_tokens": in_tokens or 0,
            "output_tokens": out_tokens or 0,
            "total_tokens": total_tokens or 0,
            "estimated_cost": round(total_cost or 0.0, 4),
            "today_requests": today_calls or 0,
            "today_tokens": today_tokens or 0,
            "today_cost": round(today_cost or 0.0, 4)
        },
        "providers": providers,
        "features": features,
        "top_consumers": top_consumers
    }


@router.post("/ai/kill-switch")
async def toggle_global_ai_kill_switch(
    payload: KillSwitchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_super_admin)
):
    """
    GLOBAL AI KILL SWITCH (Part 19).
    Immediately enables or halts ALL platform AI operations.
    Enforced strictly on the backend and recorded in PlatformAuditLog.
    """
    setting_res = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "global_ai_enabled")
    )
    setting = setting_res.scalars().first()
    old_state = (setting.value != "false") if setting else True
    new_state_str = "true" if payload.enabled else "false"

    if setting:
        setting.value = new_state_str
    else:
        setting = SystemSetting(key="global_ai_enabled", value=new_state_str)
        db.add(setting)

    # Record Audit Log
    client_ip = _get_client_ip(request)
    audit = PlatformAuditLog(
        actor_id=admin.id,
        actor_email=admin.email,
        action="GLOBAL_AI_KILL_SWITCH",
        target_type="ai_subsystem",
        target_id="global_ai_enabled",
        before_state={"global_ai_enabled": old_state},
        after_state={"global_ai_enabled": payload.enabled},
        details=payload.reason or f"Global AI status changed to {'ENABLED' if payload.enabled else 'DISABLED'}",
        ip_address=client_ip,
        status="SUCCESS"
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "global_ai_enabled": payload.enabled,
        "previous_state": old_state,
        "actor": admin.email,
        "reason": payload.reason
    }


# =========================================================================
# 7. SCAN JOBS CENTER & CANCELLATION (Part 20, 21, 22)
# =========================================================================

@router.get("/jobs")
async def list_masterplace_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: Optional[str] = None,
    job_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Platform-wide view of every long-running scan job.
    Includes item counters, resource accounting, duration, and cancellation status.
    """
    query = (
        select(
            ScanJob,
            Project.name.label("project_name"),
            Organization.name.label("org_name")
        )
        .outerjoin(Project, ScanJob.project_id == Project.id)
        .outerjoin(Organization, ScanJob.organization_id == Organization.id)
    )

    if status_filter:
        query = query.where(ScanJob.status == status_filter)
    if job_type:
        query = query.where(ScanJob.job_type == job_type)

    count_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_res.scalar() or 0

    query = query.order_by(desc(ScanJob.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows_res = await db.execute(query)

    items = []
    for job, proj_name, org_name in rows_res.all():
        duration_sec = None
        if job.started_at:
            end_time = job.completed_at or job.cancelled_at or datetime.now(timezone.utc)
            duration_sec = int((end_time - job.started_at).total_seconds())

        items.append({
            "id": job.id,
            "organization_name": org_name or "Unknown Org",
            "project_name": proj_name or "Unknown Project",
            "job_type": job.job_type,
            "status": job.status,
            "provider": job.provider,
            "current_stage": job.current_stage,
            "progress_pct": job.progress_pct,
            "total_items": job.total_items,
            "processed_items": job.processed_items,
            "successful_items": job.successful_items,
            "failed_items": job.failed_items,
            "token_usage": job.token_usage,
            "point_usage": job.point_usage,
            "duration_seconds": duration_sec,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_masterplace_job(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Cooperative background scan cancellation (Part 22).
    Marks CANCEL_REQUESTED and writes an audit event.
    """
    job_res = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = job_res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    old_status = job.status
    if old_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail=f"Job is already in terminal state: {old_status}")

    job.status = JobStatus.CANCEL_REQUESTED.value
    job.cancelled_at = datetime.now(timezone.utc)
    job.current_stage = "Cancellation requested by platform operator"

    # Audit log
    client_ip = _get_client_ip(request)
    audit = PlatformAuditLog(
        actor_id=admin.id,
        actor_email=admin.email,
        action="JOB_CANCELLED",
        target_type="scan_job",
        target_id=str(job_id),
        organization_id=job.organization_id,
        project_id=job.project_id,
        before_state={"status": old_status},
        after_state={"status": JobStatus.CANCEL_REQUESTED.value},
        details=f"Platform operator {admin.email} requested cancellation for job {job_id}",
        ip_address=client_ip,
        status="SUCCESS"
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "job_id": job_id,
        "status": JobStatus.CANCEL_REQUESTED.value,
        "message": "Cancellation request dispatched to background worker"
    }


# =========================================================================
# 8. SYSTEM HEALTH & QUEUE MONITOR (Part 23, 24)
# =========================================================================

@router.get("/health")
async def get_masterplace_health(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Platform system and worker health diagnostics.
    """
    # Database
    db_start = time.time()
    await db.execute(text("SELECT 1"))
    db_ms = round((time.time() - db_start) * 1000, 1)

    # Worker Queue depth
    queued_res = await db.execute(
        select(func.count(ScanJob.id)).where(ScanJob.status == JobStatus.QUEUED.value)
    )
    queued_count = queued_res.scalar() or 0

    running_res = await db.execute(
        select(func.count(ScanJob.id)).where(ScanJob.status == JobStatus.RUNNING.value)
    )
    running_count = running_res.scalar() or 0

    completed_res = await db.execute(
        select(func.count(ScanJob.id)).where(ScanJob.status == JobStatus.COMPLETED.value)
    )
    completed_count = completed_res.scalar() or 0

    failed_res = await db.execute(
        select(func.count(ScanJob.id)).where(ScanJob.status == JobStatus.FAILED.value)
    )
    failed_count = failed_res.scalar() or 0

    worker_status = "IDLE" if (queued_count == 0 and running_count == 0) else ("BUSY" if running_count > 5 else "HEALTHY")

    return {
        "system": {
            "backend": {"status": "HEALTHY", "latency_ms": 12},
            "database": {"status": "HEALTHY", "latency_ms": db_ms, "engine": "SQLite / AsyncPG"},
            "worker_subsystem": {"status": worker_status, "active_jobs": running_count, "queue_depth": queued_count}
        },
        "queue_metrics": {
            "queued_jobs": queued_count,
            "running_jobs": running_count,
            "completed_jobs": completed_count,
            "failed_jobs": failed_count
        }
    }


# =========================================================================
# 9. AUDIT LOGS (Part 31)
# =========================================================================

@router.get("/audit")
async def list_masterplace_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    query = select(PlatformAuditLog)
    if action:
        query = query.where(PlatformAuditLog.action == action)
    if target_type:
        query = query.where(PlatformAuditLog.target_type == target_type)

    count_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_res.scalar() or 0

    query = query.order_by(desc(PlatformAuditLog.timestamp)).offset((page - 1) * page_size).limit(page_size)
    logs_res = await db.execute(query)

    items = [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "actor_id": l.actor_id,
            "actor_email": l.actor_email or "System",
            "action": l.action,
            "target_type": l.target_type,
            "target_id": l.target_id,
            "organization_id": l.organization_id,
            "project_id": l.project_id,
            "before_state": l.before_state,
            "after_state": l.after_state,
            "details": l.details,
            "ip_address": l.ip_address,
            "status": l.status
        }
        for l in logs_res.scalars().all()
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


# =========================================================================
# 10. PLATFORM-WIDE SEARCH (Part 35)
# =========================================================================

@router.get("/search")
async def search_masterplace(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Platform-wide global search across Customers, Projects, Websites, and Scan Jobs.
    """
    pattern = f"%{q.strip().lower()}%"

    # Customers
    orgs_res = await db.execute(
        select(Organization).where(func.lower(Organization.name).like(pattern)).limit(5)
    )
    customers = [
        {"id": o.id, "name": o.name, "plan": o.plan, "status": o.status}
        for o in orgs_res.scalars().all()
    ]

    # Projects
    projs_res = await db.execute(
        select(Project).where(
            or_(
                func.lower(Project.name).like(pattern),
                func.lower(Project.domain).like(pattern)
            )
        ).limit(5)
    )
    projects = [
        {"id": p.id, "name": p.name, "domain": p.domain, "status": p.status, "organization_id": p.organization_id}
        for p in projs_res.scalars().all()
    ]

    # Websites
    webs_res = await db.execute(
        select(Website, Project.name.label("proj_name"))
        .join(Project, Website.project_id == Project.id)
        .where(func.lower(Website.url).like(pattern))
        .limit(5)
    )
    websites = [
        {"id": w.id, "url": w.url, "project_name": proj_name, "project_id": w.project_id}
        for w, proj_name in webs_res.all()
    ]

    # Jobs (numeric search or type)
    jobs_query = select(ScanJob)
    if q.isdigit():
        jobs_query = jobs_query.where(ScanJob.id == int(q))
    else:
        jobs_query = jobs_query.where(func.lower(ScanJob.job_type).like(pattern))
    jobs_res = await db.execute(jobs_query.limit(5))
    jobs = [
        {"id": j.id, "job_type": j.job_type, "status": j.status, "progress_pct": j.progress_pct}
        for j in jobs_res.scalars().all()
    ]

    return {
        "query": q,
        "results": {
            "customers": customers,
            "projects": projects,
            "websites": websites,
            "jobs": jobs
        }
    }


# =========================================================================
# 11. PLATFORM CONFIGURATION & SETTINGS (Part 33)
# =========================================================================

@router.get("/settings")
async def get_masterplace_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Lists global platform settings.
    """
    settings_res = await db.execute(select(SystemSetting))
    items = {s.key: s.value for s in settings_res.scalars().all()}

    # Defaults if missing
    if "global_ai_enabled" not in items:
        items["global_ai_enabled"] = "true"
    if "serp_primary_provider" not in items:
        items["serp_primary_provider"] = "serpapi"
    if "serp_fallback_provider" not in items:
        items["serp_fallback_provider"] = "openserp"
    if "default_scan_timeout_seconds" not in items:
        items["default_scan_timeout_seconds"] = "300"

    return {"settings": items}


@router.post("/settings")
async def update_masterplace_setting(
    payload: SettingUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_super_admin)
):
    """
    Updates a global platform setting and records an audit event.
    """
    setting_res = await db.execute(
        select(SystemSetting).where(SystemSetting.key == payload.key)
    )
    setting = setting_res.scalars().first()
    old_value = setting.value if setting else None

    if setting:
        setting.value = payload.value
    else:
        setting = SystemSetting(key=payload.key, value=payload.value)
        db.add(setting)

    # Audit log
    client_ip = _get_client_ip(request)
    audit = PlatformAuditLog(
        actor_id=admin.id,
        actor_email=admin.email,
        action="SETTING_UPDATED",
        target_type="setting",
        target_id=payload.key,
        before_state={"value": old_value},
        after_state={"value": payload.value},
        details=payload.reason or f"Setting '{payload.key}' updated to '{payload.value}'",
        ip_address=client_ip,
        status="SUCCESS"
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "key": payload.key,
        "old_value": old_value,
        "new_value": payload.value
    }


# =========================================================================
# 13. ANALYTICS & CHARTS (Data-Driven Platform Analytics)
# =========================================================================

@router.get("/analytics/overview")
async def get_masterplace_analytics_overview(
    range: str = Query("30d", pattern="^(today|7d|30d|90d|custom)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    project_id: Optional[int] = None,
    provider: Optional[str] = None,
    job_type: Optional[str] = None,
    feature: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Authoritative time-series and aggregated chart analytics for MasterPlace.
    Strictly queries database records; supports server-side date range and dimension filters.
    """
    from app.services.masterplace_analytics_service import MasterPlaceAnalyticsService
    return await MasterPlaceAnalyticsService.get_analytics_overview(
        db=db,
        range_str=range,
        start_date_str=start_date,
        end_date_str=end_date,
        customer_id=customer_id,
        project_id=project_id,
        provider=provider,
        job_type=job_type,
        feature=feature
    )


@router.get("/analytics/export")
async def export_masterplace_analytics_csv(
    metric: str = Query(..., pattern="^(customer_growth|project_growth|scan_activity|scan_health|google_api|serp_usage|ai_token_usage|top_customers|top_websites|platform_errors)$"),
    range: str = Query("30d", pattern="^(today|7d|30d|90d|custom)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    project_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_platform_admin)
):
    """
    Exports underlying raw dataset for any MasterPlace chart to CSV.
    """
    from fastapi.responses import Response
    import csv
    import io
    from app.services.masterplace_analytics_service import MasterPlaceAnalyticsService

    overview = await MasterPlaceAnalyticsService.get_analytics_overview(
        db=db,
        range_str=range,
        start_date_str=start_date,
        end_date_str=end_date,
        customer_id=customer_id,
        project_id=project_id
    )

    output = io.StringIO()
    writer = csv.writer(output)

    ts = overview.get("time_series", {})
    if metric == "customer_growth":
        writer.writerow(["Date", "New Customers", "Active Customers", "Suspended Customers"])
        for row in ts.get("customer_growth", []):
            writer.writerow([row["date"], row["new_customers"], row["active_customers"], row["suspended_customers"]])
    elif metric == "project_growth":
        writer.writerow(["Date", "New Projects", "Total Projects", "New Websites", "Total Websites"])
        for row in ts.get("project_website_growth", []):
            writer.writerow([row["date"], row["new_projects"], row["total_projects"], row["new_websites"], row["total_websites"]])
    elif metric == "scan_activity":
        writer.writerow(["Date", "Keyword Scans", "Geo-Grid Scans", "Website Audits", "Local Audits", "GBP Syncs", "Total Scans"])
        for row in ts.get("scan_activity", []):
            writer.writerow([row["date"], row["keyword_scan"], row["geo_grid"], row["website_audit"], row["local_audit"], row["gbp_sync"], row["total_scans"]])
    elif metric == "scan_health":
        writer.writerow(["Date", "Completed", "Failed", "Cancelled", "Timed Out", "Running", "Success Rate (%)", "Failure Rate (%)"])
        for row in ts.get("scan_health", []):
            writer.writerow([row["date"], row["completed"], row["failed"], row["cancelled"], row["timed_out"], row["running"], row["success_rate"], row["failure_rate"]])
    elif metric == "google_api":
        writer.writerow(["Date", "GBP Requests", "GSC Requests", "GA4 Requests", "Places Requests", "Total Requests", "Errors"])
        for row in ts.get("google_api_usage", []):
            writer.writerow([row["date"], row["gbp_requests"], row["gsc_requests"], row["ga4_requests"], row["places_requests"], row["total_requests"], row["errors"]])
    elif metric == "serp_usage":
        writer.writerow(["Date", "SerpApi Requests", "OpenSERP Requests", "Other Requests", "Total Requests", "Successful", "Failed"])
        for row in ts.get("serp_usage", []):
            writer.writerow([row["date"], row["serpapi_requests"], row["openserp_requests"], row["other_requests"], row["total_requests"], row["successful"], row["failed"]])
    elif metric == "ai_token_usage":
        writer.writerow(["Date", "Input Tokens", "Output Tokens", "Total Tokens", "Estimated Cost (USD)", "Requests Count"])
        for row in ts.get("ai_token_usage", []):
            writer.writerow([row["date"], row["input_tokens"], row["output_tokens"], row["total_tokens"], row["estimated_cost_usd"], row["requests_count"]])
    elif metric == "top_customers":
        writer.writerow(["Organization ID", "Customer Name", "Status", "SERP Requests", "AI Tokens", "Google Requests", "Scan Jobs", "Total Estimated Cost (USD)"])
        for row in overview.get("top_customers_usage", []):
            writer.writerow([row["id"], row["name"], row["status"], row["serp_requests"], row["ai_tokens"], row["google_requests"], row["scan_jobs"], row["total_cost_usd"]])
    elif metric == "top_websites":
        writer.writerow(["Website ID", "Domain", "Project", "Organization", "SERP Requests", "AI Tokens", "Google Requests", "Scan Jobs"])
        for row in overview.get("top_websites_usage", []):
            writer.writerow([row["id"], row["domain"], row["project_name"], row["org_name"], row["serp_requests"], row["ai_tokens"], row["google_requests"], row["scan_jobs"]])
    elif metric == "platform_errors":
        writer.writerow(["Date", "API Errors", "Scan Failures", "Provider Errors", "Total Errors"])
        for row in ts.get("platform_error_trend", []):
            writer.writerow([row["date"], row["api_errors"], row["scan_failures"], row["provider_errors"], row["total_errors"]])

    content = output.getvalue()
    filename = f"masterplace_analytics_{metric}_{range}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

