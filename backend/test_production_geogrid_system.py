"""
Production Geo-Grid Local Visibility System Test Suite
Validates:
1. Grid coordinate generation for 3x3 (9 points), 5x5 (25 points), 7x7 (49 points).
2. Point result database persistence with distance_km, direction, competitors.
3. Point analysis endpoint /api/v1/keywords/{project_id}/grid/scans/{scan_id}/points/{point_number}
   with WHAT, WHERE, HOW, WHY evidence-based diagnostics.
4. Competitor hierarchy (competitors_above, target_business, competitors_below, result_depth).
5. Server-side project authorization (unauthorized access rejection, 404 on invalid IDs).
"""

import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.services.serp.grid_scanner import GeoGridScanner


def test_grid_scanner_coordinate_generation_sizes():
    """Verify 3x3, 5x5, and 7x7 grid point counts and geometry."""
    center_lat, center_lng = 34.0522, -118.2437
    radius = 5.0

    # 3x3 = 9 points
    grid_3 = GeoGridScanner.calculate_grid_coordinates(center_lat, center_lng, radius, 3)
    assert len(grid_3) == 9
    assert grid_3[0]["row"] == 0 and grid_3[0]["col"] == 0
    assert grid_3[4]["is_center"] is True
    assert grid_3[4]["distance_km"] == 0.0
    assert grid_3[4]["direction"] == "Center"

    # 5x5 = 25 points
    grid_5 = GeoGridScanner.calculate_grid_coordinates(center_lat, center_lng, radius, 5)
    assert len(grid_5) == 25
    assert grid_5[12]["is_center"] is True
    assert grid_5[12]["distance_km"] == 0.0

    # 7x7 = 49 points
    grid_7 = GeoGridScanner.calculate_grid_coordinates(center_lat, center_lng, radius, 7)
    assert len(grid_7) == 49
    assert grid_7[24]["is_center"] is True
    assert grid_7[24]["distance_km"] == 0.0


def test_distance_and_direction_calculation():
    """Verify distance and direction calculations."""
    lat1, lng1 = 34.0522, -118.2437
    # Center
    dist, dir_name = GeoGridScanner.calculate_distance_and_direction(lat1, lng1, lat1, lng1)
    assert dist == 0.0
    assert dir_name == "Center"

    # North
    lat_north = lat1 + 0.05
    dist_n, dir_n = GeoGridScanner.calculate_distance_and_direction(lat1, lng1, lat_north, lng1)
    assert dist_n > 0
    assert dir_n == "North"

    # East
    lng_east = lng1 + 0.05
    dist_e, dir_e = GeoGridScanner.calculate_distance_and_direction(lat1, lng1, lat1, lng_east)
    assert dist_e > 0
    assert dir_e == "East"


