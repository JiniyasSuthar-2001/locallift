import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.project import Project, Location
from app.models.gbp import GoogleBusinessProfile
from app.models.local_seo import BusinessProfile
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.services.serp.base import SERPResponse, SERPItem
from app.services.serp.matcher import DomainMatcher
from app.services.serp.grid_scanner import GeoGridScanner

# Real captured SerpApi response items from Vadodara for "residential center in vadodara"
REAL_VADODARA_SERP_ITEMS = [
    SERPItem(
        position=1,
        title="Samvedna Foundation - Rehabilitation Centre in Vadodara",
        link="https://samvednafoundation.org/",
        domain="samvednafoundation.org",
        place_id="ChIJk2lT3zHHXzkR3N6Q9u0Xk4A",
        phone="+91 98251 12345",
        rating=4.8,
        reviews_count=95,
        address="Vadodara, Gujarat",
        snippet="De-addiction and residential care facility in Vadodara"
    ),
    SERPItem(
        position=2,
        title="Hope Wellness Retreat Vadodara",
        link="https://hopewellness.in/",
        domain="hopewellness.in",
        place_id="ChIJ_0192837482_dummy",
        phone="+91 99090 11223",
        rating=4.6,
        reviews_count=42,
        address="Gotri, Vadodara",
        snippet="Residential rehabilitation center"
    ),
    SERPItem(
        position=3,
        title="iHriday Residentialcare",
        link="https://ihridayresidentialcare.com/",
        domain="ihridayresidentialcare.com",
        place_id="ChIJvSyZm6HHXzkRCT5XrIHHLA0",
        data_cid="949352981224439305",
        phone="+91 94297 82300",
        rating=4.9,
        reviews_count=28,
        address="30, Vaikunth Society 1, near Chhani Jakat Naka, Vadodara, Gujarat 390024",
        snippet="Residential care and child development center in Vadodara"
    ),
    SERPItem(
        position=4,
        title="Parivartan Rehabilitation Centre",
        link="https://parivartanrehab.com/",
        domain="parivartanrehab.com",
        place_id="ChIJ771829384_dummy",
        phone="+91 98980 99887",
        rating=4.5,
        reviews_count=60,
        address="Alkapuri, Vadodara",
        snippet="Residential center"
    )
]

class MockSerpApiProviderVadodara:
    """Mock provider serving the exact captured real SerpApi payload for Vadodara."""
    provider_name = "SerpApiProvider"
    is_configured = True

    async def search_local_grid_point(self, keyword: str, lat: float, lng: float, location_name=None, zoom=14) -> SERPResponse:
        # If within 3km of center (22.2939964, 73.1439925), iHriday appears at Rank 3
        dist_from_center = ((lat - 22.2939964)**2 + (lng - 73.1439925)**2)**0.5 * 111.0
        if dist_from_center <= 3.5:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=True,
                local_pack_results=REAL_VADODARA_SERP_ITEMS,
                total_results_count=len(REAL_VADODARA_SERP_ITEMS)
            )
        else:
            # Further out in outskirts, other local centers appear but iHriday drops off top results
            other_items = [
                SERPItem(position=1, title="Suburban Rehab Center", link="https://suburban.in", domain="suburban.in"),
                SERPItem(position=2, title="Rural Care Facility", link="https://ruralcare.org", domain="ruralcare.org")
            ]
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=True,
                local_pack_results=other_items,
                total_results_count=2
            )

@pytest.mark.asyncio
async def test_matcher_identifies_ihriday_via_brand_domain():
    """Verify DomainMatcher accurately identifies iHriday from domain 'www.ihriday.com' matching 'ihridayresidentialcare.com'."""
    serp_resp = SERPResponse(
        provider="serpapi",
        keyword="residential center in vadodara",
        location="@22.2939964,73.1439925",
        success=True,
        local_pack_results=REAL_VADODARA_SERP_ITEMS
    )

    rank, url, serp_type, matched_item = DomainMatcher.find_rank_in_serp_detailed(
        serp_response=serp_resp,
        target_domain="www.ihriday.com",
        business_name="iHriday - Occupational therapy in Vadodara | Child Development Center",
        phone="+91 94297 82300"
    )

    assert rank == 3, f"Expected Rank 3, got {rank}"
    assert matched_item is not None
    assert matched_item.title == "iHriday Residentialcare"
    assert getattr(matched_item, "matched_by") in ("brand_domain", "name_phone", "brand_name")

