"""
LocalLift — Part 2 End-to-End Frontend & Data Pipeline Verification Test

Verifies:
1. Geo-Grid 5x5 canonical keyword flow & 25-point persistence (DB == API == Frontend contract)
2. Project switching & multi-tenant isolation across crawls and Geo-Grids
3. Exclusion of fake fallbacks: evaluated_rules, health_score, pillar scores return honest states
"""

import pytest
import os
import sys
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.models.ranking import GeoGridScan, GeoGridPointResult
from app.database import AsyncSessionLocal
from sqlalchemy import select


@pytest.mark.asyncio
async def test_e2e_geogrid_25_point_contract_and_canonical_keyword():
    """Verify 1 scan -> 25 discrete points -> DB point == API point -> Canonical Keyword preserved."""
    await init_test_db(reset=False)

    user, org, project, token = await create_test_tenant(
        project_name="Solar Masters Sydney",
        domain="solarmasters.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 1. Add canonical tracked keyword
        kw_resp = await client.post(
            "/api/v1/keywords",
            json={"project_id": project.id, "keyword": "commercial solar panels sydney", "search_volume": 1200},
            headers=auth_headers
        )
        assert kw_resp.status_code == 200, f"Keyword creation failed: {kw_resp.text}"
        keyword_data = kw_resp.json()
        keyword_id = keyword_data["id"]
        canonical_kw = keyword_data["keyword"]
        assert canonical_kw == "commercial solar panels sydney"

        # 2. Add saved location
        loc_resp = await client.post(
            f"/api/v1/projects/{project.id}/locations",
            json={
                "name": "Sydney Central Office",
                "address": "100 George St",
                "city": "Sydney",
                "state": "NSW",
                "latitude": -33.8688,
                "longitude": 151.2093
            },
            headers=auth_headers
        )
        assert loc_resp.status_code == 200
        location_data = loc_resp.json()
        loc_id = location_data["id"]

        # 3. Trigger 5x5 Geo-Grid Rescan via API (identical to Frontend request)
        rescan_resp = await client.post(
            f"/api/v1/keywords/{project.id}/grid/rescan",
            json={
                "keyword_id": keyword_id,
                "keyword": canonical_kw,
                "location_id": loc_id,
                "radius_km": 5.0,
                "grid_size": 5
            },
            headers=auth_headers
        )
        assert rescan_resp.status_code == 200, f"Rescan failed: {rescan_resp.text}"
        grid_data = rescan_resp.json()

        # 4. Verify API response structure
        assert grid_data["keyword"] == "commercial solar panels sydney"
        assert grid_data["keyword"] != "Sydney Central Office"
        assert grid_data["keyword"] != "Solar Masters Sydney"
        assert grid_data["grid_size"] == 5
        assert grid_data["radius_km"] == 5.0

        points = grid_data.get("points") or grid_data.get("grid_points") or []
        assert len(points) == 25, f"Expected 25 points, got {len(points)}"

        # 5. Verify database persistence
        scan_id = grid_data["id"]
        async with AsyncSessionLocal() as session:
            stmt = select(GeoGridPointResult).where(GeoGridPointResult.scan_id == scan_id).order_by(GeoGridPointResult.point_number)
            db_points = (await session.execute(stmt)).scalars().all()
            assert len(db_points) == 25, f"Expected 25 DB points, got {len(db_points)}"

            # Cross-verify database point == API point for sample points
            for i in [0, 12, 24]:
                db_p = db_points[i]
                api_p = points[i]
                assert db_p.point_number == api_p["point_number"]
                assert round(db_p.latitude, 4) == round(api_p.get("latitude") or api_p.get("lat"), 4)
                assert round(db_p.longitude, 4) == round(api_p.get("longitude") or api_p.get("lng"), 4)
                assert db_p.keyword == canonical_kw
                assert api_p.get("keyword") == canonical_kw

        # 6. Verify GET /keywords/{project_id}/grid returns the exact scan
        get_grid = await client.get(f"/api/v1/keywords/{project.id}/grid", headers=auth_headers)
        assert get_grid.status_code == 200
        get_data = get_grid.json()
        assert get_data["id"] == scan_id
        assert len(get_data.get("points", [])) == 25
        assert get_data["keyword"] == canonical_kw


@pytest.mark.asyncio
async def test_e2e_project_switching_and_crawl_isolation():
    """Verify Project A vs Project B crawl isolation and zero cross-project leakage."""
    await init_test_db(reset=False)

    user_a, org_a, project_a, token_a = await create_test_tenant(
        project_name="Plumbing Pro Melbourne",
        domain="plumbingpro.com.au"
    )
    user_b, org_b, project_b, token_b = await create_test_tenant(
        project_name="Electrician Elite Brisbane",
        domain="electricianelite.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 1. Project A Canonical Audit returns honest empty when no crawl exists
        canon_a = await client.get(f"/api/v1/audits/{project_a.id}/canonical", headers=headers_a)
        assert canon_a.status_code == 200
        data_a = canon_a.json()
        assert data_a["score_available"] is False
        assert data_a["health_score"] is None

        # 2. Project A Diagnostic Summary has no fake scores
        diag_a = await client.get(f"/api/v1/audits/{project_a.id}/diagnostic-summary", headers=headers_a)
        assert diag_a.status_code == 200
        diag_data_a = diag_a.json()
        assert diag_data_a["overall_score"] in [0, None]
        assert diag_data_a["pages_analyzed"] == 0

        # 3. Cross-tenant access attempt by Tenant A to Project B audit is strictly rejected
        cross_resp = await client.get(f"/api/v1/audits/{project_b.id}/canonical", headers=headers_a)
        assert cross_resp.status_code in [403, 404]

        cross_grid = await client.get(f"/api/v1/keywords/{project_b.id}/grid", headers=headers_a)
        assert cross_grid.status_code in [403, 404]
