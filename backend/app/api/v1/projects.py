import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.core.deps import get_current_user, verify_project_access, verify_client_access, get_user_organization_ids
from app.core.audit_logger import log_user_action
from app.models.user import User, OrganizationMember
from app.models.project import Project, Location, Website
from app.models.audit import SEOAudit, SEOIssue, SEOTask, IssueSeverity, IssueStatus
from app.models.gbp import GoogleBusinessProfile, GoogleAccount
from app.models.ranking import Keyword
from app.models.local_seo import Review
from app.models.analytics import GSCMetric
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut, DashboardSummaryOut, LocationCreate, LocationUpdate, LocationOut
from app.services.category_taxonomy import CategoryTaxonomy

logger = logging.getLogger("locallift.api.projects")

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/categories")
async def list_business_categories(
    q: Optional[str] = None,
    group: Optional[str] = None,
    popular_only: bool = False,
    limit: int = 30
):
    """
    Search and retrieve business categories from the comprehensive taxonomy.
    Supports query autocomplete, group filtering, and popular category highlights.
    """
    items = CategoryTaxonomy.search(query=q, group=group, popular_only=popular_only, limit=limit)
    groups = CategoryTaxonomy.get_groups()
    return {
        "items": items,
        "total": len(items),
        "groups": groups
    }

@router.get("", response_model=List[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.is_superuser:
        stmt = select(Project).options(
            selectinload(Project.locations),
            selectinload(Project.team_memberships)
        ).order_by(Project.id.desc())
        result = await db.execute(stmt)
        projects = result.scalars().unique().all()
        for p in projects:
            active_count = sum(1 for m in p.team_memberships if m.status == 'active') if p.team_memberships else 0
            p.team_member_count = 1 + active_count
            if p.additional_categories is None:
                p.additional_categories = []
        return projects

    mem_result = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id))
    memberships = mem_result.scalars().all()
    org_ids = [m.organization_id for m in memberships]

    from app.models.team import ProjectMembership
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

    from sqlalchemy import or_
    stmt = select(Project).options(
        selectinload(Project.locations),
        selectinload(Project.team_memberships)
    ).where(or_(*conditions)).order_by(Project.id.desc())

    result = await db.execute(stmt)
    projects = result.scalars().unique().all()

    for p in projects:
        active_count = sum(1 for m in p.team_memberships if m.status == 'active') if p.team_memberships else 0
        p.team_member_count = 1 + active_count
        if p.additional_categories is None:
            p.additional_categories = []

    return projects



