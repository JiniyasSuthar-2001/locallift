import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_, and_

from app.database import get_db
from app.core.deps import get_current_user, get_user_organization_ids
from app.models.user import User, Organization, OrganizationMember
from app.models.project import Project, Website
from app.models.audit import SEOAudit, SEOTask, SEOIssue, TaskStatus, IssueStatus, IssueSeverity
from app.models.ranking import Keyword, GeoGridScan
from app.models.local_seo import Review, Citation
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.provider_usage import ProviderUsageRecord
from app.models.ai_control import AIUsageLog, OrganizationAIConfig
from app.models.connections import GoogleConnection, OrganizationSERPConfig
from app.models.team import ProjectMembership

logger = logging.getLogger("locallift.api.user_dashboard")

router = APIRouter(prefix="/dashboard", tags=["User Central Dashboard"])


async def get_authorized_projects_list(current_user: User, db: AsyncSession) -> List[Project]:
    """
    Returns all projects the current user is authorized to access.
    Strict tenant/org/membership boundary enforcement.
    """
    if current_user.is_superuser:
        stmt = select(Project).order_by(Project.id.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    org_ids = await get_user_organization_ids(current_user.id, db)

    team_res = await db.execute(
        select(ProjectMembership.project_id).where(
            ProjectMembership.user_id == current_user.id,
            ProjectMembership.status == "active"
        )
    )
    team_proj_ids = list(team_res.scalars().all())

    conditions = []
    if org_ids:
        conditions.append(Project.organization_id.in_(org_ids))
    if team_proj_ids:
        conditions.append(Project.id.in_(team_proj_ids))

    if not conditions:
        return []

    stmt = select(Project).where(or_(*conditions)).order_by(Project.id.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/overview")
async def get_user_central_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    USER CENTRAL DASHBOARD - Top-level multi-project aggregation for the logged-in customer.
    Answers: 'How are all MY projects doing?'
    Strictly scoped to current user / authorized organization projects.
    Never exposes platform-wide or other customers' data.
    """
    projects = await get_authorized_projects_list(current_user, db)
    project_ids = [p.id for p in projects]
    org_ids = list(set([p.organization_id for p in projects]))

    if not project_ids:
        return {
            "summary": {
                "total_projects": 0,
                "total_websites": 0,
                "tracked_keywords": 0,
                "active_scan_jobs": 0,
                "completed_scans": 0,
                "open_tasks": 0,
                "total_reviews": 0,
                "citation_records": 0,
                "geogrid_scans": 0,
            },
            "projects": [],
            "usage": {
                "serp_provider": {
                    "connected": False,
                    "provider": None,
                    "provider_name": None,
                    "plan_name": None,
                    "usage_model": None,
                    "used": None,
                    "limit": None,
                    "remaining": None,
                    "balance": None,
                    "currency": None,
                    "unit": None,
                    "percentage_used": None,
                    "renewal_date": None,
                    "last_synced_at": None,
                    "usage_available": False,
                    "locallift_requests_used": 0,
                },
                "serp_used": 0,
                "ai_tokens_used": 0,
                "ai_tokens_limit": 100000,
                "keywords_used": 0,
                "keywords_limit": 200,
                "geogrid_used": 0,
                "geogrid_limit": 1000,
            },
            "recent_activity": [],
            "alerts": []
        }

    # 1. Total Websites
    websites_res = await db.execute(
        select(func.count(Website.id)).where(Website.project_id.in_(project_ids))
    )
    total_websites = websites_res.scalar() or len(project_ids)

    # 2. Tracked Keywords
    kw_res = await db.execute(
        select(func.count(Keyword.id)).where(Keyword.project_id.in_(project_ids))
    )
    tracked_keywords = kw_res.scalar() or 0

    # 3. Scan Jobs
    active_scans_res = await db.execute(
        select(func.count(ScanJob.id)).where(
            ScanJob.project_id.in_(project_ids),
            ScanJob.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value])
        )
    )
    active_scan_jobs = active_scans_res.scalar() or 0

    completed_scans_res = await db.execute(
        select(func.count(ScanJob.id)).where(
            ScanJob.project_id.in_(project_ids),
            ScanJob.status.in_([JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_ERRORS.value])
        )
    )
    completed_scans = completed_scans_res.scalar() or 0

    # 4. Open Tasks
    open_task_statuses = [TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.WAITING, TaskStatus.RECHECK_REQUIRED]
    open_tasks_res = await db.execute(
        select(func.count(SEOTask.id)).where(
            SEOTask.project_id.in_(project_ids),
            SEOTask.status.in_(open_task_statuses)
        )
    )
    open_tasks = open_tasks_res.scalar() or 0

    # 5. Reviews
    reviews_res = await db.execute(
        select(func.count(Review.id)).where(Review.project_id.in_(project_ids))
    )
    total_reviews = reviews_res.scalar() or 0

    # 6. Citations
    citations_res = await db.execute(
        select(func.count(Citation.id)).where(Citation.project_id.in_(project_ids))
    )
    citation_records = citations_res.scalar() or 0

    # 7. GeoGrid Scans
    geogrid_res = await db.execute(
        select(func.count(GeoGridScan.id)).where(GeoGridScan.project_id.in_(project_ids))
    )
    geogrid_scans = geogrid_res.scalar() or 0

    # 8. Per-Project Detailed Summaries
    project_summaries = []
    for p in projects:
        # Keywords for project
        p_kw_res = await db.execute(
            select(func.count(Keyword.id)).where(Keyword.project_id == p.id)
        )
        p_kw_count = p_kw_res.scalar() or 0

        # Latest SEO Audit
        audit_res = await db.execute(
            select(SEOAudit).where(SEOAudit.project_id == p.id).order_by(SEOAudit.created_at.desc()).limit(1)
        )
        latest_audit = audit_res.scalars().first()
        audit_score = latest_audit.overall_score if latest_audit else p.health_score

        # Reviews for project
        p_rev_res = await db.execute(
            select(func.count(Review.id), func.avg(Review.rating)).where(Review.project_id == p.id)
        )
        p_rev_count, p_rev_avg = p_rev_res.first() or (0, None)

        # Citations for project
        p_cit_res = await db.execute(
            select(func.count(Citation.id)).where(Citation.project_id == p.id)
        )
        p_cit_count = p_cit_res.scalar() or 0

        # Tasks for project
        p_task_res = await db.execute(
            select(
                func.count(SEOTask.id).filter(SEOTask.status.in_(open_task_statuses)),
                func.count(SEOTask.id).filter(SEOTask.status == TaskStatus.COMPLETED)
            ).where(SEOTask.project_id == p.id)
        )
        p_open_tasks, p_done_tasks = p_task_res.first() or (0, 0)

        # Last scan job
        last_job_res = await db.execute(
            select(ScanJob).where(ScanJob.project_id == p.id).order_by(ScanJob.created_at.desc()).limit(1)
        )
        last_job = last_job_res.scalars().first()

        # Open issues count
        issues_res = await db.execute(
            select(func.count(SEOIssue.id)).where(
                SEOIssue.project_id == p.id,
                SEOIssue.status.in_([IssueStatus.OPEN, IssueStatus.IN_TASK])
            )
        )
        p_open_issues = issues_res.scalar() or 0

        project_summaries.append({
            "id": p.id,
            "name": p.name,
            "domain": p.domain,
            "primary_category": p.primary_category,
            "country": p.country,
            "status": p.status or "active",
            "is_archived": p.is_archived,
            "health_score": audit_score,
            "keyword_count": p_kw_count,
            "review_count": p_rev_count or 0,
            "rating_avg": round(float(p_rev_avg), 1) if p_rev_avg else None,
            "citation_count": p_cit_count or 0,
            "open_issues_count": p_open_issues,
            "open_tasks_count": p_open_tasks or 0,
            "completed_tasks_count": p_done_tasks or 0,
            "last_scan_date": last_job.created_at.isoformat() if last_job else (latest_audit.created_at.isoformat() if latest_audit else None),
            "last_scan_status": last_job.status if last_job else ("COMPLETED" if latest_audit else "NOT_SCANNED"),
            "last_scan_type": last_job.job_type if last_job else None
        })

    # 9. Customer Resource Usage (Strictly Org-Level)
    serp_usage_res = await db.execute(
        select(func.coalesce(func.sum(ProviderUsageRecord.units_consumed), 0)).where(
            ProviderUsageRecord.project_id.in_(project_ids)
        )
    )
    serp_units_used = serp_usage_res.scalar() or 0

    # Fetch External SERP Provider Account Usage from OrganizationSERPConfig
    serp_config = None
    if org_ids:
        serp_config_res = await db.execute(
            select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id.in_(org_ids)).limit(1)
        )
        serp_config = serp_config_res.scalars().first()

    serp_provider_usage = {
        "connected": bool(serp_config and serp_config.provider and serp_config.provider != "none" and serp_config.enabled),
        "provider": serp_config.provider if serp_config else None,
        "provider_name": serp_config.provider.capitalize() if (serp_config and serp_config.provider) else None,
        "plan_name": None,
        "usage_model": None,
        "used": None,
        "limit": None,
        "remaining": None,
        "balance": None,
        "currency": None,
        "unit": None,
        "percentage_used": None,
        "renewal_date": None,
        "last_synced_at": serp_config.last_synced_at.isoformat() if (serp_config and serp_config.last_synced_at) else None,
        "usage_available": False,
        "locallift_requests_used": serp_units_used,
    }

    if serp_config and serp_config.enabled and serp_config.usage_info:
        u = serp_config.usage_info
        a = serp_config.account_info or {}
        serp_provider_usage.update({
            "plan_name": a.get("plan_name"),
            "usage_model": u.get("model"),
            "used": u.get("used"),
            "limit": u.get("limit"),
            "remaining": u.get("remaining"),
            "balance": u.get("balance"),
            "currency": u.get("currency"),
            "unit": u.get("unit"),
            "percentage_used": u.get("percentage_used"),
            "renewal_date": a.get("renewal_date"),
            "usage_available": True if u.get("model") != "unavailable" else False
        })

    ai_usage_res = await db.execute(
        select(func.coalesce(func.sum(AIUsageLog.total_tokens), 0)).where(
            AIUsageLog.project_id.in_(project_ids)
        )
    )
    ai_tokens_used = ai_usage_res.scalar() or 0

    geogrid_used_res = await db.execute(
        select(func.coalesce(func.sum(ScanJob.point_usage), 0)).where(
            ScanJob.project_id.in_(project_ids),
            ScanJob.job_type == JobType.GEO_GRID.value
        )
    )
    geogrid_points_used = geogrid_used_res.scalar() or (geogrid_scans * 25)

    # 10. Recent Activity Stream (Strictly customer's own projects)
    recent_jobs_res = await db.execute(
        select(ScanJob, Project.name)
        .join(Project, ScanJob.project_id == Project.id)
        .where(ScanJob.project_id.in_(project_ids))
        .order_by(ScanJob.created_at.desc())
        .limit(10)
    )
    recent_jobs = recent_jobs_res.all()

    recent_activity = []
    for job, p_name in recent_jobs:
        recent_activity.append({
            "id": f"job-{job.id}",
            "project_id": job.project_id,
            "project_name": p_name,
            "type": "scan_job",
            "job_type": job.job_type,
            "title": f"{p_name} — {job.job_type.replace('_', ' ').title()} {job.status.lower()}",
            "status": job.status,
            "timestamp": job.created_at.isoformat() if job.created_at else None,
            "details": f"{job.processed_items}/{job.total_items} items processed" if job.total_items else job.current_stage
        })

    # Also add recent task activities
    recent_tasks_res = await db.execute(
        select(SEOTask, Project.name)
        .join(Project, SEOTask.project_id == Project.id)
        .where(SEOTask.project_id.in_(project_ids))
        .order_by(SEOTask.created_at.desc())
        .limit(5)
    )
    for task, p_name in recent_tasks_res.all():
        task_ts = task.completed_at or task.created_at
        recent_activity.append({
            "id": f"task-{task.id}",
            "project_id": task.project_id,
            "project_name": p_name,
            "type": "task",
            "job_type": "task_update",
            "title": f"{p_name} — Task: {task.title}",
            "status": str(task.status.value) if hasattr(task.status, 'value') else str(task.status),
            "timestamp": task_ts.isoformat() if task_ts else None,
            "details": f"Priority: {task.priority.value if hasattr(task.priority, 'value') else str(task.priority)}"
        })

    # Sort combined recent activity by timestamp desc
    recent_activity.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    recent_activity = recent_activity[:12]

    # 11. Customer Alerts
    alerts = []
    # Failed scan alert
    failed_scans_res = await db.execute(
        select(ScanJob, Project.name)
        .join(Project, ScanJob.project_id == Project.id)
        .where(
            ScanJob.project_id.in_(project_ids),
            ScanJob.status.in_([JobStatus.FAILED.value, JobStatus.COMPLETED_WITH_ERRORS.value]),
            ScanJob.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        )
        .order_by(ScanJob.created_at.desc())
        .limit(3)
    )
    for fjob, p_name in failed_scans_res.all():
        alerts.append({
            "id": f"alert-fail-{fjob.id}",
            "severity": "warning",
            "project_id": fjob.project_id,
            "project_name": p_name,
            "title": f"Scan Warning on {p_name}",
            "message": f"{fjob.job_type.replace('_', ' ').title()} encountered an issue: {fjob.current_stage or 'Scan incomplete'}",
            "timestamp": fjob.created_at.isoformat() if fjob.created_at else None
        })

    # High severity audit issues alert
    for ps in project_summaries:
        if ps["open_issues_count"] > 5:
            alerts.append({
                "id": f"alert-issues-{ps['id']}",
                "severity": "info",
                "project_id": ps["id"],
                "project_name": ps["name"],
                "title": f"Audit Opportunities on {ps['name']}",
                "message": f"{ps['open_issues_count']} open SEO issues detected. Review audit to improve health score.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    # Dynamic SERP Alerts based on external provider usage (No fake/hardcoded alerts)
    if serp_provider_usage["connected"] and serp_provider_usage["usage_available"]:
        pct = serp_provider_usage.get("percentage_used")
        rem = serp_provider_usage.get("remaining")
        bal = serp_provider_usage.get("balance")
        pname = serp_provider_usage.get("provider_name") or "SERP"

        if pct is not None:
            if pct >= 100 or (rem is not None and rem <= 0):
                alerts.append({
                    "id": "alert-serp-quota-exhausted",
                    "severity": "critical",
                    "title": f"{pname} Quota Exceeded",
                    "message": f"Your {pname} provider account has reached its search limit. Upgrade or renew your provider plan.",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            elif pct >= 90:
                alerts.append({
                    "id": "alert-serp-quota-90",
                    "severity": "warning",
                    "title": f"{pname} Usage Approaching Limit",
                    "message": f"Your {pname} provider usage is at {pct:.1f}%. {rem} searches remaining.",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            elif pct >= 75:
                alerts.append({
                    "id": "alert-serp-quota-75",
                    "severity": "info",
                    "title": f"{pname} Usage at {pct:.1f}%",
                    "message": f"You have utilized {pct:.1f}% of your monthly {pname} allowance.",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        elif bal is not None and bal < 5.0:
            alerts.append({
                "id": "alert-serp-balance-low",
                "severity": "warning",
                "title": f"Low {pname} Balance",
                "message": f"Your {pname} balance is ${bal:.2f} {serp_provider_usage.get('currency', 'USD')}. Top up to avoid search interruption.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    return {
        "summary": {
            "total_projects": len(projects),
            "total_websites": total_websites,
            "tracked_keywords": tracked_keywords,
            "active_scan_jobs": active_scan_jobs,
            "completed_scans": completed_scans,
            "open_tasks": open_tasks,
            "total_reviews": total_reviews,
            "citation_records": citation_records,
            "geogrid_scans": geogrid_scans,
        },
        "projects": project_summaries,
        "usage": {
            "serp_provider": serp_provider_usage,
            "serp_used": serp_units_used,
            "ai_tokens_used": ai_tokens_used,
            "ai_tokens_limit": 100000,
            "keywords_used": tracked_keywords,
            "keywords_limit": 200,
            "geogrid_used": geogrid_points_used,
            "geogrid_limit": 1000,
        },
        "recent_activity": recent_activity,
        "alerts": alerts
    }


@router.get("/analytics")
async def get_user_central_dashboard_analytics(
    date_range: str = Query("30d", regex="^(today|7d|30d|90d|all)$"),
    project_id: Optional[int] = Query(None),
    metric: Optional[str] = Query("all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    USER CENTRAL DASHBOARD - Multi-project analytics and comparative telemetry.
    Strictly aggregates data across the logged-in customer's authorized projects.
    Supports time slicing (today, 7d, 30d, 90d) and project filtering.
    """
    authorized_projects = await get_authorized_projects_list(current_user, db)
    auth_proj_ids = [p.id for p in authorized_projects]

    if not auth_proj_ids:
        return {
            "timeline": [],
            "project_comparison": [],
            "ranking_distribution": {"top3": 0, "top10": 0, "top20": 0, "below20": 0, "unranked": 0},
            "metrics": {}
        }

    # Filter by specific project if requested
    if project_id is not None:
        if project_id not in auth_proj_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Project does not belong to your authorized organization."
            )
        target_proj_ids = [project_id]
        active_projects_map = {p.id: p.name for p in authorized_projects if p.id == project_id}
    else:
        target_proj_ids = auth_proj_ids
        active_projects_map = {p.id: p.name for p in authorized_projects}

    # Calculate start date
    now = datetime.now(timezone.utc)
    if date_range == "today":
        start_date = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        days = 1
    elif date_range == "7d":
        start_date = now - timedelta(days=7)
        days = 7
    elif date_range == "30d":
        start_date = now - timedelta(days=30)
        days = 30
    elif date_range == "90d":
        start_date = now - timedelta(days=90)
        days = 90
    else:
        start_date = now - timedelta(days=180)
        days = 180

    # 1. Timeline series generation (Day by Day)
    timeline_map: Dict[str, Dict[str, Any]] = {}
    cur = start_date
    while cur <= now + timedelta(days=1):
        date_str = cur.strftime("%Y-%m-%d")
        timeline_map[date_str] = {
            "date": date_str,
            "label": cur.strftime("%b %d"),
            "scans_completed": 0,
            "keywords_scanned": 0,
            "reviews_synced": 0,
            "citations_found": 0,
            "tasks_completed": 0,
            "serp_queries": 0,
            "ai_tokens": 0
        }
        cur += timedelta(days=1)

    # Scans timeline
    scans_stmt = select(ScanJob).where(
        ScanJob.project_id.in_(target_proj_ids),
        ScanJob.created_at >= start_date
    )
    scans_res = await db.execute(scans_stmt)
    for sj in scans_res.scalars().all():
        if sj.created_at:
            ds = sj.created_at.strftime("%Y-%m-%d")
            if ds in timeline_map:
                if sj.status in [JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_ERRORS.value]:
                    timeline_map[ds]["scans_completed"] += 1
                if sj.job_type == JobType.KEYWORD_RANK.value:
                    timeline_map[ds]["keywords_scanned"] += sj.processed_items or 1

    # Reviews timeline
    rev_stmt = select(Review).where(
        Review.project_id.in_(target_proj_ids),
        Review.created_at >= start_date
    )
    rev_res = await db.execute(rev_stmt)
    for r in rev_res.scalars().all():
        if r.created_at:
            ds = r.created_at.strftime("%Y-%m-%d")
            if ds in timeline_map:
                timeline_map[ds]["reviews_synced"] += 1

    # Citations timeline
    cit_stmt = select(Citation).where(
        Citation.project_id.in_(target_proj_ids),
        Citation.created_at >= start_date
    )
    cit_res = await db.execute(cit_stmt)
    for c in cit_res.scalars().all():
        if c.created_at:
            ds = c.created_at.strftime("%Y-%m-%d")
            if ds in timeline_map:
                timeline_map[ds]["citations_found"] += 1

    # Tasks completed timeline
    tasks_stmt = select(SEOTask).where(
        SEOTask.project_id.in_(target_proj_ids),
        SEOTask.status == TaskStatus.COMPLETED,
        or_(
            and_(SEOTask.completed_at.isnot(None), SEOTask.completed_at >= start_date),
            and_(SEOTask.completed_at.is_(None), SEOTask.created_at >= start_date)
        )
    )
    tasks_res = await db.execute(tasks_stmt)
    for t in tasks_res.scalars().all():
        t_date = t.completed_at or t.created_at
        if t_date:
            ds = t_date.strftime("%Y-%m-%d")
            if ds in timeline_map:
                timeline_map[ds]["tasks_completed"] += 1

    # SERP Provider usage timeline
    serp_stmt = select(ProviderUsageRecord).where(
        ProviderUsageRecord.project_id.in_(target_proj_ids),
        ProviderUsageRecord.created_at >= start_date
    )
    serp_res = await db.execute(serp_stmt)
    for su in serp_res.scalars().all():
        if su.created_at:
            ds = su.created_at.strftime("%Y-%m-%d")
            if ds in timeline_map:
                timeline_map[ds]["serp_queries"] += su.units_consumed

    # AI Tokens timeline
    ai_stmt = select(AIUsageLog).where(
        AIUsageLog.project_id.in_(target_proj_ids),
        AIUsageLog.created_at >= start_date
    )
    ai_res = await db.execute(ai_stmt)
    for al in ai_res.scalars().all():
        if al.created_at:
            ds = al.created_at.strftime("%Y-%m-%d")
            if ds in timeline_map:
                timeline_map[ds]["ai_tokens"] += (al.total_tokens or 0)

    # Convert sorted timeline list
    timeline = [timeline_map[k] for k in sorted(timeline_map.keys())]

    # 2. Project Activity Comparison (Bar / distribution by customer's projects)
    project_comparison = []
    for pid, pname in active_projects_map.items():
        # Scans count for project in range
        p_scans_res = await db.execute(
            select(func.count(ScanJob.id)).where(
                ScanJob.project_id == pid,
                ScanJob.created_at >= start_date
            )
        )
        p_scans = p_scans_res.scalar() or 0

        # Keywords count
        p_kw_res = await db.execute(
            select(func.count(Keyword.id)).where(Keyword.project_id == pid)
        )
        p_kw = p_kw_res.scalar() or 0

        # Health score
        p_obj = next((p for p in authorized_projects if p.id == pid), None)
        h_score = p_obj.health_score if p_obj else None

        # Citations
        p_cit_res = await db.execute(
            select(func.count(Citation.id)).where(Citation.project_id == pid)
        )
        p_cit = p_cit_res.scalar() or 0

        # Reviews
        p_rev_res = await db.execute(
            select(func.count(Review.id)).where(Review.project_id == pid)
        )
        p_rev = p_rev_res.scalar() or 0

        project_comparison.append({
            "project_id": pid,
            "project_name": pname,
            "domain": p_obj.domain if p_obj else "",
            "category": p_obj.primary_category if p_obj else "Local Business",
            "health_score": h_score or 0,
            "keywords_count": p_kw,
            "scans_count": p_scans,
            "citations_count": p_cit,
            "reviews_count": p_rev,
            "relative_activity_score": min(100, (p_scans * 15) + (p_kw * 2) + p_cit + p_rev)
        })

    # Sort project comparison by relative activity descending
    project_comparison.sort(key=lambda x: x["relative_activity_score"], reverse=True)

    # 3. Ranking Distribution across user's keywords
    rank_dist = {"top3": 0, "top10": 0, "top20": 0, "below20": 0, "unranked": 0}
    kw_ranks_res = await db.execute(
        select(Keyword.current_rank).where(
            Keyword.project_id.in_(target_proj_ids)
        )
    )
    for r_val in kw_ranks_res.scalars().all():
        if r_val is None or r_val <= 0:
            rank_dist["unranked"] += 1
        elif r_val <= 3:
            rank_dist["top3"] += 1
        elif r_val <= 10:
            rank_dist["top10"] += 1
        elif r_val <= 20:
            rank_dist["top20"] += 1
        else:
            rank_dist["below20"] += 1

    return {
        "date_range": date_range,
        "project_filter": project_id,
        "timeline": timeline,
        "project_comparison": project_comparison,
        "ranking_distribution": rank_dist,
        "summary": {
            "total_timeline_scans": sum(t["scans_completed"] for t in timeline),
            "total_timeline_reviews": sum(t["reviews_synced"] for t in timeline),
            "total_timeline_citations": sum(t["citations_found"] for t in timeline),
            "total_timeline_tasks": sum(t["tasks_completed"] for t in timeline),
            "total_timeline_serp": sum(t["serp_queries"] for t in timeline),
            "total_timeline_ai": sum(t["ai_tokens"] for t in timeline),
        }
    }
