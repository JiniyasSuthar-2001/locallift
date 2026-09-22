import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.core.audit_logger import log_user_action
from app.models.user import User
from app.models.project import Project, Location
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan
from app.schemas.ranking import (
    KeywordCreate,
    KeywordOut,
    GeoGridScanOut,
    GeoGridScanRequest,
    KeywordCheckResponse,
    KeywordCheckAllResponse
)
from app.services.serp import get_serp_provider, get_organization_serp_provider, DomainMatcher, GeoGridScanner

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

    # Initial keyword record with no fake rank
    kw = Keyword(
        project_id=kw_in.project_id,
        keyword=kw_in.keyword.strip(),
        search_intent=kw_in.search_intent or "Commercial",
        search_volume=kw_in.search_volume,
        difficulty=kw_in.difficulty,
        target_location=kw_in.target_location or "Metro Area",
        target_rank=kw_in.target_rank,
        current_rank=None,
        previous_rank=None,
        ranking_url=None,
        serp_type="Local Pack",
        opportunity_score="HIGH" if kw_in.search_volume and kw_in.search_volume > 300 else None,
        business_relevance=kw_in.business_relevance or "High",
        last_checked_at=datetime.now(timezone.utc)
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

    # If SERP provider is configured for organization, attempt an immediate initial live lookup
    provider = await get_organization_serp_provider(db, project.organization_id)
    if provider.is_configured:
        try:
            serp_resp = await provider.search_keyword(
                keyword=kw.keyword,
                location=kw.target_location,
                country="au" if "com.au" in project.domain else "us"
            )
            if serp_resp.success:
                found_rank, found_url, serp_type = DomainMatcher.find_rank_in_serp(
                    serp_resp,
                    target_domain=project.domain
                )
                kw.current_rank = found_rank
                kw.ranking_url = found_url
                kw.serp_type = serp_type
                kw.last_checked_at = datetime.now(timezone.utc)

                if found_rank is not None:
                    db.add(KeywordRanking(
                        keyword_id=kw.id,
                        location_name=kw.target_location or "Default",
                        rank_position=found_rank,
                        serp_type=serp_type,
                        checked_at=datetime.now(timezone.utc)
                    ))
                await db.commit()
                await db.refresh(kw)
        except Exception as e:
            logger.warning(f"Initial SERP lookup on add_keyword failed: {e}")

    return kw

@router.post("/{keyword_id}/check", response_model=KeywordCheckResponse)
async def check_keyword_rank(
    request: Request,
    keyword_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a real SERP rank check for a single keyword against the project domain.
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

    provider = await get_organization_serp_provider(db, project.organization_id)
    country = "au" if "com.au" in project.domain else "us"

    serp_resp = await provider.search_keyword(
        keyword=kw.keyword,
        location=kw.target_location,
        country=country
    )

    if not serp_resp.success:
        return KeywordCheckResponse(
            keyword_id=kw.id,
            keyword=kw.keyword,
            target_domain=project.domain,
            current_rank=kw.current_rank,
            previous_rank=kw.previous_rank,
            rank_movement=None,
            ranking_url=kw.ranking_url,
            serp_type=kw.serp_type,
            provider=serp_resp.provider,
            status="provider_error" if serp_resp.error_code != "SERP_PROVIDER_NOT_CONFIGURED" else "not_configured",
            error_message=serp_resp.error_message,
            last_checked_at=kw.last_checked_at or datetime.now(timezone.utc)
        )

    # Find real rank in SERP results
    found_rank, found_url, serp_type = DomainMatcher.find_rank_in_serp(
        serp_resp,
        target_domain=project.domain
    )

    # Shift history: previous_rank becomes old current_rank
    old_current = kw.current_rank
    kw.previous_rank = old_current
    kw.current_rank = found_rank
    kw.ranking_url = found_url
    kw.serp_type = serp_type
    kw.last_checked_at = datetime.now(timezone.utc)

    # Record historical point
    if found_rank is not None:
        db.add(KeywordRanking(
            keyword_id=kw.id,
            location_name=kw.target_location or "Default",
            rank_position=found_rank,
            serp_type=serp_type,
            checked_at=datetime.now(timezone.utc)
        ))

    await db.commit()
    await db.refresh(kw)

    # Calculate movement
    movement = None
    if old_current is not None and found_rank is not None:
        movement = old_current - found_rank  # positive means improved rank

    return KeywordCheckResponse(
        keyword_id=kw.id,
        keyword=kw.keyword,
        target_domain=project.domain,
        current_rank=kw.current_rank,
        previous_rank=kw.previous_rank,
        rank_movement=movement,
        ranking_url=kw.ranking_url,
        serp_type=kw.serp_type,
        provider=serp_resp.provider,
        status="checked" if found_rank is not None else "not_found",
        error_message=None,
        last_checked_at=kw.last_checked_at
    )

@router.post("/{project_id}/check-all", response_model=KeywordCheckAllResponse)
async def check_all_project_keywords(
    request: Request,
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes real live SERP checks for all tracked keywords in a project.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "RUN_ALL_KEYWORDS_CHECK",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id
    )

    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
    keywords = kw_res.scalars().all()

    provider = await get_organization_serp_provider(db, project.organization_id)
    country = "au" if "com.au" in project.domain else "us"

    results = []
    checked_count = 0
    not_found_count = 0
    error_count = 0

    import asyncio
    sem = asyncio.Semaphore(5)

    async def _fetch_kw(kw_obj: Keyword):
        async with sem:
            resp = await provider.search_keyword(
                keyword=kw_obj.keyword,
                location=kw_obj.target_location,
                country=country
            )
            return kw_obj, resp

    pairs = await asyncio.gather(*(_fetch_kw(kw) for kw in keywords))

    for kw, serp_resp in pairs:
        if not serp_resp.success:
            error_count += 1
            results.append(KeywordCheckResponse(
                keyword_id=kw.id,
                keyword=kw.keyword,
                target_domain=project.domain,
                current_rank=kw.current_rank,
                previous_rank=kw.previous_rank,
                rank_movement=None,
                ranking_url=kw.ranking_url,
                serp_type=kw.serp_type,
                provider=serp_resp.provider,
                status="not_configured" if serp_resp.error_code == "SERP_PROVIDER_NOT_CONFIGURED" else "provider_error",
                error_message=serp_resp.error_message,
                last_checked_at=kw.last_checked_at or datetime.now(timezone.utc)
            ))
            continue

        found_rank, found_url, serp_type = DomainMatcher.find_rank_in_serp(
            serp_resp,
            target_domain=project.domain
        )

        old_current = kw.current_rank
        kw.previous_rank = old_current
        kw.current_rank = found_rank
        kw.ranking_url = found_url
        kw.serp_type = serp_type
        kw.last_checked_at = datetime.now(timezone.utc)

        if found_rank is not None:
            checked_count += 1
            db.add(KeywordRanking(
                keyword_id=kw.id,
                location_name=kw.target_location or "Default",
                rank_position=found_rank,
                serp_type=serp_type,
                checked_at=datetime.now(timezone.utc)
            ))
        else:
            not_found_count += 1

        movement = None
        if old_current is not None and found_rank is not None:
            movement = old_current - found_rank

        results.append(KeywordCheckResponse(
            keyword_id=kw.id,
            keyword=kw.keyword,
            target_domain=project.domain,
            current_rank=kw.current_rank,
            previous_rank=kw.previous_rank,
            rank_movement=movement,
            ranking_url=kw.ranking_url,
            serp_type=kw.serp_type,
            provider=serp_resp.provider,
            status="checked" if found_rank is not None else "not_found",
            error_message=None,
            last_checked_at=kw.last_checked_at
        ))

    await db.commit()

    return KeywordCheckAllResponse(
        project_id=project_id,
        checked_count=checked_count,
        not_found_count=not_found_count,
        error_count=error_count,
        provider="serpapi" if provider.is_configured else "not_configured",
        results=results,
        checked_at=datetime.now(timezone.utc)
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

@router.post("/grid-scan", response_model=GeoGridScanOut)
async def trigger_grid_scan(
    request: Request,
    scan_req: GeoGridScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Runs a real 5x5 Geo-Grid scan using live location-aware SERP queries.
    """
    # 1. Resolve Keyword & Project
    if scan_req.keyword_id:
        kw_res = await db.execute(select(Keyword).where(Keyword.id == scan_req.keyword_id))
        kw = kw_res.scalars().first()
        if not kw:
            raise HTTPException(status_code=404, detail="Keyword not found")
        project_id = kw.project_id
        kw_phrase = kw.keyword
    else:
        raise HTTPException(status_code=400, detail="keyword_id is required for grid scan")

    project = await verify_project_access(project_id, current_user, db)
    proj_res = await db.execute(
        select(Project).options(selectinload(Project.locations)).where(Project.id == project.id)
    )
    project = proj_res.scalars().first()

    # 2. Determine center coordinates from location_id, manual coordinates, or project locations
    loc = None
    if scan_req.location_id is not None:
        loc_res = await db.execute(
            select(Location).where(Location.id == scan_req.location_id, Location.project_id == project.id)
        )
        loc = loc_res.scalars().first()
        if not loc:
            raise HTTPException(
                status_code=400,
                detail=f"INVALID_LOCATION_ID: Location ID {scan_req.location_id} does not exist or does not belong to project {project.id}."
            )
    else:
        loc = project.locations[0] if project.locations else None

    lat_center = scan_req.center_lat if scan_req.center_lat is not None else (loc.latitude if loc else None)
    lng_center = scan_req.center_lng if scan_req.center_lng is not None else (loc.longitude if loc else None)

    # Attempt automatic geocoding fallback if location address/city exists but coordinates are missing
    if (lat_center is None or lng_center is None) and (loc or scan_req.center_name):
        from app.services.geocoding import GeocodingService
        geo_coords = None
        if loc and (loc.address or loc.city):
            geo_coords = await GeocodingService.geocode_address(
                address=loc.address,
                city=loc.city,
                state=loc.state,
                postal_code=loc.postal_code,
                country=loc.country
            )
        if not geo_coords and scan_req.center_name:
            geo_coords = await GeocodingService.geocode_address(city=scan_req.center_name)

        if geo_coords:
            lat_center, lng_center = geo_coords
            if loc:
                loc.latitude = lat_center
                loc.longitude = lng_center
                db.add(loc)
                await db.commit()
                await db.refresh(loc)
                log_user_action(
                    request, "SAVE_LOCATION_COORDINATES",
                    user_id=current_user.id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    location_id=loc.id,
                    latitude=lat_center,
                    longitude=lng_center
                )

    if lat_center is None or lng_center is None:
        raise HTTPException(
            status_code=400,
            detail="LOCATION_COORDINATES_REQUIRED: Valid geographic coordinates (latitude and longitude) are required for a Geo-Grid scan. Please configure your business location address or coordinates."
        )

    if not (-90.0 <= lat_center <= 90.0):
        raise HTTPException(status_code=400, detail="INVALID_LATITUDE: Latitude must be between -90 and 90 degrees.")
    if not (-180.0 <= lng_center <= 180.0):
        raise HTTPException(status_code=400, detail="INVALID_LONGITUDE: Longitude must be between -180 and 180 degrees.")

    # Auto-persist manual coordinates into Location database entity so they survive page reload
    if scan_req.center_lat is not None or scan_req.center_lng is not None:
        if loc:
            loc.latitude = lat_center
            loc.longitude = lng_center
            db.add(loc)
            await db.commit()
            await db.refresh(loc)
            log_user_action(
                request, "SAVE_LOCATION_COORDINATES",
                user_id=current_user.id,
                organization_id=project.organization_id,
                project_id=project.id,
                location_id=loc.id,
                latitude=lat_center,
                longitude=lng_center
            )
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
            loc = new_loc
            log_user_action(
                request, "SAVE_LOCATION_COORDINATES",
                user_id=current_user.id,
                organization_id=project.organization_id,
                project_id=project.id,
                location_id=new_loc.id,
                latitude=lat_center,
                longitude=lng_center
            )

    radius = scan_req.radius_km or 10.0
    grid_size = scan_req.grid_size or 5
    center_name = (loc.name if loc and loc.name else None) or scan_req.center_name or "Business Location"

    log_user_action(
        request, "RUN_GEO_GRID",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project.id,
        location_id=loc.id if loc else "manual",
        location_name=center_name,
        keyword=kw_phrase,
        grid_size=grid_size,
        radius_km=radius
    )

    # 3. Execute real GeoGrid scan via GeoGridScanner
    provider = await get_organization_serp_provider(db, project.organization_id)
    scan_result = await GeoGridScanner.scan_grid(
        provider=provider,
        keyword=kw_phrase,
        target_domain=project.domain,
        center_lat=lat_center,
        center_lng=lng_center,
        radius_km=radius,
        grid_size=grid_size,
        concurrency_limit=3
    )

    # 4. Save scan in database
    scan = GeoGridScan(
        project_id=project.id,
        keyword_id=kw.id,
        center_name=center_name,
        center_lat=lat_center,
        center_lng=lng_center,
        radius_km=radius,
        grid_size=grid_size,
        average_rank=scan_result["average_rank"],
        local_visibility_pct=scan_result["local_visibility_pct"],
        grid_points=scan_result["grid_points"],
        scan_status=scan_result["scan_status"],
        total_points=scan_result["total_points"],
        successful_points=scan_result["successful_points"],
        failed_points=scan_result["failed_points"]
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    if scan_result["scan_status"] == "failed":
        log_user_action(
            request, "GEO_GRID_FAILED",
            user_id=current_user.id,
            organization_id=project.organization_id,
            project_id=project.id,
            total=scan_result["total_points"],
            successful=scan_result["successful_points"],
            failed=scan_result["failed_points"],
            reason="All grid point queries failed"
        )
    else:
        log_user_action(
            request, "GEO_GRID_COMPLETE",
            user_id=current_user.id,
            organization_id=project.organization_id,
            project_id=project.id,
            total=scan_result["total_points"],
            successful=scan_result["successful_points"],
            failed=scan_result["failed_points"]
        )

    return scan

@router.post("/{project_id}/grid/rescan", response_model=GeoGridScanOut)
@router.post("/{project_id}/grid/scan", response_model=GeoGridScanOut)
async def rescan_project_grid(
    request: Request,
    project_id: int,
    scan_req: GeoGridScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Convenience endpoint for frontend to rescan active project grid.
    """
    project = await verify_project_access(project_id, current_user, db)
    # Find primary keyword if not passed
    if not scan_req.keyword_id:
        kw_phrase = (scan_req.keyword or (f"{project.primary_category} near me" if project.primary_category else project.name)).strip()
        kw_match = await db.execute(
            select(Keyword).where(Keyword.project_id == project_id, Keyword.keyword == kw_phrase)
        )
        matched_kw = kw_match.scalars().first()
        if not matched_kw:
            # Check if ANY keyword is tracked
            kw_res = await db.execute(
                select(Keyword).where(Keyword.project_id == project_id).order_by(Keyword.id.asc())
            )
            any_kw = kw_res.scalars().first()
            if any_kw:
                matched_kw = any_kw
            else:
                # Auto-create initial keyword for the project
                proj_res = await db.execute(
                    select(Project).options(selectinload(Project.locations)).where(Project.id == project.id)
                )
                proj_full = proj_res.scalars().first()
                loc = proj_full.locations[0] if proj_full and proj_full.locations else None
                loc_name = (
                    loc.city if loc and loc.city else (loc.name if loc and loc.name else None)
                )
                matched_kw = Keyword(
                    project_id=project_id,
                    keyword=kw_phrase,
                    target_location=loc_name,
                    search_intent=None,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(matched_kw)
                await db.flush()
                await db.refresh(matched_kw)

        scan_req.keyword_id = matched_kw.id
        scan_req.keyword = matched_kw.keyword

    return await trigger_grid_scan(request, scan_req, current_user, db)

@router.get("/{project_id}/grid", response_model=Optional[GeoGridScanOut])
async def get_project_grid(
    request: Request,
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns latest GeoGrid scan for project.
    """
    project = await verify_project_access(project_id, current_user, db)
    log_user_action(
        request, "OPEN_GEO_GRID",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project_id
    )
    query = select(GeoGridScan).where(GeoGridScan.project_id == project_id)
    if keyword_id:
        query = query.where(GeoGridScan.keyword_id == keyword_id)
    result = await db.execute(query.order_by(GeoGridScan.id.desc()))
    return result.scalars().first()

@router.get("/grid-scan/{project_id}/latest", response_model=Optional[GeoGridScanOut])
async def get_latest_grid_scan(
    request: Request,
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_project_grid(request, project_id, keyword_id, current_user, db)