@router.post("", response_model=ProjectOut)
async def create_project(
    request: Request,
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate organization authorization
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids and not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    if project_in.organization_id:
        if not current_user.is_superuser and project_in.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot create a project under an unauthorized organization."
            )
        org_id = project_in.organization_id
    else:
        if not org_ids:
            raise HTTPException(status_code=400, detail="User has no associated organization to create project under.")
        org_id = org_ids[0]

    # Validate client_id belongs to the same organization
    if project_in.client_id:
        await verify_client_access(project_in.client_id, org_id, db)

    # Normalize primary and additional categories
    normalized_primary = CategoryTaxonomy.normalize_category_name(project_in.primary_category)
    normalized_additionals = []
    if project_in.additional_categories:
        seen = {normalized_primary.lower()}
        for cat in project_in.additional_categories:
            if cat and cat.strip():
                n = CategoryTaxonomy.normalize_category_name(cat)
                if n.lower() not in seen:
                    seen.add(n.lower())
                    normalized_additionals.append(n)

    project = Project(
        organization_id=org_id,
        client_id=project_in.client_id,
        name=project_in.name,
        domain=project_in.domain.replace("https://", "").replace("http://", "").rstrip("/"),
        primary_category=normalized_primary,
        additional_categories=normalized_additionals,
        country=project_in.country,
        public_maps_url=project_in.public_maps_url,
        health_score=None,
        technical_score=None,
        onpage_score=None,
        local_score=None,
        gbp_score=None,
        reviews_score=None,
        citations_score=None,
        keywords_score=None,
        maps_score=None
    )
    db.add(project)
    await db.flush()

    # Create location
    loc = None
    if project_in.location:
        lat = project_in.location.latitude
        lng = project_in.location.longitude
        loc_country = project_in.location.country or project_in.country

        # If coordinates not supplied, resolve via real geocoding provider
        if lat is None or lng is None:
            from app.services.geocoding import GeocodingService
            geo_coords = await GeocodingService.geocode_address(
                address=project_in.location.address,
                city=project_in.location.city,
                state=project_in.location.state,
                postal_code=project_in.location.postal_code,
                country=loc_country
            )
            if geo_coords:
                lat, lng = geo_coords

        loc = Location(
            project_id=project.id,
            name=project_in.location.name,
            address=project_in.location.address,
            city=project_in.location.city,
            state=project_in.location.state,
            postal_code=project_in.location.postal_code,
            country=loc_country,
            phone=project_in.location.phone,
            latitude=lat,
            longitude=lng
        )
        db.add(loc)

    # If public_maps_url is provided, attempt Places lookup without failing project creation
    if project_in.public_maps_url:
        try:
            from app.services.google.public_maps_service import PublicGoogleMapsService
            loc_str = ""
            if loc:
                loc_str = f"{loc.city or ''} {loc.state or ''}".strip()
            lookup_res = await PublicGoogleMapsService.lookup_public_place(
                organization_id=org_id,
                project_id=project.id,
                db=db,
                business_name=project.name,
                location_str=loc_str,
                maps_url=project_in.public_maps_url,
                country=project.country
            )
            listing = lookup_res.get("listing")
            if listing and loc:
                if listing.place_id and not loc.place_id:
                    loc.place_id = listing.place_id
                elif listing.place_id:
                    loc.place_id = listing.place_id
                if loc.latitude is None and listing.latitude is not None:
                    loc.latitude = listing.latitude
                if loc.longitude is None and listing.longitude is not None:
                    loc.longitude = listing.longitude
                if not loc.address and listing.formatted_address:
                    loc.address = listing.formatted_address
                if not loc.phone and listing.phone:
                    loc.phone = listing.phone
            elif listing and not loc:
                # Create location from public listing if no manual location was supplied
                loc = Location(
                    project_id=project.id,
                    name=project.name,
                    address=listing.formatted_address,
                    country=project.country,
                    phone=listing.phone,
                    latitude=listing.latitude,
                    longitude=listing.longitude,
                    place_id=listing.place_id
                )
                db.add(loc)
        except Exception as e:
            logger.warning(f"Non-fatal error resolving public maps URL during project creation: {e}")

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
    created_proj = result.scalars().first()
    log_user_action(
        request, "CREATE_PROJECT",
        user_id=current_user.id,
        organization_id=org_id,
        project_id=created_proj.id,
        project_name=created_proj.name,
        domain=created_proj.domain
    )
    return created_proj


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.id == project.id)
    )
    return result.scalars().first()


@router.patch("/{project_id}", response_model=ProjectOut)
@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    request: Request,
    project_id: int,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)
    update_data = project_in.model_dump(exclude_unset=True)
    if "primary_category" in update_data and update_data["primary_category"]:
        update_data["primary_category"] = CategoryTaxonomy.normalize_category_name(update_data["primary_category"])
    if "additional_categories" in update_data and update_data["additional_categories"] is not None:
        target_prim = update_data.get("primary_category") or project.primary_category or ""
        seen = {target_prim.lower()}
        clean_additionals = []
        for cat in update_data["additional_categories"]:
            if cat and cat.strip():
                norm = CategoryTaxonomy.normalize_category_name(cat)
                if norm.lower() not in seen:
                    seen.add(norm.lower())
                    clean_additionals.append(norm)
        update_data["additional_categories"] = clean_additionals

    for field, val in update_data.items():
        if hasattr(project, field):
            setattr(project, field, val)
    await db.commit()
    result = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.id == project.id)
    )
    updated_proj = result.scalars().first()
    log_user_action(
        request, "UPDATE_PROJECT",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        project_name=updated_proj.name
    )
    return updated_proj