@pytest.mark.asyncio
async def test_point_analysis_endpoint_and_authorization():
    """Verify point analysis endpoint returns structured WHAT/WHERE/HOW/WHY and enforces security."""
    await init_test_db(reset=False)

    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Metro Dental Los Angeles",
        domain="metrodentalla.com"
    )
    user2, org2, proj2, token2 = await create_test_tenant(
        project_name="Other Tenant Business",
        domain="othertenant.com"
    )

    # Insert a real completed scan with points for proj1
    async with AsyncSessionLocal() as db:
        kw = Keyword(
            project_id=proj1.id,
            keyword="emergency dentist los angeles",
            target_location="Los Angeles, CA",
            last_checked_at=datetime.now(timezone.utc)
        )
        db.add(kw)
        await db.flush()

        scan = GeoGridScan(
            project_id=proj1.id,
            keyword_id=kw.id,
            center_name="Los Angeles Downtown",
            center_lat=34.0522,
            center_lng=-118.2437,
            radius_km=5.0,
            grid_size=3,
            average_rank=4.0,
            local_visibility_pct=66.7,
            scan_status="completed",
            total_points=9,
            completed_points=9,
            successful_points=9,
            failed_points=0,
            ranking_found_points=6,
            not_found_points=3,
            provider_error_points=0,
            timeout_points=0,
            started_at=datetime.now(timezone.utc),
            grid_points=[]
        )
        db.add(scan)
        await db.flush()

        # Insert Point #1 (Ranked #4 with competitors)
        sample_competitors = [
            {"position": 1, "title": "Top Smile Dental", "domain": "topsmile.com", "rating": 4.9, "reviews_count": 320, "category": "Dentist", "is_target": False},
            {"position": 2, "title": "LA City Dental", "domain": "lacitydental.com", "rating": 4.8, "reviews_count": 210, "category": "Dental clinic", "is_target": False},
            {"position": 3, "title": "Downtown Dental Care", "domain": "downtowndentalcare.com", "rating": 4.7, "reviews_count": 180, "category": "Dentist", "is_target": False},
            {"position": 4, "title": "Metro Dental Los Angeles", "domain": "metrodentalla.com", "rating": 4.6, "reviews_count": 115, "category": "Dentist", "is_target": True},
            {"position": 5, "title": "Angel City Teeth", "domain": "angelcityteeth.com", "rating": 4.5, "reviews_count": 90, "category": "Dentist", "is_target": False},
        ]
        pt1 = GeoGridPointResult(
            scan_id=scan.id,
            project_id=proj1.id,
            keyword_id=kw.id,
            point_number=1,
            row=0,
            col=0,
            latitude=34.08,
            longitude=-118.28,
            distance_km=4.5,
            direction="NW",
            competitors=sample_competitors,
            keyword="emergency dentist los angeles",
            provider="serpapi",
            status="RANKED",
            rank=4,
            matched_business="Metro Dental Los Angeles",
            matched_place_id="ChIJsample123",
            matched_domain="metrodentalla.com",
            ranking_url="https://google.com/maps/place/sample123",
            searched_at=datetime.now(timezone.utc)
        )
        # Insert Point #2 (Not Found)
        pt2 = GeoGridPointResult(
            scan_id=scan.id,
            project_id=proj1.id,
            keyword_id=kw.id,
            point_number=2,
            row=0,
            col=1,
            latitude=34.08,
            longitude=-118.24,
            distance_km=3.1,
            direction="N",
            competitors=sample_competitors[:3],
            keyword="emergency dentist los angeles",
            provider="serpapi",
            status="NOT_FOUND",
            rank=None,
            searched_at=datetime.now(timezone.utc)
        )
        db.add_all([pt1, pt2])
        await db.commit()
        scan_id = scan.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = {"Authorization": f"Bearer {token1}"}
        h2 = {"Authorization": f"Bearer {token2}"}

        # 1. Successful point #1 analysis
        res1 = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/1", headers=h1)
        assert res1.status_code == 200
        data1 = res1.json()

        # Check LOCATION
        assert data1["location"]["point_number"] == 1
        assert data1["location"]["row"] == 0
        assert data1["location"]["col"] == 0
        assert data1["location"]["distance_km"] == 4.5
        assert data1["location"]["direction"] == "NW"

        # Check RANKING
        assert data1["ranking"]["rank"] == 4
        assert data1["ranking"]["status"] == "RANKED"
        assert data1["ranking"]["business_name"] == proj1.name
        assert data1["ranking"]["place_id"] == "ChIJsample123"

        # Check COMPETITORS HIERARCHY
        comp_hier = data1["competitors_hierarchy"]
        assert len(comp_hier["competitors_above"]) == 3
        assert comp_hier["target_business"]["position"] == 4
        assert len(comp_hier["competitors_below"]) == 1
        assert comp_hier["result_depth"] == 10  # Rank #4 maps to Top 10

        # Check WHAT / WHERE / HOW / WHY DIAGNOSTICS
        diag = data1["diagnostics"]
        assert "ranked #4" in diag["what"].lower()
        assert "4.5 km" in diag["where"]
        assert "NW" in diag["where"]
        assert len(diag["how"]) >= 4
        assert len(diag["why"]) > 0

        # 2. Point #2 (Not Found) analysis
        res2 = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/2", headers=h1)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["ranking"]["status"] == "NOT_FOUND"
        assert "not found" in data2["diagnostics"]["what"].lower()
        assert data2["competitors_hierarchy"]["not_found_in_depth"] is True

        # 3. Security: Tenant 2 unauthorized access to Tenant 1's scan point -> 404 or 403
        res_sec = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/1", headers=h2)
        assert res_sec.status_code in [403, 404]

        # 4. Invalid point number -> 404
        res_inv = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/99", headers=h1)
        assert res_inv.status_code == 404
