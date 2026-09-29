import math
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Body, Response
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user, verify_project_access
from app.core.audit_logger import log_user_action
from app.models.user import User
from app.models.project import Project, Location
from app.models.connections import PublicBusinessListing
from app.models.gbp import GoogleBusinessProfile
from app.models.local_seo import BusinessProfile
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan, GeoGridPointResult
from app.schemas.ranking import (
    KeywordCreate,
    KeywordOut,
    GeoGridScanOut,
    GeoGridScanRequest,
    KeywordCheckResponse,
    KeywordCheckAllResponse
)
from app.services.serp import get_serp_provider, get_organization_serp_provider, DomainMatcher, GeoGridScanner
from app.services.geocoding import GeocodingService
from app.services.reports.geogrid_pdf_service import GeoGridPDFService

DEFAULT_GEO_GRID_RADIUS_KM = 5.0

logger = logging.getLogger("locallift.keywords")

router = APIRouter(prefix="/keywords", tags=["Keywords & Rankings"])

@router.get("/{project_id}", response_model=List[KeywordOut])
async def list_keywords(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Keyword)
        .where(Keyword.project_id == project_id)
        .order_by(Keyword.current_rank.asc().nullslast())
    )
    return result.scalars().all()

@router.post("", response_model=KeywordOut)
async def add_keyword(
    request: Request,
    kw_in: KeywordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch project domain for accurate initial tracking and verify access
    project = await verify_project_access(kw_in.project_id, current_user, db)

    # Initial keyword record with no fake rank and null last_checked_at
    kw = Keyword(
        project_id=kw_in.project_id,
        keyword=kw_in.keyword.strip(),
        search_intent=kw_in.search_intent or "Commercial",
        search_volume=kw_in.search_volume,
        difficulty=kw_in.difficulty,
        target_location=kw_in.target_location.strip() if kw_in.target_location and kw_in.target_location.strip() else None,
        target_rank=kw_in.target_rank,
        current_rank=None,
        previous_rank=None,
        organic_rank=None,
        local_pack_rank=None,
        maps_rank=None,
        rank_status="NOT_CHECKED",
        ranking_url=None,
        ranking_title=None,
        serp_type="Local Pack",
        opportunity_score="HIGH" if kw_in.search_volume and kw_in.search_volume > 300 else None,
        business_relevance=kw_in.business_relevance or "High",
        last_checked_at=None,
        last_attempted_at=None
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)

    log_user_action(
        request, "CREATE_KEYWORD",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project.id,
        keyword=kw.keyword,
        target_location=kw.target_location
    )

    # If SERP provider is configured, perform initial live lookup via KeywordRankingService
    provider = await get_organization_serp_provider(db, project.organization_id)
    if getattr(provider, "is_configured", False):
        try:
            from app.services.serp.ranking_service import KeywordRankingService
            await KeywordRankingService.check_keyword(
                db=db,
                keyword_id=kw.id,
                project_id=project.id,
                organization_id=project.organization_id
            )
            await db.refresh(kw)
        except Exception as e:
            logger.warning(f"Initial SERP lookup on add_keyword notice: {e}")

    return kw

@router.post("/{keyword_id}/check", response_model=KeywordCheckResponse)
async def check_keyword_rank(
    request: Request,
    keyword_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a real SERP rank check for a single keyword against the project domain using canonical service.
    """
    kw_res = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = kw_res.scalars().first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    project = await verify_project_access(kw.project_id, current_user, db)
    log_user_action(
        request, "RUN_KEYWORD_RANK_CHECK",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project.id,
        keyword_id=kw.id,
        keyword=kw.keyword
    )

    from app.services.serp.ranking_service import KeywordRankingService
    res = await KeywordRankingService.check_keyword(
        db=db,
        keyword_id=kw.id,
        project_id=project.id,
        organization_id=project.organization_id
    )

    return KeywordCheckResponse(
        keyword_id=res["keyword_id"],
        keyword=res["keyword"],
        target_domain=res["target_domain"],
        current_rank=res["current_rank"],
        previous_rank=res["previous_rank"],
        organic_rank=res.get("organic_rank"),
        local_pack_rank=res.get("local_pack_rank"),
        maps_rank=res.get("maps_rank"),
        rank_movement=res.get("rank_movement"),
        movement_label=res.get("movement_label"),
        ranking_url=res.get("ranking_url"),
        ranking_title=res.get("ranking_title"),
        serp_type=res.get("serp_type", "Local Pack"),
        provider=res.get("provider", "serpapi"),
        status=res.get("status", "checked"),
        error_message=res.get("error_message"),
        last_checked_at=res.get("last_checked_at")
    )

@router.post("/{project_id}/check-all", response_model=KeywordCheckAllResponse)
async def check_all_project_keywords(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes real live SERP checks for all tracked keywords in a project using canonical service.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "RUN_ALL_KEYWORDS_CHECK",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id
    )

    from app.services.serp.ranking_service import KeywordRankingService
    res = await KeywordRankingService.check_all_project_keywords(
        db=db,
        project_id=project.id,
        organization_id=project.organization_id
    )

    formatted_results = [
        KeywordCheckResponse(
            keyword_id=r["keyword_id"],
            keyword=r["keyword"],
            target_domain=r["target_domain"],
            current_rank=r["current_rank"],
            previous_rank=r["previous_rank"],
            organic_rank=r.get("organic_rank"),
            local_pack_rank=r.get("local_pack_rank"),
            maps_rank=r.get("maps_rank"),
            rank_movement=r.get("rank_movement"),
            movement_label=r.get("movement_label"),
            ranking_url=r.get("ranking_url"),
            ranking_title=r.get("ranking_title"),
            serp_type=r.get("serp_type", "Local Pack"),
            provider=r.get("provider", "serpapi"),
            status=r.get("status", "checked"),
            error_message=r.get("error_message"),
            last_checked_at=r.get("last_checked_at")
        )
        for r in res["results"]
    ]

    return KeywordCheckAllResponse(
        project_id=res["project_id"],
        checked_count=res["checked_count"],
        not_found_count=res["not_found_count"],
        error_count=res["error_count"],
        provider=res["provider"],
        results=formatted_results,
        checked_at=res["checked_at"]
    )

@router.delete("/{keyword_id}")
async def delete_keyword(
    request: Request,
    keyword_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalars().first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    project = await verify_project_access(kw.project_id, current_user, db)
    log_user_action(
        request, "DELETE_KEYWORD",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project.id,
        keyword_id=keyword_id
    )

    await db.delete(kw)
    await db.commit()
    return {"message": "Keyword deleted successfully"}

# ---------------------------------------------------------------------------
# Real 5x5 Geo-Grid Endpoints
# ---------------------------------------------------------------------------
# Geo-Grid Scanning & Real Cooperative Cancellation
# ---------------------------------------------------------------------------

async def _prepare_grid_scan_parameters(
    request: Request,
    project_id: int,
    scan_req: GeoGridScanRequest,
    current_user: User,
    db: AsyncSession
):
    """
    Validates project access, canonical keyword, coordinates, and SERP provider.
    """
    # 1. Resolve Keyword & Project (Strict: Never use business or location name as keyword)
    if scan_req.keyword_id:
        kw_res = await db.execute(select(Keyword).where(Keyword.id == scan_req.keyword_id))
        kw = kw_res.scalars().first()
        if not kw:
            raise HTTPException(status_code=404, detail="Keyword not found")
        project_id = kw.project_id
        kw_phrase = kw.keyword
    elif scan_req.keyword and scan_req.keyword.strip():
        kw_phrase = scan_req.keyword.strip()
        loc_match = None
        if scan_req.location_id is not None:
            loc_res = await db.execute(select(Location).where(Location.id == scan_req.location_id))
            loc_match = loc_res.scalars().first()
        if loc_match:
            project_id = loc_match.project_id
        kw_match_res = await db.execute(
            select(Keyword).where(Keyword.project_id == project_id, Keyword.keyword == kw_phrase)
        )
        kw = kw_match_res.scalars().first()
        if not kw:
            kw = Keyword(
                project_id=project_id,
                keyword=kw_phrase,
                created_at=datetime.now(timezone.utc)
            )
            db.add(kw)
            await db.flush()
            await db.refresh(kw)
    else:
        kw_res = await db.execute(
            select(Keyword).where(Keyword.project_id == project_id).order_by(Keyword.id.asc())
        )
        kw = kw_res.scalars().first()
        if not kw:
            raise HTTPException(
                status_code=400,
                detail="KEYWORD_REQUIRED: A valid tracked keyword_id or explicit keyword phrase is required for a Geo-Grid scan. Business and location names cannot be substituted for search keywords."
            )
        kw_phrase = kw.keyword

    project = await verify_project_access(project_id, current_user, db)
    if kw.project_id != project.id:
        raise HTTPException(
            status_code=400,
            detail=f"KEYWORD_PROJECT_MISMATCH: Keyword {kw.id} does not belong to project {project.id}."
        )

    # 2. Resolve authoritative location & business coordinates via GeoGridLocationResolver
    from app.services.serp.grid_location_resolver import GeoGridLocationResolver
    loc_res = await GeoGridLocationResolver.resolve_business_center(
        db=db,
        project_id=project.id,
        location_id=scan_req.location_id,
        explicit_lat=scan_req.center_lat,
        explicit_lng=scan_req.center_lng,
        explicit_center_name=scan_req.center_name
    )

    lat_center = loc_res.latitude
    lng_center = loc_res.longitude

    if (lat_center == 0.0 and lng_center == 0.0) or lat_center is None or lng_center is None:
        raise HTTPException(
            status_code=400,
            detail="LOCATION_COORDINATES_REQUIRED: Valid geographic coordinates (latitude and longitude) are required for a Geo-Grid scan. Please configure your business location address or coordinates."
        )

    if not (-90.0 <= lat_center <= 90.0):
        raise HTTPException(status_code=400, detail="INVALID_LATITUDE: Latitude must be between -90 and 90 degrees.")
    if not (-180.0 <= lng_center <= 180.0):
        raise HTTPException(status_code=400, detail="INVALID_LONGITUDE: Longitude must be between -180 and 180 degrees.")

    # Auto-persist manual coordinates into Location database entity if explicitly provided
    if scan_req.center_lat is not None or scan_req.center_lng is not None:
        if loc_res.location_entity:
            loc_res.location_entity.latitude = lat_center
            loc_res.location_entity.longitude = lng_center
            db.add(loc_res.location_entity)
            await db.commit()
            await db.refresh(loc_res.location_entity)
        elif not project.locations:
            new_loc = Location(
                project_id=project.id,
                name=scan_req.center_name or "Main Location",
                latitude=lat_center,
                longitude=lng_center
            )
            db.add(new_loc)
            await db.commit()
            await db.refresh(new_loc)
            loc_res.location_entity = new_loc

    radius = scan_req.radius_km if scan_req.radius_km is not None else DEFAULT_GEO_GRID_RADIUS_KM
    grid_size = scan_req.grid_size or 5
    center_name = loc_res.center_name

    # 3. Resolve SERP provider and validate configuration before scanning
    provider = await get_organization_serp_provider(db, project.organization_id)
    if not provider.is_configured:
        raise HTTPException(
            status_code=400,
            detail="SERP_PROVIDER_NOT_CONFIGURED: Connect your SerpApi account in Settings to enable Geo-Grid."
        )

    return (
        project, kw, kw_phrase, lat_center, lng_center, radius, grid_size, center_name,
        provider, loc_res.location_entity, loc_res.target_place_id, loc_res.target_url,
        loc_res.business_name, loc_res.phone, loc_res
    )


async def _execute_grid_scan_runner(
    scan_id: int,
    project_id: int,
    organization_id: int,
    keyword_id: int,
    kw_phrase: str,
    lat_center: float,
    lng_center: float,
    radius: float,
    grid_size: int,
    target_domain: Optional[str],
    business_name: Optional[str],
    phone: Optional[str],
    target_place_id: Optional[str] = None,
    target_url: Optional[str] = None
):
    """
    Asynchronous runner for GeoGrid scanning with cooperative cancellation and progressive DB point persistence.
    """
    async with AsyncSessionLocal() as session:
        scan_res = await session.execute(select(GeoGridScan).where(GeoGridScan.id == scan_id))
        scan = scan_res.scalars().first()
        if not scan:
            logger.error(f"[GEO_GRID_RUNNER] Scan #{scan_id} not found.")
            return

        provider = await get_organization_serp_provider(session, organization_id)
        if not provider.is_configured:
            scan.scan_status = "failed"
            scan.cancellation_reason = "SERP provider not configured."
            await session.commit()
            return

        async def _is_cancelled_check() -> bool:
            async with AsyncSessionLocal() as chk_sess:
                res = await chk_sess.execute(select(GeoGridScan.cancel_requested).where(GeoGridScan.id == scan_id))
                val = res.scalar_one_or_none()
                return bool(val)

        async def _on_point_completed(pt: Dict[str, Any]):
            async with AsyncSessionLocal() as pt_sess:
                # 1. Insert Point Result
                pt_record = GeoGridPointResult(
                    scan_id=scan_id,
                    project_id=project_id,
                    keyword_id=keyword_id,
                    point_number=pt.get("point_number", 0),
                    row=pt.get("row"),
                    col=pt.get("col"),
                    latitude=pt.get("lat", 0.0),
                    longitude=pt.get("lng", 0.0),
                    distance_km=pt.get("distance_km"),
                    direction=pt.get("direction"),
                    competitors=pt.get("competitors", []),
                    keyword=kw_phrase,
                    provider=pt.get("provider", getattr(provider, "provider_name", type(provider).__name__)),
                    status=pt.get("status", "NOT_FOUND"),
                    rank=pt.get("rank"),
                    matched_business=pt.get("matched_business"),
                    matched_place_id=pt.get("matched_place_id"),
                    matched_domain=pt.get("matched_domain"),
                    ranking_url=pt.get("ranking_url"),
                    searched_at=datetime.now(timezone.utc),
                    error=pt.get("error")
                )
                pt_sess.add(pt_record)

                # 2. Update parent scan counters
                s_res = await pt_sess.execute(select(GeoGridScan).where(GeoGridScan.id == scan_id))
                parent_scan = s_res.scalars().first()
                if parent_scan:
                    parent_scan.completed_points = (parent_scan.completed_points or 0) + 1
                    if pt.get("rank") is not None:
                        parent_scan.ranking_found_points = (parent_scan.ranking_found_points or 0) + 1
                        parent_scan.successful_points = (parent_scan.successful_points or 0) + 1
                    elif pt.get("status") == "NOT_FOUND":
                        parent_scan.not_found_points = (parent_scan.not_found_points or 0) + 1
                        parent_scan.successful_points = (parent_scan.successful_points or 0) + 1
                    elif pt.get("error_type") == "TIMEOUT" or pt.get("status") == "TIMEOUT":
                        parent_scan.timeout_points = (parent_scan.timeout_points or 0) + 1
                        parent_scan.failed_points = (parent_scan.failed_points or 0) + 1
                    elif pt.get("error_type") == "PROVIDER_ERROR" or pt.get("status") in ("PROVIDER_ERROR", "failed"):
                        parent_scan.provider_error_points = (parent_scan.provider_error_points or 0) + 1
                        parent_scan.failed_points = (parent_scan.failed_points or 0) + 1

                    current_pts = list(parent_scan.grid_points or [])
                    current_pts.append(pt)
                    parent_scan.grid_points = current_pts
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(parent_scan, "grid_points")

                await pt_sess.commit()

        scan_result = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword=kw_phrase,
            target_domain=target_domain,
            center_lat=lat_center,
            center_lng=lng_center,
            radius_km=radius,
            grid_size=grid_size,
            concurrency_limit=3,
            target_place_id=target_place_id,
            target_url=target_url,
            business_name=business_name,
            phone=phone,
            is_cancelled_fn=_is_cancelled_check,
            on_point_completed=_on_point_completed
        )

        # Reload scan in main session to update terminal attributes
        await session.refresh(scan)
        scan.average_rank = scan_result["average_rank"]
        scan.local_visibility_pct = scan_result["local_visibility_pct"]
        scan.grid_points = scan_result["grid_points"]
        scan.total_points = scan_result["total_points"]
        scan.completed_points = scan_result["completed_points"]
        scan.ranking_found_points = scan_result["ranking_found_points"]
        scan.not_found_points = scan_result["not_found_points"]
        scan.provider_error_points = scan_result["provider_error_points"]
        scan.timeout_points = scan_result["timeout_points"]
        scan.successful_points = scan_result["successful_points"]
        scan.failed_points = scan_result["failed_points"]

        if scan_result.get("is_cancelled") or scan.cancel_requested:
            scan.scan_status = "cancelled"
            scan.cancelled_at = datetime.now(timezone.utc)
            scan.cancellation_reason = "Cancelled by user"
        else:
            scan.scan_status = scan_result["scan_status"]

        await session.commit()

        # Ingest competitors from completed Geo-Grid scan
        if scan_result.get("grid_points") and scan.scan_status in ("completed", "completed_with_errors"):
            try:
                from app.services.local_seo.competitor_geogrid_service import CompetitorGeoGridService
                await CompetitorGeoGridService.ingest_scan_competitors(
                    db=session,
                    project_id=project_id,
                    scan_id=scan.id,
                    grid_points=scan_result.get("grid_points", []),
                    keyword=kw_phrase,
                    scan_time=scan.scanned_at
                )
            except Exception as ce:
                logger.warning(f"Error ingesting competitors from async scan #{scan.id}: {ce}")



@router.post("/{project_id}/grid/start-scan")
async def start_async_grid_scan(
    request: Request,
    project_id: int,
    scan_req: GeoGridScanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initializes a real Geo-Grid scan asynchronously.
    Returns the persistent scan_id immediately and starts cooperative background execution.
    """
    (
        project, kw, kw_phrase, lat_center, lng_center, radius, grid_size, center_name,
        provider, loc, target_place_id, target_url, resolved_business_name, resolved_phone, loc_res
    ) = (
        await _prepare_grid_scan_parameters(request, project_id, scan_req, current_user, db)
    )

    total_pts = grid_size * grid_size
    scan = GeoGridScan(
        project_id=project.id,
        keyword_id=kw.id,
        center_name=center_name,
        center_lat=lat_center,
        center_lng=lng_center,
        location_precision=loc_res.location_precision,
        center_source=loc_res.center_source,
        center_address=loc_res.center_address,
        radius_km=radius,
        grid_size=grid_size,
        scan_status="running",
        total_points=total_pts,
        completed_points=0,
        cancel_requested=False,
        started_at=datetime.now(timezone.utc),
        grid_points=[]
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    log_user_action(
        request, "START_ASYNC_GEO_GRID",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project.id,
        scan_id=scan.id,
        keyword=kw_phrase,
        grid_size=grid_size,
        radius_km=radius
    )

    background_tasks.add_task(
        _execute_grid_scan_runner,
        scan_id=scan.id,
        project_id=project.id,
        organization_id=project.organization_id,
        keyword_id=kw.id,
        kw_phrase=kw_phrase,
        lat_center=lat_center,
        lng_center=lng_center,
        radius=radius,
        grid_size=grid_size,
        target_domain=project.domain,
        business_name=resolved_business_name,
        phone=resolved_phone,
        target_place_id=target_place_id,
        target_url=target_url
    )

    return {
        "scan_id": scan.id,
        "id": scan.id,
        "status": "running",
        "scan_status": "running",
        "keyword": kw_phrase,
        "keyword_id": kw.id,
        "project_id": project.id,
        "grid_size": grid_size,
        "total_points": total_pts,
        "completed_points": 0,
        "progress_pct": 0.0,
        "started_at": scan.started_at.isoformat() if scan.started_at else None
    }


@router.get("/{project_id}/grid/scans/{scan_id}")
async def get_grid_scan_status(
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Polls real-time progress, status, and discrete point results of a Geo-Grid scan.
    """
    await verify_project_access(project_id, current_user, db)

    scan_res = await db.execute(
        select(GeoGridScan).where(GeoGridScan.id == scan_id, GeoGridScan.project_id == project_id)
    )
    scan = scan_res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Geo-Grid scan not found")

    kw_res = await db.execute(select(Keyword).where(Keyword.id == scan.keyword_id))
    kw = kw_res.scalars().first()

    pts_res = await db.execute(
        select(GeoGridPointResult).where(GeoGridPointResult.scan_id == scan.id).order_by(GeoGridPointResult.point_number)
    )
    db_points = pts_res.scalars().all()

    total_pts = scan.total_points or (scan.grid_size * scan.grid_size)
    completed_pts = scan.completed_points or len(db_points)
    progress_pct = round((completed_pts / total_pts) * 100, 1) if total_pts > 0 else 0.0

    return {
        "scan_id": scan.id,
        "id": scan.id,
        "project_id": scan.project_id,
        "keyword_id": scan.keyword_id,
        "keyword": kw.keyword if kw else "",
        "status": scan.scan_status,
        "scan_status": scan.scan_status,
        "cancel_requested": scan.cancel_requested,
        "cancellation_reason": scan.cancellation_reason,
        "total_points": total_pts,
        "completed_points": completed_pts,
        "progress_pct": progress_pct,
        "average_rank": scan.average_rank,
        "local_visibility_pct": scan.local_visibility_pct,
        "center_lat": scan.center_lat,
        "center_lng": scan.center_lng,
        "location_precision": getattr(scan, "location_precision", "EXACT") or "EXACT",
        "center_source": getattr(scan, "center_source", None),
        "center_address": getattr(scan, "center_address", None),
        "warning_message": "Exact business coordinates were not available. This Geo-Grid is using city-level location and may be less precise." if getattr(scan, "location_precision", "") == "CITY_LEVEL" else None,
        "radius_km": scan.radius_km,
        "grid_size": scan.grid_size,
        "points": [
            {
                "point_number": p.point_number,
                "row": p.row,
                "col": p.col,
                "lat": p.latitude,
                "lng": p.longitude,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "distance_km": getattr(p, "distance_km", None),
                "direction": getattr(p, "direction", None),
                "keyword": p.keyword,
                "provider": p.provider,
                "status": p.status,
                "rank": p.rank,
                "matched_business": p.matched_business,
                "matched_place_id": p.matched_place_id,
                "matched_domain": p.matched_domain,
                "ranking_url": p.ranking_url,
                "competitors": getattr(p, "competitors", []) or [],
                "error": p.error
            } for p in db_points
        ] if db_points else (scan.grid_points or []),
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "cancelled_at": scan.cancelled_at.isoformat() if scan.cancelled_at else None,
        "scanned_at": scan.scanned_at.isoformat() if scan.scanned_at else None
    }


@router.post("/{project_id}/grid/scans/{scan_id}/cancel")
async def cancel_grid_scan(
    request: Request,
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a cooperative cancellation request for an in-progress Geo-Grid scan.
    Stops pending point dispatches and preserves completed points.
    """
    project = await verify_project_access(project_id, current_user, db)

    scan_res = await db.execute(
        select(GeoGridScan).where(GeoGridScan.id == scan_id, GeoGridScan.project_id == project_id)
    )
    scan = scan_res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Geo-Grid scan not found")

    if scan.scan_status == "running":
        scan.cancel_requested = True
        scan.cancellation_reason = "Cancelled by user"
        scan.cancelled_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(scan)

        log_user_action(
            request, "CANCEL_GEO_GRID_SCAN",
            user_id=current_user.id,
            organization_id=project.organization_id,
            project_id=project.id,
            scan_id=scan.id
        )

    return {
        "scan_id": scan.id,
        "id": scan.id,
        "status": "cancelling" if scan.scan_status == "running" else scan.scan_status,
        "scan_status": "cancelling" if scan.scan_status == "running" else scan.scan_status,
        "cancel_requested": scan.cancel_requested,
        "message": "Cancellation request submitted. Halting remaining grid points."
    }


async def _execute_sync_grid_scan(
    request: Request,
    target_proj_id: int,
    scan_req: GeoGridScanRequest,
    current_user: User,
    db: AsyncSession
) -> GeoGridScan:
    (
        project, kw, kw_phrase, lat_center, lng_center, radius, grid_size, center_name,
        provider, loc, target_place_id, target_url, resolved_business_name, resolved_phone, loc_res
    ) = (
        await _prepare_grid_scan_parameters(request, target_proj_id, scan_req, current_user, db)
    )

    scan_result = await GeoGridScanner.scan_grid(
        provider=provider,
        keyword=kw_phrase,
        target_domain=project.domain,
        center_lat=lat_center,
        center_lng=lng_center,
        radius_km=radius,
        grid_size=grid_size,
        concurrency_limit=5,
        target_place_id=target_place_id,
        target_url=target_url,
        business_name=resolved_business_name,
        phone=resolved_phone
    )

    scan = GeoGridScan(
        project_id=project.id,
        keyword_id=kw.id,
        center_name=center_name,
        center_lat=lat_center,
        center_lng=lng_center,
        location_precision=loc_res.location_precision,
        center_source=loc_res.center_source,
        center_address=loc_res.center_address,
        radius_km=radius,
        grid_size=grid_size,
        average_rank=scan_result["average_rank"],
        local_visibility_pct=scan_result["local_visibility_pct"],
        grid_points=scan_result["grid_points"],
        scan_status=scan_result["scan_status"],
        total_points=scan_result["total_points"],
        completed_points=scan_result.get("completed_points", 0),
        ranking_found_points=scan_result.get("ranking_found_points", 0),
        not_found_points=scan_result.get("not_found_points", 0),
        provider_error_points=scan_result.get("provider_error_points", 0),
        timeout_points=scan_result.get("timeout_points", 0),
        successful_points=scan_result["successful_points"],
        failed_points=scan_result["failed_points"],
        started_at=datetime.now(timezone.utc)
    )
    db.add(scan)
    await db.flush()

    for pt in scan_result.get("grid_points", []):
        pt_record = GeoGridPointResult(
            scan_id=scan.id,
            project_id=project.id,
            keyword_id=kw.id,
            point_number=pt.get("point_number", 0),
            row=pt.get("row"),
            col=pt.get("col"),
            latitude=pt.get("lat", 0.0),
            longitude=pt.get("lng", 0.0),
            area_name=pt.get("area_name") or "Area name unavailable",
            distance_km=pt.get("distance_km"),
            direction=pt.get("direction"),
            competitors=pt.get("competitors", []),
            keyword=kw_phrase,
            provider=pt.get("provider", getattr(provider, "provider_name", type(provider).__name__)),
            status=pt.get("status", "NOT_FOUND"),
            rank=pt.get("rank"),
            matched_business=pt.get("matched_business"),
            matched_place_id=pt.get("matched_place_id"),
            matched_domain=pt.get("matched_domain"),
            ranking_url=pt.get("ranking_url"),
            searched_at=datetime.now(timezone.utc),
            error=pt.get("error")
        )
        db.add(pt_record)

    await db.commit()
    await db.refresh(scan)

    # Ingest competitors from completed Geo-Grid scan
    if scan_result.get("grid_points") and scan.scan_status in ("completed", "completed_with_errors"):
        try:
            from app.services.local_seo.competitor_geogrid_service import CompetitorGeoGridService
            await CompetitorGeoGridService.ingest_scan_competitors(
                db=db,
                project_id=project.id,
                scan_id=scan.id,
                grid_points=scan_result.get("grid_points", []),
                keyword=kw_phrase,
                scan_time=scan.scanned_at
            )
        except Exception as ce:
            logger.warning(f"Error ingesting competitors from sync scan #{scan.id}: {ce}")

    scan.scan_id = scan.id
    scan.keyword = kw_phrase
    scan.points = scan.grid_points
    scan.center = {"lat": lat_center, "lng": lng_center}
    scan.provider = {
        "name": getattr(provider, "provider_name", type(provider).__name__),
        "live": getattr(provider, "is_configured", False),
        "status": scan_result["scan_status"]
    }

    return scan


@router.post("/{project_id}/grid/rescan", response_model=GeoGridScanOut)
@router.post("/{project_id}/grid/scan", response_model=GeoGridScanOut)
async def rescan_project_grid(
    request: Request,
    project_id: int,
    scan_req: Optional[GeoGridScanRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Synchronous rescan endpoint scoped to a specific project.
    """
    if scan_req is None:
        scan_req = GeoGridScanRequest()
    return await _execute_sync_grid_scan(request, project_id, scan_req, current_user, db)


@router.post("/grid-scan", response_model=GeoGridScanOut)
async def trigger_grid_scan(
    request: Request,
    scan_req: Optional[GeoGridScanRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Global / standalone synchronous rescan endpoint.
    """
    if scan_req is None:
        scan_req = GeoGridScanRequest()

    target_proj_id = getattr(scan_req, "project_id", None)
    if not target_proj_id and scan_req.keyword_id:
        kw_res = await db.execute(select(Keyword).where(Keyword.id == scan_req.keyword_id))
        kw = kw_res.scalars().first()
        if kw:
            target_proj_id = kw.project_id

    if not target_proj_id:
        raise HTTPException(status_code=400, detail="PROJECT_ID_REQUIRED: Project context is required.")

    return await _execute_sync_grid_scan(request, target_proj_id, scan_req, current_user, db)

@router.get("/{project_id}/grid", response_model=Optional[GeoGridScanOut])
async def get_project_grid(
    request: Request,
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns latest GeoGrid scan for project with point results from database.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "OPEN_GEO_GRID",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id
    )
    query = (
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.project_id == project_id)
    )
    if keyword_id:
        query = query.where(GeoGridScan.keyword_id == keyword_id)
    result = await db.execute(query.order_by(GeoGridScan.id.desc()))
    scan = result.scalars().first()
    if not scan:
        return None

    # Attach response helper fields
    scan.scan_id = scan.id
    scan.keyword = scan.keyword_rel.keyword if scan.keyword_rel else None
    if scan.point_results:
        # Dynamic backfill of area_name for legacy points
        missing_pts = [pr for pr in scan.point_results if not getattr(pr, "area_name", None)]
        if missing_pts:
            coords = [(pr.latitude, pr.longitude) for pr in missing_pts]
            geo_map = await GeocodingService.reverse_geocode_points_batch(coords)
            for pr in missing_pts:
                pr.area_name = geo_map.get((round(pr.latitude, 3), round(pr.longitude, 3))) or "Area name unavailable"

        scan.points = [
            {
                "point_number": pr.point_number,
                "row": pr.row,
                "col": pr.col,
                "lat": pr.latitude,
                "lng": pr.longitude,
                "latitude": pr.latitude,
                "longitude": pr.longitude,
                "area_name": getattr(pr, "area_name", None) or "Area name unavailable",
                "distance_km": pr.distance_km,
                "direction": pr.direction,
                "rank": pr.rank,
                "status": pr.status,
                "keyword": pr.keyword,
                "provider": pr.provider,
                "matched_business": pr.matched_business,
                "matched_place_id": pr.matched_place_id,
                "matched_domain": pr.matched_domain,
                "ranking_url": pr.ranking_url,
                "error": pr.error,
                "competitors": pr.competitors or [],
                "searched_at": pr.searched_at.isoformat() if pr.searched_at else None
            }
            for pr in sorted(scan.point_results, key=lambda x: x.point_number)
        ]
    else:
        scan.points = scan.grid_points or []

    scan.center = {"lat": scan.center_lat, "lng": scan.center_lng}
    scan.warning_message = "Exact business coordinates were not available. This Geo-Grid is using city-level location and may be less precise." if getattr(scan, "location_precision", "") == "CITY_LEVEL" else None
    provider = await get_organization_serp_provider(db, project.organization_id)
    scan.provider = {
        "name": getattr(provider, "provider_name", type(provider).__name__),
        "live": getattr(provider, "is_configured", False),
        "status": scan.scan_status
    }
    return scan

@router.get("/grid-scan/{project_id}/latest", response_model=Optional[GeoGridScanOut])
async def get_latest_grid_scan(
    request: Request,
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_project_grid(request, project_id, keyword_id, current_user, db)


@router.get("/{project_id}/grid/history")
async def get_project_grid_history(
    project_id: int,
    keyword_id: Optional[int] = None,
    page: Optional[int] = Query(None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    limit: Optional[int] = Query(None, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns historical Geo-Grid scans for the project with server-side pagination (page_size = 20).
    """
    project = await verify_project_access(project_id, current_user, db)
    base_conds = [GeoGridScan.project_id == project_id]
    if keyword_id:
        base_conds.append(GeoGridScan.keyword_id == keyword_id)

    # If page is explicitly requested or for paginated API consumption
    if page is not None:
        effective_page_size = page_size
        count_stmt = select(func.count(GeoGridScan.id)).where(*base_conds)
        total_res = await db.execute(count_stmt)
        total_count = total_res.scalar() or 0

        offset = (page - 1) * effective_page_size
        query = (
            select(GeoGridScan)
            .options(selectinload(GeoGridScan.keyword_rel))
            .where(*base_conds)
            .order_by(GeoGridScan.id.desc())
            .offset(offset)
            .limit(effective_page_size)
        )
        res = await db.execute(query)
        scans = res.scalars().all()
        total_pages = math.ceil(total_count / effective_page_size) if total_count > 0 else 1

        formatted = [
            {
                "id": s.id,
                "keyword_id": s.keyword_id,
                "keyword": s.keyword_rel.keyword if s.keyword_rel else None,
                "center_name": s.center_name,
                "center_lat": s.center_lat,
                "center_lng": s.center_lng,
                "radius_km": s.radius_km,
                "grid_size": s.grid_size,
                "average_rank": s.average_rank,
                "local_visibility_pct": s.local_visibility_pct,
                "total_points": s.total_points,
                "completed_points": s.completed_points,
                "ranking_found_points": s.ranking_found_points,
                "not_found_points": s.not_found_points,
                "provider_error_points": s.provider_error_points,
                "scan_status": s.scan_status,
                "scanned_at": s.scanned_at
            }
            for s in scans
        ]
        return {
            "items": formatted,
            "records": formatted,
            "total": total_count,
            "page": page,
            "page_size": effective_page_size,
            "total_pages": total_pages
        }

    # Backward-compatible list view if no page param specified
    effective_limit = limit or page_size or 20
    query = (
        select(GeoGridScan)
        .options(selectinload(GeoGridScan.keyword_rel))
        .where(*base_conds)
        .order_by(GeoGridScan.id.desc())
        .limit(effective_limit)
    )
    res = await db.execute(query)
    scans = res.scalars().all()

    return [
        {
            "id": s.id,
            "keyword_id": s.keyword_id,
            "keyword": s.keyword_rel.keyword if s.keyword_rel else None,
            "center_name": s.center_name,
            "center_lat": s.center_lat,
            "center_lng": s.center_lng,
            "radius_km": s.radius_km,
            "grid_size": s.grid_size,
            "average_rank": s.average_rank,
            "local_visibility_pct": s.local_visibility_pct,
            "total_points": s.total_points,
            "completed_points": s.completed_points,
            "ranking_found_points": s.ranking_found_points,
            "not_found_points": s.not_found_points,
            "provider_error_points": s.provider_error_points,
            "scan_status": s.scan_status,
            "scanned_at": s.scanned_at
        }
        for s in scans
    ]


@router.get("/{project_id}/grid/scans/{scan_id}/pdf")
async def download_grid_scan_pdf(
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads a high-fidelity ReportLab PDF for a single complete or historical scan.
    Uses stored database records without triggering any new SERP provider queries.
    """
    project = await verify_project_access(project_id, current_user, db)
    stmt = (
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.id == scan_id, GeoGridScan.project_id == project_id)
    )
    res = await db.execute(stmt)
    scan = res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Geo-Grid scan not found.")

    points = scan.point_results or []
    # Ensure area_name is populated
    missing_pts = [p for p in points if not getattr(p, "area_name", None)]
    if missing_pts:
        coords = [(getattr(p, "latitude", getattr(p, "lat", 0.0)), getattr(p, "longitude", getattr(p, "lng", 0.0))) for p in missing_pts]
        geo_map = await GeocodingService.reverse_geocode_points_batch(coords)
        for p in missing_pts:
            p_lat = getattr(p, "latitude", getattr(p, "lat", 0.0))
            p_lng = getattr(p, "longitude", getattr(p, "lng", 0.0))
            p.area_name = geo_map.get((round(p_lat, 3), round(p_lng, 3))) or "Area name unavailable"

    pdf_bytes = GeoGridPDFService.generate_single_scan_pdf(project, scan, points)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="geogrid-scan-{scan_id}.pdf"'
        }
    )


@router.get("/{project_id}/grid/pdf/latest")
async def download_latest_grid_scan_pdf(
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads the PDF for the latest scan of the project.
    """
    project = await verify_project_access(project_id, current_user, db)
    stmt = (
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.project_id == project_id)
    )
    if keyword_id:
        stmt = stmt.where(GeoGridScan.keyword_id == keyword_id)

    res = await db.execute(stmt.order_by(GeoGridScan.id.desc()).limit(1))
    scan = res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="No Geo-Grid scans found for this project.")

    points = scan.point_results or []
    missing_pts = [p for p in points if not getattr(p, "area_name", None)]
    if missing_pts:
        coords = [(getattr(p, "latitude", getattr(p, "lat", 0.0)), getattr(p, "longitude", getattr(p, "lng", 0.0))) for p in missing_pts]
        geo_map = await GeocodingService.reverse_geocode_points_batch(coords)
        for p in missing_pts:
            p_lat = getattr(p, "latitude", getattr(p, "lat", 0.0))
            p_lng = getattr(p, "longitude", getattr(p, "lng", 0.0))
            p.area_name = geo_map.get((round(p_lat, 3), round(p_lng, 3))) or "Area name unavailable"

    pdf_bytes = GeoGridPDFService.generate_single_scan_pdf(project, scan, points)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="geogrid-latest-scan-{scan.id}.pdf"'
        }
    )


@router.get("/{project_id}/grid/pdf/recent-scans")
async def download_recent_scans_pdf(
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads a chronological multi-scan report comparing the Current + Previous 2 scans (max 3 scans).
    """
    project = await verify_project_access(project_id, current_user, db)
    stmt = (
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.project_id == project_id, GeoGridScan.scan_status == "completed")
    )
    if keyword_id:
        stmt = stmt.where(GeoGridScan.keyword_id == keyword_id)

    # Get latest 3 completed scans
    res = await db.execute(stmt.order_by(GeoGridScan.id.desc()).limit(3))
    scans = res.scalars().all()
    if not scans:
        # Fallback to any scans if none explicitly completed
        fallback_stmt = select(GeoGridScan).options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        ).where(GeoGridScan.project_id == project_id).order_by(GeoGridScan.id.desc()).limit(3)
        fb_res = await db.execute(fallback_stmt)
        scans = fb_res.scalars().all()

    if not scans:
        raise HTTPException(status_code=404, detail="No Geo-Grid scans available for comparison report.")

    for s in scans:
        pts = s.point_results or []
        missing_pts = [p for p in pts if not getattr(p, "area_name", None)]
        if missing_pts:
            coords = [(getattr(p, "latitude", getattr(p, "lat", 0.0)), getattr(p, "longitude", getattr(p, "lng", 0.0))) for p in missing_pts]
            geo_map = await GeocodingService.reverse_geocode_points_batch(coords)
            for p in missing_pts:
                p_lat = getattr(p, "latitude", getattr(p, "lat", 0.0))
                p_lng = getattr(p, "longitude", getattr(p, "lng", 0.0))
                p.area_name = geo_map.get((round(p_lat, 3), round(p_lng, 3))) or "Area name unavailable"

    scans_with_points = [(s, s.point_results or []) for s in scans]
    pdf_bytes = GeoGridPDFService.generate_multi_scan_comparison_pdf(project, scans_with_points)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="geogrid-recent-scans-trend.pdf"'
        }
    )


@router.get("/{project_id}/grid/scans/{scan_id}/points/{point_number}/pdf")
async def download_selected_point_pdf(
    project_id: int,
    scan_id: int,
    point_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads a dedicated deep-dive PDF report for ONLY the selected grid point.
    """
    project = await verify_project_access(project_id, current_user, db)
    stmt = (
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.id == scan_id, GeoGridScan.project_id == project_id)
    )
    res = await db.execute(stmt)
    scan = res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Geo-Grid scan not found.")

    target_pt = next((p for p in (scan.point_results or []) if p.point_number == point_number), None)
    if not target_pt:
        # Check database directly in case point_results was not loaded
        pt_res = await db.execute(
            select(GeoGridPointResult).where(
                GeoGridPointResult.scan_id == scan_id,
                GeoGridPointResult.project_id == project_id,
                GeoGridPointResult.point_number == point_number
            )
        )
        target_pt = pt_res.scalars().first()

    if not target_pt:
        raise HTTPException(status_code=404, detail=f"Grid point #{point_number} not found for scan #{scan_id}.")

    # Generate full point analysis payload
    analysis_data = await get_grid_point_analysis(
        project_id=project_id,
        scan_id=scan_id,
        point_number=point_number,
        current_user=current_user,
        db=db
    )

    if not getattr(target_pt, "area_name", None):
        target_pt.area_name = analysis_data.get("location", {}).get("area_name") or "Area name unavailable"

    pdf_bytes = GeoGridPDFService.generate_selected_point_pdf(project, scan, target_pt, analysis_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="geogrid-scan-{scan_id}-point-{point_number}.pdf"'
        }
    )


@router.get("/{project_id}/grid/scans/{scan_id}", response_model=GeoGridScanOut)
async def get_grid_scan_by_id(
    project_id: int,
    scan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves a specific historical Geo-Grid scan with all discrete point results.
    """
    project = await verify_project_access(project_id, current_user, db)
    stmt = (
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.id == scan_id, GeoGridScan.project_id == project_id)
    )
    res = await db.execute(stmt)
    scan = res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Geo-Grid scan not found.")

    scan.scan_id = scan.id
    scan.keyword = scan.keyword_rel.keyword if scan.keyword_rel else None
    if scan.point_results:
        missing_pts = [pr for pr in scan.point_results if not getattr(pr, "area_name", None)]
        if missing_pts:
            coords = [(pr.latitude, pr.longitude) for pr in missing_pts]
            geo_map = await GeocodingService.reverse_geocode_points_batch(coords)
            for pr in missing_pts:
                pr.area_name = geo_map.get((round(pr.latitude, 3), round(pr.longitude, 3))) or "Area name unavailable"

        scan.points = [
            {
                "point_number": pr.point_number,
                "row": pr.row,
                "col": pr.col,
                "lat": pr.latitude,
                "lng": pr.longitude,
                "latitude": pr.latitude,
                "longitude": pr.longitude,
                "area_name": getattr(pr, "area_name", None) or "Area name unavailable",
                "distance_km": pr.distance_km,
                "direction": pr.direction,
                "rank": pr.rank,
                "status": pr.status,
                "keyword": pr.keyword,
                "provider": pr.provider,
                "matched_business": pr.matched_business,
                "matched_place_id": pr.matched_place_id,
                "matched_domain": pr.matched_domain,
                "ranking_url": pr.ranking_url,
                "error": pr.error,
                "competitors": pr.competitors or [],
                "searched_at": pr.searched_at.isoformat() if pr.searched_at else None
            }
            for pr in sorted(scan.point_results, key=lambda x: x.point_number)
        ]
    else:
        scan.points = scan.grid_points or []

    scan.center = {"lat": scan.center_lat, "lng": scan.center_lng}
    provider = await get_organization_serp_provider(db, project.organization_id)
    scan.provider = {
        "name": getattr(provider, "provider_name", type(provider).__name__),
        "live": getattr(provider, "is_configured", False),
        "status": scan.scan_status
    }
    return scan


@router.get("/{project_id}/grid/scans/{scan_id}/points/{point_number}")
async def get_grid_point_analysis(
    project_id: int,
    scan_id: int,
    point_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns deep-dive 4-part (WHAT, WHERE, HOW, WHY) diagnostic and competitor hierarchy for a discrete grid point.
    """
    project = await verify_project_access(project_id, current_user, db)
    
    # 1. Fetch scan
    scan_res = await db.execute(
        select(GeoGridScan)
        .options(
            selectinload(GeoGridScan.keyword_rel),
            selectinload(GeoGridScan.point_results)
        )
        .where(GeoGridScan.id == scan_id, GeoGridScan.project_id == project_id)
    )
    scan = scan_res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Geo-Grid scan not found.")

    # 2. Find point record
    pt_record = None
    if scan.point_results:
        pt_record = next((p for p in scan.point_results if p.point_number == point_number), None)
    
    pt_data = None
    if pt_record:
        pt_data = {
            "point_number": pt_record.point_number,
            "row": pt_record.row,
            "col": pt_record.col,
            "latitude": pt_record.latitude,
            "longitude": pt_record.longitude,
            "area_name": pt_record.area_name,
            "distance_km": pt_record.distance_km,
            "direction": pt_record.direction,
            "keyword": pt_record.keyword,
            "provider": pt_record.provider,
            "status": pt_record.status,
            "rank": pt_record.rank,
            "matched_business": pt_record.matched_business,
            "matched_place_id": pt_record.matched_place_id,
            "matched_domain": pt_record.matched_domain,
            "ranking_url": pt_record.ranking_url,
            "competitors": pt_record.competitors or [],
            "error": pt_record.error,
            "searched_at": pt_record.searched_at.isoformat() if pt_record.searched_at else None
        }
    elif scan.grid_points:
        matched_dict = next((p for p in scan.grid_points if p.get("point_number") == point_number), None)
        if matched_dict:
            pt_data = {
                "point_number": matched_dict.get("point_number", point_number),
                "row": matched_dict.get("row"),
                "col": matched_dict.get("col"),
                "latitude": matched_dict.get("lat") or matched_dict.get("latitude"),
                "longitude": matched_dict.get("lng") or matched_dict.get("longitude"),
                "area_name": matched_dict.get("area_name"),
                "distance_km": matched_dict.get("distance_km"),
                "direction": matched_dict.get("direction"),
                "keyword": matched_dict.get("keyword") or (scan.keyword_rel.keyword if scan.keyword_rel else None),
                "provider": matched_dict.get("provider", "serpapi"),
                "status": matched_dict.get("status", "NOT_FOUND"),
                "rank": matched_dict.get("rank"),
                "matched_business": matched_dict.get("matched_business"),
                "matched_place_id": matched_dict.get("matched_place_id"),
                "matched_domain": matched_dict.get("matched_domain"),
                "ranking_url": matched_dict.get("ranking_url"),
                "competitors": matched_dict.get("competitors", []),
                "error": matched_dict.get("error"),
                "searched_at": scan.scanned_at.isoformat() if scan.scanned_at else None
            }

    if not pt_data:
        raise HTTPException(status_code=404, detail=f"Grid point #{point_number} not found in scan #{scan_id}.")

    # 3. Calculate distance, direction, and area_name if missing
    if pt_data.get("distance_km") is None and pt_data.get("latitude") is not None and pt_data.get("longitude") is not None:
        dist, direction = GeoGridScanner.calculate_distance_and_direction(
            scan.center_lat, scan.center_lng, pt_data["latitude"], pt_data["longitude"]
        )
        pt_data["distance_km"] = dist
        pt_data["direction"] = direction

    # Resolve real geographic area / locality name
    area_name = pt_data.get("area_name")
    if not area_name or area_name == "Area name unavailable":
        if pt_data.get("latitude") is not None and pt_data.get("longitude") is not None:
            area_name = await GeocodingService.reverse_geocode(pt_data["latitude"], pt_data["longitude"]) or "Area name unavailable"
            pt_data["area_name"] = area_name
        else:
            area_name = "Area name unavailable"

    # Query project's verified Google Places / GBP listing to avoid unverified dummy values
    pub_listing_res = await db.execute(
        select(PublicBusinessListing).where(PublicBusinessListing.project_id == project.id)
    )
    pub_listing = pub_listing_res.scalars().first()

    gbp_profile_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project.id)
    )
    gbp_profile = gbp_profile_res.scalars().first()

    # 4. Competitor segmentation: Above, Target, Below
    competitors = pt_data.get("competitors") or []
    target_rank = pt_data.get("rank")
    
    competitors_above = []
    target_item = None
    competitors_below = []

    for c in competitors:
        pos = c.get("position", 999)
        if c.get("is_target") or (target_rank and pos == target_rank):
            target_item = c
        elif target_rank and pos < target_rank:
            competitors_above.append(c)
        elif target_rank and pos > target_rank:
            competitors_below.append(c)
        else:
            competitors_above.append(c)

    # Ensure target business displays verified Google rating and review count from PublicBusinessListing / GBP
    if target_item:
        if target_item.get("rating") is None and pub_listing and pub_listing.rating is not None:
            target_item["rating"] = pub_listing.rating
        if target_item.get("reviews_count") is None and pub_listing and pub_listing.review_count is not None:
            target_item["reviews_count"] = pub_listing.review_count
    elif target_rank:
        target_item = {
            "position": target_rank,
            "title": project.name,
            "link": project.domain or "",
            "domain": project.domain or "",
            "rating": pub_listing.rating if pub_listing else None,
            "reviews_count": pub_listing.review_count if pub_listing else None,
            "is_target": True
        }

    if target_rank:
        if target_rank <= 10:
            result_depth = 10
        elif target_rank <= 25:
            result_depth = 25
        elif target_rank <= 50:
            result_depth = 50
        else:
            result_depth = 100
    else:
        result_depth = len(competitors) or 20

    # 5. Build What, Where, How, Why diagnostic
    kw_str = pt_data.get("keyword") or "target keyword"
    biz_name = project.name
    dist_val = pt_data.get("distance_km", 0.0)
    dir_val = pt_data.get("direction", "Center")
    
    # WHAT
    if target_rank:
        what_text = f"Your business '{biz_name}' ranked #{target_rank} for '{kw_str}' at this scan location."
    elif pt_data.get("status") in ["TIMEOUT", "PROVIDER_ERROR"] or pt_data.get("error"):
        what_text = f"The SERP provider encountered an issue ({pt_data.get('error') or 'Search query error'}) at this coordinate."
    else:
        what_text = f"Your business '{biz_name}' was not found within the top {len(competitors) or 20} local map pack results at this scan location."

    # WHERE (Include resolved Area name)
    where_text = f"Area: {area_name} · Located {dist_val} km {dir_val} of {scan.center_name or 'Business Center'} at GPS coordinates ({pt_data.get('latitude')}, {pt_data.get('longitude')})."

    # HOW (Include authoritative Google rating and reviews)
    how_items = []
    how_items.append({"field": "Business Name", "value": (target_item.get("title") if target_item else None) or biz_name, "provider_observed": True})
    
    # Google Rating & Reviews
    if pub_listing and pub_listing.rating is not None:
        how_items.append({"field": "Google Rating", "value": f"{pub_listing.rating} / 5.0", "provider_observed": True})
    elif target_item and target_item.get("rating") is not None:
        how_items.append({"field": "Google Rating", "value": f"{target_item['rating']} / 5.0", "provider_observed": True})
    else:
        how_items.append({"field": "Google Rating", "value": "Google rating unavailable", "provider_observed": False})

    if pub_listing and pub_listing.review_count is not None:
        how_items.append({"field": "Google Reviews", "value": f"{pub_listing.review_count} reviews", "provider_observed": True})
    elif target_item and target_item.get("reviews_count") is not None:
        how_items.append({"field": "Google Reviews", "value": f"{target_item['reviews_count']} reviews", "provider_observed": True})
    else:
        how_items.append({"field": "Google Reviews", "value": "Google reviews unavailable", "provider_observed": False})

    if target_item:
        if target_item.get("category"):
            how_items.append({"field": "Category", "value": target_item["category"], "provider_observed": True})
        if target_item.get("address"):
            how_items.append({"field": "Address", "value": target_item["address"], "provider_observed": True})
        if target_item.get("link"):
            how_items.append({"field": "Website", "value": target_item["link"], "provider_observed": True})
        if target_item.get("place_id"):
            how_items.append({"field": "Place ID", "value": target_item["place_id"], "provider_observed": True})
    elif pt_data.get("matched_business"):
        how_items.append({"field": "Business Matched", "value": pt_data["matched_business"], "provider_observed": True})
        if pt_data.get("ranking_url"):
            how_items.append({"field": "Ranking URL", "value": pt_data["ranking_url"], "provider_observed": True})
    else:
        how_items.append({
            "field": "Search Query",
            "value": f"Searched '{kw_str}' @ {pt_data.get('latitude')},{pt_data.get('longitude')} (Google Maps Engine)",
            "provider_observed": True
        })

    # WHY
    why_points = []
    if competitors_above:
        top1 = competitors_above[0]
        t1_title = top1.get("title", "Top Competitor")
        t1_rev = top1.get("reviews_count")
        t1_rat = top1.get("rating")
        t1_cat = top1.get("category")
        
        our_rev = target_item.get("reviews_count") if target_item else (pub_listing.review_count if pub_listing else None)
        our_rat = target_item.get("rating") if target_item else (pub_listing.rating if pub_listing else None)

        if t1_rev is not None and our_rev is not None:
            if t1_rev > our_rev:
                why_points.append(
                    f"Observed: Competitor '{t1_title}' ranks #{top1.get('position', 1)} with {t1_rev} reviews compared with {our_rev} for your business. Potential contributing signal: Review volume correlation."
                )
            elif t1_rev < our_rev:
                why_points.append(
                    f"Observed: Competitor '{t1_title}' ranks #{top1.get('position', 1)} despite having fewer reviews ({t1_rev} vs {our_rev}). Potential contributing signal: Proximity to search point and localized citation signals."
                )
        elif t1_rev is not None:
            why_points.append(
                f"Observed: '{t1_title}' holds position #{top1.get('position', 1)} with {t1_rev} reviews ({t1_rat or 'N/A'}★)."
            )

        if t1_cat:
            why_points.append(f"Detected: Primary category for #{top1.get('position', 1)} is '{t1_cat}'.")

    if not target_rank:
        why_points.append(
            f"Business not found within scanned result depth ({len(competitors) or 20} places). Potential contributing signal: Physical distance from search point ({dist_val} km) or keyword categorization mismatch."
        )
    elif target_rank <= 3:
        why_points.append(
            "Observed: Strong local authority and proximity within the high-visibility Google Local 3-Pack."
        )
    elif target_rank > 3:
        why_points.append(
            f"Observed: Your business appears at position #{target_rank}, outside the initial 3-pack view."
        )

    return {
        "point_number": pt_data["point_number"],
        "scan_id": scan.id,
        "project_id": project.id,
        "location": {
            "point_number": pt_data["point_number"],
            "row": pt_data.get("row"),
            "col": pt_data.get("col"),
            "latitude": pt_data.get("latitude"),
            "longitude": pt_data.get("longitude"),
            "area_name": area_name,
            "distance_km": dist_val,
            "direction": dir_val,
            "center_name": scan.center_name or "Business Location",
            "keyword": kw_str,
            "searched_at": pt_data.get("searched_at")
        },
        "ranking": {
            "business_name": biz_name,
            "rank": target_rank,
            "status": pt_data.get("status"),
            "result_depth": result_depth,
            "ranking_url": pt_data.get("ranking_url"),
            "place_id": pt_data.get("matched_place_id"),
            "matched_place_id": pt_data.get("matched_place_id"),
            "matched_domain": pt_data.get("matched_domain"),
            "provider": pt_data.get("provider"),
            "error": pt_data.get("error")
        },
        "competitors_hierarchy": {
            "competitors_above": competitors_above,
            "target_business": target_item or ({
                "position": target_rank,
                "title": biz_name,
                "link": project.domain or "",
                "domain": project.domain or "",
                "rating": pub_listing.rating if pub_listing else None,
                "reviews_count": pub_listing.review_count if pub_listing else None,
                "is_target": True
            } if target_rank else None),
            "competitors_below": competitors_below,
            "total_competitors_evaluated": len(competitors),
            "result_depth": result_depth,
            "not_found_in_depth": target_rank is None
        },
        "diagnostics": {
            "what": what_text,
            "where": where_text,
            "how": how_items,
            "why": why_points
        }
    }


@router.get("/{project_id}/grid/compare")
async def compare_project_grid_scans(
    project_id: int,
    scan_a_id: int = Query(..., description="Earlier baseline scan ID"),
    scan_b_id: int = Query(..., description="Later comparison scan ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Compares two historical scans (Scan A vs Scan B) point-by-point.
    Returns delta average rank, visibility percentage change, and individual pin movement.
    """
    project = await verify_project_access(project_id, current_user, db)

    stmt_a = (
        select(GeoGridScan)
        .options(selectinload(GeoGridScan.point_results))
        .where(GeoGridScan.id == scan_a_id, GeoGridScan.project_id == project_id)
    )
    stmt_b = (
        select(GeoGridScan)
        .options(selectinload(GeoGridScan.point_results))
        .where(GeoGridScan.id == scan_b_id, GeoGridScan.project_id == project_id)
    )

    res_a = await db.execute(stmt_a)
    scan_a = res_a.scalars().first()
    res_b = await db.execute(stmt_b)
    scan_b = res_b.scalars().first()

    if not scan_a or not scan_b:
        raise HTTPException(
            status_code=404,
            detail="One or both scans not found for comparison in this project."
        )

    return GeoGridScanner.compare_scans(scan_a, scan_b)