@router.delete("/{project_id}")
async def delete_project(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)
    org_id = project.organization_id
    proj_name = project.name
    await db.delete(project)
    await db.commit()
    log_user_action(
        request, "DELETE_PROJECT",
        user_id=current_user.id,
        organization_id=org_id,
        project_id=project_id,
        project_name=proj_name
    )
    return {"message": "Project deleted successfully", "id": project_id}


@router.get("/{project_id}/dashboard", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "OPEN_DASHBOARD",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id
    )

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

    # Fetch latest real GSC metrics & connection status
    from app.models.connections import GoogleConnection, GoogleSearchConsoleProperty, GoogleAnalyticsProperty
    from app.models.analytics import GA4Metric
    from app.services.google.connections_service import GoogleConnectionsService

    gsc_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "search_console", db)
    gsc_prop_res = await db.execute(
        select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.project_id == project_id)
    )
    gsc_prop = gsc_prop_res.scalars().first()

    gsc_res = await db.execute(
        select(GSCMetric).where(GSCMetric.project_id == project_id).order_by(GSCMetric.date.desc())
    )
    latest_gsc = gsc_res.scalars().first()

    if gsc_conn and gsc_conn.status == "connected" and latest_gsc:
        gsc_summary = {
            "connected": True,
            "has_data": True,
            "clicks": latest_gsc.clicks,
            "impressions": latest_gsc.impressions,
            "ctr": latest_gsc.ctr,
            "avg_position": latest_gsc.average_position
        }
    elif gsc_conn and gsc_conn.status == "connected":
        gsc_summary = {
            "connected": True,
            "has_data": False,
            "clicks": None,
            "impressions": None,
            "ctr": None,
            "avg_position": None,
            "status": "waiting_for_data" if gsc_prop else "needs_property_selection"
        }
    else:
        gsc_summary = {
            "connected": False,
            "has_data": False,
            "clicks": None,
            "impressions": None,
            "ctr": None,
            "avg_position": None
        }

    # Fetch latest real GA4 metrics & connection status
    ga_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "analytics", db)
    ga4_res = await db.execute(
        select(GA4Metric).where(GA4Metric.project_id == project_id).order_by(GA4Metric.date.desc())
    )
    latest_ga4 = ga4_res.scalars().first()

    if ga_conn and ga_conn.status == "connected" and latest_ga4:
        ga4_summary = {
            "connected": True,
            "has_data": True,
            "organic_users": latest_ga4.organic_users,
            "sessions": latest_ga4.sessions,
            "engagement_rate": latest_ga4.engagement_rate,
            "conversions": latest_ga4.conversions
        }
    elif ga_conn and ga_conn.status == "connected":
        ga4_summary = {
            "connected": True,
            "has_data": False,
            "organic_users": None,
            "sessions": None,
            "engagement_rate": None,
            "conversions": None
        }
    else:
        ga4_summary = {
            "connected": False,
            "has_data": False,
            "organic_users": None,
            "sessions": None,
            "engagement_rate": None,
            "conversions": None
        }

    from sqlalchemy import func
    from app.models.audit import TaskStatus

    # Real aggregated counts across entire project
    open_issues_count = (await db.execute(
        select(func.count(SEOIssue.id)).where(SEOIssue.project_id == project_id, SEOIssue.status == IssueStatus.OPEN)
    )).scalar() or 0

    active_tasks_count = (await db.execute(
        select(func.count(SEOTask.id)).where(SEOTask.project_id == project_id, SEOTask.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]))
    )).scalar() or 0

    tracked_keywords_count = (await db.execute(
        select(func.count(Keyword.id)).where(Keyword.project_id == project_id)
    )).scalar() or 0

    reviews_total_count = (await db.execute(
        select(func.count(Review.id)).where(Review.project_id == project_id)
    )).scalar() or 0

    return DashboardSummaryOut(
        health_score=project.health_score,
        scores={
            "technical": project.technical_score,
            "onpage": project.onpage_score,
            "local": project.local_score,
            "gbp": project.gbp_score,
            "reviews": project.reviews_score,
            "citations": project.citations_score,
            "keywords": project.keywords_score,
            "maps": project.maps_score,
        },
        counts={
            "open_issues": open_issues_count,
            "active_tasks": active_tasks_count,
            "tracked_keywords": tracked_keywords_count,
            "reviews_total": reviews_total_count
        },
        recent_issues=recent_issues,
        recent_tasks=recent_tasks,
        recent_reviews=recent_reviews,
        top_keywords=top_keywords,
        gbp_summary=gbp_summary,
        gsc_summary=gsc_summary,
        ga4_summary=ga4_summary
    )