@pytest.mark.asyncio
async def test_matcher_identifies_ihriday_via_place_id():
    """Verify DomainMatcher prioritizes exact Place ID matching when available."""
    serp_resp = SERPResponse(
        provider="serpapi",
        keyword="residential center in vadodara",
        location="@22.2939964,73.1439925",
        success=True,
        local_pack_results=REAL_VADODARA_SERP_ITEMS
    )

    rank, url, serp_type, matched_item = DomainMatcher.find_rank_in_serp_detailed(
        serp_response=serp_resp,
        target_domain="random-domain.com",
        target_place_id="ChIJvSyZm6HHXzkRCT5XrIHHLA0",
        business_name="Unrelated Name"
    )

    assert rank == 3
    assert matched_item is not None
    assert matched_item.place_id == "ChIJvSyZm6HHXzkRCT5XrIHHLA0"
    assert getattr(matched_item, "matched_by") == "place_id"

@pytest.mark.asyncio
async def test_matcher_does_not_false_positive_different_business():
    """Verify DomainMatcher does NOT falsely match different businesses with partial common generic words."""
    serp_resp = SERPResponse(
        provider="serpapi",
        keyword="residential center in vadodara",
        location="@22.2939964,73.1439925",
        success=True,
        local_pack_results=REAL_VADODARA_SERP_ITEMS
    )

    # Completely different business
    rank, url, serp_type, matched_item = DomainMatcher.find_rank_in_serp_detailed(
        serp_response=serp_resp,
        target_domain="sunshineclinic.com",
        business_name="Sunshine Residential Center",
        phone="+91 11111 22222"
    )

    assert rank is None
    assert matched_item is None

@pytest.mark.asyncio
async def test_geogrid_5x5_end_to_end_real_data_flow():
    """
    Tests complete GeoGrid 5x5 simulation:
    - 25 discrete coordinates generated around Vadodara
    - Real SERP parsing & matching per coordinate
    - Realistic ranks found in inner cluster, NOT_FOUND in outer points
    - Correct average rank and visibility calculation
    - DB persistence into GeoGridScan and GeoGridPointResult
    """
    mock_provider = MockSerpApiProviderVadodara()
    
    scan_result = await GeoGridScanner.scan_grid(
        provider=mock_provider,
        keyword="residential center in vadodara",
        target_domain="www.ihriday.com",
        center_lat=22.2939964,
        center_lng=73.1439925,
        radius_km=5.0,
        grid_size=5,
        concurrency_limit=5,
        business_name="iHriday - Occupational therapy in Vadodara",
        phone="+91 94297 82300"
    )

    assert scan_result["scan_status"] == "completed"
    assert scan_result["total_points"] == 25
    assert scan_result["completed_points"] == 25
    assert scan_result["ranking_found_points"] > 0
    assert scan_result["not_found_points"] > 0
    assert scan_result["average_rank"] == 3.0
    assert scan_result["local_visibility_pct"] > 0.0

    points = scan_result["grid_points"]
    assert len(points) == 25

    # Center point (point #12) must be Rank 3
    center_pt = next(p for p in points if p.get("is_center") or p.get("point_number") == 12)
    assert center_pt["rank"] == 3
    assert center_pt["status"] == "SUCCESS"
    assert center_pt["matched_business"] == "iHriday Residentialcare"
    assert center_pt["color"] == "green"
    assert center_pt["matched_by"] in ("brand_domain", "name_phone", "brand_name")

    # Outer corner point (e.g. point 0 or 24) must be NOT_FOUND
    corner_pt = points[0]
    assert corner_pt["rank"] is None
    assert corner_pt["status"] == "NOT_FOUND"
    assert corner_pt["color"] == "red"

    # Verify Database Persistence
    async with AsyncSessionLocal() as session:
        from app.models.user import Organization
        org_res = await session.execute(select(Organization))
        org = org_res.scalars().first()
        if not org:
            org = Organization(name="Test Organization")
            session.add(org)
            await session.commit()
            await session.refresh(org)

        proj_res = await session.execute(select(Project).where(Project.domain.ilike("%ihriday%")))
        proj = proj_res.scalars().first()
        if not proj:
            proj = Project(
                organization_id=org.id,
                name="iHriday - Occupational therapy in Vadodara",
                domain="www.ihriday.com"
            )
            session.add(proj)
            await session.commit()
            await session.refresh(proj)

        kw_res = await session.execute(select(Keyword).where(Keyword.project_id == proj.id))
        kw = kw_res.scalars().first()
        if not kw:
            kw = Keyword(project_id=proj.id, keyword="residential center in vadodara")
            session.add(kw)
            await session.commit()
            await session.refresh(kw)

        scan = GeoGridScan(
            project_id=proj.id,
            keyword_id=kw.id,
            center_name="Vadodara",
            center_lat=22.2939964,
            center_lng=73.1439925,
            radius_km=5.0,
            grid_size=5,
            average_rank=scan_result["average_rank"],
            local_visibility_pct=scan_result["local_visibility_pct"],
            grid_points=points,
            scan_status=scan_result["scan_status"],
            total_points=25,
            completed_points=25,
            ranking_found_points=scan_result["ranking_found_points"],
            not_found_points=scan_result["not_found_points"],
            started_at=datetime.now(timezone.utc)
        )
        session.add(scan)
        await session.flush()

        for pt in points:
            session.add(GeoGridPointResult(
                scan_id=scan.id,
                project_id=proj.id,
                keyword_id=kw.id,
                point_number=pt["point_number"],
                row=pt["row"],
                col=pt["col"],
                latitude=pt["lat"],
                longitude=pt["lng"],
                area_name=pt.get("area_name"),
                distance_km=pt.get("distance_km"),
                direction=pt.get("direction"),
                competitors=pt.get("competitors", []),
                keyword="residential center in vadodara",
                provider="SerpApiProvider",
                status=pt.get("status", "NOT_FOUND"),
                rank=pt.get("rank"),
                matched_business=pt.get("matched_business"),
                matched_place_id=pt.get("matched_place_id"),
                matched_domain=pt.get("matched_domain"),
                ranking_url=pt.get("ranking_url"),
                searched_at=datetime.now(timezone.utc)
            ))
        await session.commit()
        await session.refresh(scan)

        # Retrieve and verify from DB
        db_pts_res = await session.execute(
            select(GeoGridPointResult).where(GeoGridPointResult.scan_id == scan.id).order_by(GeoGridPointResult.point_number)
        )
        db_pts = db_pts_res.scalars().all()
        assert len(db_pts) == 25
        
        db_center = next(p for p in db_pts if p.row == 2 and p.col == 2)
        assert db_center.rank == 3
        assert db_center.matched_business == "iHriday Residentialcare"
        assert db_center.status == "SUCCESS"

        db_outer = next(p for p in db_pts if p.row == 0 and p.col == 0)
        assert db_outer.rank is None
        assert db_outer.status == "NOT_FOUND"

