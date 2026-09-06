import random
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project, Location
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan
from app.schemas.ranking import KeywordCreate, KeywordOut, GeoGridScanOut, GeoGridScanRequest

router = APIRouter(prefix="/keywords", tags=["Keywords & Rankings"])

@router.get("/{project_id}", response_model=List[KeywordOut])
async def list_keywords(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Keyword).where(Keyword.project_id == project_id).order_by(Keyword.current_rank.asc().nullslast())
    )
    return result.scalars().all()

@router.post("", response_model=KeywordOut)
async def add_keyword(
    kw_in: KeywordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    kw = Keyword(
        project_id=kw_in.project_id,
        keyword=kw_in.keyword,
        search_intent=kw_in.search_intent or "Commercial",
        search_volume=kw_in.search_volume or 450,
        difficulty=kw_in.difficulty or 35,
        target_location=kw_in.target_location or "Brisbane CBD",
        target_rank=kw_in.target_rank or 3,
        current_rank=random.randint(1, 12),
        previous_rank=random.randint(2, 14),
        ranking_url=f"https://example.com/services/{kw_in.keyword.lower().replace(' ', '-')}",
        serp_type="Local Pack",
        opportunity_score="HIGH" if kw_in.search_volume and kw_in.search_volume > 300 else "MEDIUM",
        business_relevance=kw_in.business_relevance or "High"
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw

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
    await db.delete(kw)
    await db.commit()
    return {"message": "Keyword deleted successfully"}

@router.post("/grid-scan", response_model=GeoGridScanOut)
async def trigger_grid_scan(
    scan_req: GeoGridScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    kw_res = await db.execute(select(Keyword).where(Keyword.id == scan_req.keyword_id))
    kw = kw_res.scalars().first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    grid_size = scan_req.grid_size or 5
    lat_center = scan_req.center_lat or -27.4698
    lng_center = scan_req.center_lng or 153.0251
    radius = scan_req.radius_km or 10.0

    # Generate matrix of grid points
    grid_points = []
    step = (radius * 2) / (grid_size - 1) if grid_size > 1 else 1.0
    total_ranks = 0
    top_3_count = 0

    for row in range(grid_size):
        for col in range(grid_size):
            # Calculate simulated distance from center
            dist_from_center = abs(row - (grid_size // 2)) + abs(col - (grid_size // 2))
            
            # Rank increases with distance from center
            if dist_from_center == 0:
                rank = random.choice([1, 1, 2])
            elif dist_from_center == 1:
                rank = random.choice([1, 2, 3])
            elif dist_from_center == 2:
                rank = random.choice([2, 3, 4, 5])
            elif dist_from_center == 3:
                rank = random.choice([4, 6, 8, 11])
            else:
                rank = random.choice([7, 12, 16, 20])

            total_ranks += rank
            if rank <= 3:
                top_3_count += 1

            # Lat/lng offset
            lat_offset = (row - (grid_size // 2)) * (step / 111.0)
            lng_offset = (col - (grid_size // 2)) * (step / 111.0)

            grid_points.append({
                "row": row,
                "col": col,
                "lat": round(lat_center + lat_offset, 6),
                "lng": round(lng_center + lng_offset, 6),
                "rank": rank,
                "status": "green" if rank <= 3 else "yellow" if rank <= 7 else "red",
                "competitor_ahead": "City Electricians Group" if rank > 3 else None
            })

    avg_rank = round(total_ranks / (grid_size * grid_size), 2)
    vis_pct = round((top_3_count / (grid_size * grid_size)) * 100, 1)

    scan = GeoGridScan(
        project_id=kw.project_id,
        keyword_id=kw.id,
        center_name=scan_req.center_name or "City Center",
        center_lat=lat_center,
        center_lng=lng_center,
        radius_km=radius,
        grid_size=grid_size,
        average_rank=avg_rank,
        local_visibility_pct=vis_pct,
        grid_points=grid_points
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan

@router.get("/grid-scan/{project_id}/latest", response_model=Optional[GeoGridScanOut])
async def get_latest_grid_scan(
    project_id: int,
    keyword_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(GeoGridScan).where(GeoGridScan.project_id == project_id)
    if keyword_id:
        query = query.where(GeoGridScan.keyword_id == keyword_id)
    result = await db.execute(query.order_by(GeoGridScan.id.desc()))
    return result.scalars().first()