@router.get("/{project_id}/locations", response_model=List[LocationOut])
async def list_project_locations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all locations belonging to an authorized project.
    """
    await verify_project_access(project_id, current_user, db)
    stmt = select(Location).where(Location.project_id == project_id).order_by(Location.id.asc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{project_id}/locations", response_model=LocationOut)
async def create_project_location(
    project_id: int,
    location_in: LocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new location for an authorized project with strict coordinate bounds validation (-90 to 90 lat, -180 to 180 lng).
    """
    project = await verify_project_access(project_id, current_user, db)

    lat = location_in.latitude
    lng = location_in.longitude

    if lat is not None and not (-90.0 <= lat <= 90.0):
        raise HTTPException(status_code=400, detail="INVALID_LATITUDE: Latitude must be between -90 and 90 degrees.")
    if lng is not None and not (-180.0 <= lng <= 180.0):
        raise HTTPException(status_code=400, detail="INVALID_LONGITUDE: Longitude must be between -180 and 180 degrees.")

    if (lat is None or lng is None) and (location_in.address or location_in.city):
        from app.services.geocoding import GeocodingService
        coords = await GeocodingService.geocode_address(
            address=location_in.address,
            city=location_in.city,
            state=location_in.state,
            postal_code=location_in.postal_code,
            country=location_in.country
        )
        if coords:
            lat, lng = coords

    loc = Location(
        project_id=project_id,
        name=location_in.name,
        address=location_in.address,
        city=location_in.city,
        state=location_in.state,
        postal_code=location_in.postal_code,
        country=location_in.country or (project.country if hasattr(project, 'country') else None),
        phone=location_in.phone,
        latitude=lat,
        longitude=lng,
        place_id=location_in.place_id
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


@router.put("/{project_id}/locations/{location_id}", response_model=LocationOut)
@router.patch("/{project_id}/locations/{location_id}", response_model=LocationOut)
async def update_project_location(
    request: Request,
    project_id: int,
    location_id: int,
    location_in: LocationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing location record for a project. Validates coordinate bounds and logs action.
    """
    project = await verify_project_access(project_id, current_user, db)
    
    stmt = select(Location).where(Location.id == location_id, Location.project_id == project_id)
    res = await db.execute(stmt)
    loc = res.scalars().first()
    if not loc:
        raise HTTPException(
            status_code=404,
            detail=f"LOCATION_NOT_FOUND: Location ID {location_id} does not exist in project {project_id}."
        )

    update_data = location_in.model_dump(exclude_unset=True)
    if "latitude" in update_data and update_data["latitude"] is not None:
        lat = update_data["latitude"]
        if not (-90.0 <= lat <= 90.0):
            raise HTTPException(status_code=400, detail="INVALID_LATITUDE: Latitude must be between -90 and 90 degrees.")
    
    if "longitude" in update_data and update_data["longitude"] is not None:
        lng = update_data["longitude"]
        if not (-180.0 <= lng <= 180.0):
            raise HTTPException(status_code=400, detail="INVALID_LONGITUDE: Longitude must be between -180 and 180 degrees.")

    for field, val in update_data.items():
        setattr(loc, field, val)

    await db.commit()
    await db.refresh(loc)

    log_user_action(
        request, "SAVE_LOCATION_COORDINATES",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id,
        location_id=location_id,
        latitude=loc.latitude,
        longitude=loc.longitude
    )
    return loc


@router.get("/{project_id}/local-intelligence-summary")
async def get_local_intelligence_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Aggregated Local SEO Intelligence Summary for dashboard consumption.
    Every metric comes from real backend data — no fabricated fallbacks.
    Returns None/null for unavailable metrics.
    """
    from sqlalchemy import func
    from app.models.audit import LocalAuditRun, LocalAuditFinding
    from app.models.local_seo import Citation, BusinessProfile
    from app.models.ranking import GeoGridScan
    from app.services.local_seo.business_profile_service import BusinessProfileService

    await verify_project_access(project_id, current_user, db)

    # 1. Latest Local Audit
    audit_res = await db.execute(
        select(LocalAuditRun)
        .where(LocalAuditRun.project_id == project_id)
        .order_by(LocalAuditRun.id.desc())
    )
    latest_audit = audit_res.scalars().first()

    audit_data = None
    priority_findings = []
    if latest_audit:
        # Get top priority findings (CRITICAL/WARNING, FAIL status)
        findings_res = await db.execute(
            select(LocalAuditFinding)
            .where(
                LocalAuditFinding.audit_run_id == latest_audit.id,
                LocalAuditFinding.status.in_(["FAIL", "PARTIAL"]),
            )
            .order_by(
                # Critical first, then warning
                LocalAuditFinding.severity.asc(),
                LocalAuditFinding.id.asc()
            )
            .limit(10)
        )
        findings = findings_res.scalars().all()
        priority_findings = [
            {
                "id": f.id,
                "category": f.category,
                "check_key": f.check_key,
                "title": f.title,
                "status": f.status,
                "severity": f.severity,
                "evidence": f.evidence,
                "recommendation": f.recommendation,
                "verification_status": f.verification_status,
            }
            for f in findings
        ]

        audit_data = {
            "id": latest_audit.id,
            "overall_score": latest_audit.overall_score,
            "category_scores": latest_audit.category_scores or {},
            "findings_summary": latest_audit.findings_summary or {},
            "status": latest_audit.status,
            "completed_at": latest_audit.completed_at.isoformat() if latest_audit.completed_at else None,
        }

    # 2. Latest Geo-Grid Scan
    geo_res = await db.execute(
        select(GeoGridScan)
        .where(GeoGridScan.project_id == project_id)
        .order_by(GeoGridScan.id.desc())
    )
    latest_geo = geo_res.scalars().first()

    geo_data = None
    if latest_geo:
        geo_data = {
            "id": latest_geo.id,
            "keyword": latest_geo.keyword if hasattr(latest_geo, 'keyword') else None,
            "average_rank": latest_geo.average_rank,
            "local_visibility_pct": latest_geo.local_visibility_pct,
            "total_points": latest_geo.total_points if hasattr(latest_geo, 'total_points') else None,
            "scan_status": latest_geo.scan_status if hasattr(latest_geo, 'scan_status') else None,
            "scanned_at": latest_geo.scanned_at.isoformat() if latest_geo.scanned_at else None,
        }

    # 3. Keywords
    kw_count = (await db.execute(
        select(func.count(Keyword.id)).where(Keyword.project_id == project_id)
    )).scalar() or 0

    kw_avg_rank_res = await db.execute(
        select(func.avg(Keyword.current_rank)).where(
            Keyword.project_id == project_id,
            Keyword.current_rank.isnot(None)
        )
    )
    kw_avg_rank = kw_avg_rank_res.scalar()

    # 4. Reviews
    rev_count = (await db.execute(
        select(func.count(Review.id)).where(Review.project_id == project_id)
    )).scalar() or 0

    rev_avg_rating_res = await db.execute(
        select(func.avg(Review.rating)).where(Review.project_id == project_id)
    )
    rev_avg_rating = rev_avg_rating_res.scalar()

    unanswered_res = await db.execute(
        select(func.count(Review.id)).where(
            Review.project_id == project_id,
            Review.response_status.in_(["unanswered", None])
        )
    )
    unanswered_count = unanswered_res.scalar() or 0

    # 5. Citations
    cit_count = (await db.execute(
        select(func.count(Citation.id)).where(Citation.project_id == project_id)
    )).scalar() or 0

    nap_conflict_count = (await db.execute(
        select(func.count(Citation.id)).where(
            Citation.project_id == project_id,
            Citation.nap_status == "mismatch"
        )
    )).scalar() or 0

    # 6. Business Profile
    bp_res = await db.execute(
        select(BusinessProfile).where(BusinessProfile.project_id == project_id)
    )
    bp = bp_res.scalars().first()

    profile_data = None
    if bp:
        profile_data = {
            "business_name": bp.business_name,
            "verification_status": bp.verification_status,
            "has_coordinates": bp.latitude is not None and bp.longitude is not None,
            "has_phone": bp.primary_phone is not None,
            "has_address": bp.primary_address is not None,
            "primary_category": bp.primary_category,
        }

    # 7. Open issues & tasks
    from app.models.audit import IssueStatus, TaskStatus, SEOIssue, SEOTask
    open_issues = (await db.execute(
        select(func.count(SEOIssue.id)).where(
            SEOIssue.project_id == project_id, SEOIssue.status == IssueStatus.OPEN
        )
    )).scalar() or 0

    active_tasks = (await db.execute(
        select(func.count(SEOTask.id)).where(
            SEOTask.project_id == project_id,
            SEOTask.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS])
        )
    )).scalar() or 0

    # 8. GBP connection
    acc_res = await db.execute(
        select(GoogleAccount).where(GoogleAccount.project_id == project_id)
    )
    google_acc = acc_res.scalars().first()
    gbp = None
    if google_acc:
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == google_acc.id)
        )
        gbp = gbp_res.scalars().first()

    gbp_data = None
    if gbp:
        gbp_data = {
            "connected": True,
            "business_name": gbp.business_name,
            "completeness_score": gbp.completeness_score,
            "is_verified": gbp.is_verified if hasattr(gbp, 'is_verified') else None,
        }

    matching_nap_cit = (await db.execute(
        select(func.count(Citation.id)).where(
            Citation.project_id == project_id,
            Citation.nap_status == "match"
        )
    )).scalar() or 0

    return {
        "project_id": project_id,
        "business_name": profile_data["business_name"] if profile_data else None,
        "overall_score": audit_data["overall_score"] if audit_data else None,
        "category_scores": audit_data["category_scores"] if audit_data else {},
        "geo_visibility_pct": geo_data["local_visibility_pct"] if geo_data else None,
        "total_keywords": kw_count,
        "total_reviews": rev_count,
        "average_rating": round(rev_avg_rating, 2) if rev_avg_rating else None,
        "total_citations": cit_count,
        "citations_matching_nap": matching_nap_cit,
        "audit": audit_data,
        "geo_visibility": geo_data,
        "keywords": {
            "total": kw_count,
            "average_rank": round(kw_avg_rank, 1) if kw_avg_rank else None,
        },
        "reviews": {
            "total": rev_count,
            "average_rating": round(rev_avg_rating, 2) if rev_avg_rating else None,
            "unanswered": unanswered_count,
        },
        "citations": {
            "total": cit_count,
            "matching_nap": matching_nap_cit,
            "nap_conflicts": nap_conflict_count,
        },
        "business_profile": profile_data,
        "gbp": gbp_data,
        "open_issues": open_issues,
        "active_tasks": active_tasks,
        "priority_findings": priority_findings,
    }