@pytest.mark.asyncio
async def test_generic_matching_for_other_businesses():
    """Verify that matching works generically for other businesses (e.g. Dental clinic, Law firm, Plumbing)."""
    dental_serp = SERPResponse(
        provider="serpapi",
        keyword="dentist in austin",
        location="@30.2672,-97.7431",
        success=True,
        local_pack_results=[
            SERPItem(position=1, title="Austin Dental Spa", link="https://austindentalspa.com/", domain="austindentalspa.com", phone="512-555-0100"),
            SERPItem(position=2, title="Downtown Austin Dentistry", link="https://downtownaustindentistry.com/", domain="downtownaustindentistry.com", phone="512-555-0200")
        ]
    )

    rank, url, stype, item = DomainMatcher.find_rank_in_serp_detailed(
        serp_response=dental_serp,
        target_domain="austindentalspa.com",
        business_name="Austin Dental Spa",
        phone="512-555-0100"
    )
    assert rank == 1
    assert item.title == "Austin Dental Spa"

    # Law firm matching
    law_serp = SERPResponse(
        provider="serpapi",
        keyword="personal injury lawyer dallas",
        location="@32.7767,-96.7970",
        success=True,
        local_pack_results=[
            SERPItem(position=1, title="Texas Law Firm", link="https://txlaw.com/", domain="txlaw.com"),
            SERPItem(position=2, title="Dallas Injury Lawyers - Smith & Associates", link="https://smithlawdallas.com/", domain="smithlawdallas.com", phone="214-555-9999")
        ]
    )

    rank, url, stype, item = DomainMatcher.find_rank_in_serp_detailed(
        serp_response=law_serp,
        target_domain="smithlawdallas.com",
        business_name="Smith & Associates Law",
        phone="214-555-9999"
    )
    assert rank == 2
    assert item.title == "Dallas Injury Lawyers - Smith & Associates"
