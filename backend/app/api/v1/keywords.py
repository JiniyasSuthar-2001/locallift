import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
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
from app.services.serp import get_serp_provider, DomainMatcher, GeoGridScanner

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
        search_volume=kw_in.search_volume or 0,
        difficulty=kw_in.difficulty or 30,
        target_location=kw_in.target_location or "Metro Area",
        target_rank=kw_in.target_rank or 3,
        current_rank=None,
        previous_rank=None,
        ranking_url=None,
        serp_type="Local Pack",
        opportunity_score="HIGH" if kw_in.search_volume and kw_in.search_volume > 300 else "MEDIUM",
        business_relevance=kw_in.business_relevance or "High",
        last_checked_at=datetime.now(timezone.utc)
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)

    # If SERP provider is configured, attempt an immediate initial live lookup
    provider = get_serp_provider()
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

    provider = get_serp_provider()
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
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes real live SERP checks for all tracked keywords in a project.
    """
    project = await verify_project_access(project_id, current_user, db)

    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
    keywords = kw_res.scalars().all()

    provider = get_serp_provider()
    country = "au" if "com.au" in project.domain else "us"

    results = []
    checked_count = 0
    not_found_count = 0
    error_count = 0

    for kw in keywords:
        serp_resp = await provider.search_keyword(
            keyword=kw.keyword,
            location=kw.target_location,
            country=country
        )

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
                status="provider_error",
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
    keyword_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalars().first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    await verify_project_access(kw.project_id, current_user, db)

    await db.delete(kw)
    await db.commit()
    return {"message": "Keyword deleted successfully"}

# ---------------------------------------------------------------------------
# Real 5x5 Geo-Grid Endpoints
# ---------------------------------------------------------------------------

@router.post("/grid-scan", response_model=GeoGridScanOut)
async def trigger_grid_scan(
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

    # 2. Determine center coordinates from location or request
    loc = project.locations[0] if project.locations else None
    lat_center = scan_req.center_lat or (loc.latitude if loc and loc.latitude else -27.4698)
    lng_center = scan_req.center_lng or (loc.longitude if loc and loc.longitude else 153.0251)
    radius = scan_req.radius_km or 10.0
    grid_size = scan_req.grid_size or 5
    center_name = scan_req.center_name or (loc.name if loc else "City Center")

    # 3. Execute real GeoGrid scan via GeoGridScanner
    provider = get_serp_provider()
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
        grid_points=scan_result["grid_points"]
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan

@router.post("/{project_id}/grid/rescan", response_model=GeoGridScanOut)
async def rescan_project_grid(
    project_id: int,
    scan_req: GeoGridScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Convenience endpoint for frontend to rescan active project grid.
    """
    await verify_project_access(project_id, current_user, db)
    # Find primary keyword if not passed
    if not scan_req.keyword_id:
        kw_res = await db.execute(
            select(Keyword).where(Keyword.project_id == project_id).order_by(Keyword.id.asc())
        )
        kw = kw_res.scalars().first()
        if not kw:
            raise HTTPException(status_code=400, detail="No keywords tracked for this project. Add a keyword first.")
        scan_req.keyword_id = kw.id

    return await trigger_grid_scan(scan_req, current_user, db)

@router.get("/{project_id}/grid", response_model=Optional[GeoGridScanOut])
async def get_project_grid(
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns latest GeoGrid scan for project.
    """
    await verify_project_access(project_id, current_user, db)
    query = select(GeoGridScan).where(GeoGridScan.project_id == project_id)
    if keyword_id:
        query = query.where(GeoGridScan.keyword_id == keyword_id)
    result = await db.execute(query.order_by(GeoGridScan.id.desc()))
    return result.scalars().first()

@router.get("/grid-scan/{project_id}/latest", response_model=Optional[GeoGridScanOut])
async def get_latest_grid_scan(
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_project_grid(project_id, keyword_id, current_user, db)
