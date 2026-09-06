from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, OrganizationMember
from app.models.project import Project, Location, Website
from app.models.audit import SEOAudit, SEOIssue, SEOTask, IssueSeverity, IssueStatus
from app.models.gbp import GoogleBusinessProfile, GoogleAccount
from app.models.ranking import Keyword
from app.models.local_seo import Review
from app.models.analytics import GSCMetric
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut, DashboardSummaryOut, LocationCreate, LocationOut

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=List[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id))
    memberships = mem_result.scalars().all()
    org_ids = [m.organization_id for m in memberships]

    result = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.organization_id.in_(org_ids))
    )
    return result.scalars().all()

@router.post("", response_model=ProjectOut)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find active organization
    mem_result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id))
    mem = mem_result.scalars().first()
    if not mem:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    org_id = project_in.organization_id or mem.organization_id

    project = Project(
        organization_id=org_id,
        client_id=project_in.client_id,
        name=project_in.name,
        domain=project_in.domain.replace("https://", "").replace("http://", "").rstrip("/"),
        primary_category=project_in.primary_category,
        country=project_in.country,
        health_score=0,
        technical_score=0,
        onpage_score=0,
        local_score=0,
        gbp_score=0,
        reviews_score=0,
        citations_score=0,
        keywords_score=0,
        maps_score=0
    )
    db.add(project)
    await db.flush()

    # Create location
    if project_in.location:
        loc = Location(
            project_id=project.id,
            name=project_in.location.name,
            address=project_in.location.address,
            city=project_in.location.city,
            state=project_in.location.state,
            postal_code=project_in.location.postal_code,
            country=project_in.location.country,
            phone=project_in.location.phone,
            latitude=project_in.location.latitude or -27.4698,
            longitude=project_in.location.longitude or 153.0251
        )
        db.add(loc)

    # Create initial website record
    website = Website(
        project_id=project.id,
        url=f"https://{project.domain}",
        status="ready"
    )
    db.add(website)

    await db.commit()
    
    # Reload with relations
    result = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.id == project.id)
    )
    return result.scalars().first()

@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.id == project_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/{project_id}/dashboard", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch recent issues
    issues_res = await db.execute(
        select(SEOIssue).where(SEOIssue.project_id == project_id).order_by(SEOIssue.id.desc()).limit(6)
    )
    recent_issues = [
        {
            "id": i.id,
            "title": i.title,
            "category": i.category,
            "severity": i.severity.value if hasattr(i.severity, 'value') else str(i.severity),
            "evidence": i.evidence,
            "why_it_matters": i.why_it_matters,
            "recommended_solution": i.recommended_solution,
            "action_type": i.action_type,
            "affected_url": i.affected_url,
            "status": i.status.value if hasattr(i.status, 'value') else str(i.status),
        }
        for i in issues_res.scalars().all()
    ]

    # Fetch recent tasks
    tasks_res = await db.execute(
        select(SEOTask).where(SEOTask.project_id == project_id).order_by(SEOTask.id.desc()).limit(6)
    )
    recent_tasks = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority.value if hasattr(t.priority, 'value') else str(t.priority),
            "category": t.category,
            "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
            "evidence": t.evidence,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in tasks_res.scalars().all()
    ]

    # Fetch top keywords
    kw_res = await db.execute(
        select(Keyword).where(Keyword.project_id == project_id).order_by(Keyword.current_rank.asc().nullslast()).limit(5)
    )
    top_keywords = [
        {
            "id": k.id,
            "keyword": k.keyword,
            "current_rank": k.current_rank,
            "previous_rank": k.previous_rank,
            "search_volume": k.search_volume,
            "target_location": k.target_location,
            "opportunity_score": k.opportunity_score
        }
        for k in kw_res.scalars().all()
    ]

    # Fetch recent reviews
    rev_res = await db.execute(
        select(Review).where(Review.project_id == project_id).order_by(Review.id.desc()).limit(5)
    )
    recent_reviews = [
        {
            "id": r.id,
            "author_name": r.author_name,
            "rating": r.rating,
            "review_text": r.review_text,
            "sentiment": r.sentiment,
            "response_status": r.response_status
        }
        for r in rev_res.scalars().all()
    ]

    # Fetch GBP summary scoped to project
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
    google_acc = acc_res.scalars().first()
    gbp = None
    if google_acc:
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == google_acc.id)
        )
        gbp = gbp_res.scalars().first()

    gbp_summary = {
        "connected": gbp is not None,
        "business_name": gbp.business_name if gbp else None,
        "completeness_score": gbp.completeness_score if gbp else 0,
        "search_impressions": gbp.search_impressions if gbp else 0,
        "maps_impressions": gbp.maps_impressions if gbp else 0,
        "calls": gbp.call_clicks if gbp else 0,
        "website_clicks": gbp.website_clicks if gbp else 0
    } if gbp else {"connected": False}

    # Fetch latest real GSC metrics if available
    gsc_res = await db.execute(
        select(GSCMetric).where(GSCMetric.project_id == project_id).order_by(GSCMetric.date.desc())
    )
    latest_gsc = gsc_res.scalars().first()
    gsc_summary = {
        "clicks": latest_gsc.clicks if latest_gsc else 0,
        "impressions": latest_gsc.impressions if latest_gsc else 0,
        "ctr": latest_gsc.ctr if latest_gsc else 0.0,
        "avg_position": latest_gsc.average_position if latest_gsc else 0.0
    }

    return DashboardSummaryOut(
        health_score=project.health_score or 0,
        scores={
            "technical": project.technical_score or 0,
            "onpage": project.onpage_score or 0,
            "local": project.local_score or 0,
            "gbp": project.gbp_score or 0,
            "reviews": project.reviews_score or 0,
            "citations": project.citations_score or 0,
            "keywords": project.keywords_score or 0,
            "maps": project.maps_score or 0,
        },
        counts={
            "open_issues": len([i for i in recent_issues if i["status"] == "open"]),
            "active_tasks": len([t for t in recent_tasks if t["status"] in ["open", "in_progress"]]),
            "tracked_keywords": len(top_keywords),
            "reviews_total": len(recent_reviews)
        },
        recent_issues=recent_issues,
        recent_tasks=recent_tasks,
        recent_reviews=recent_reviews,
        top_keywords=top_keywords,
        gbp_summary=gbp_summary,
        gsc_summary=gsc_summary
    )
