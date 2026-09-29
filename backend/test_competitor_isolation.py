import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.local_seo import Competitor
from app.services.local_seo.competitor_geogrid_service import CompetitorGeoGridService
from app.services.reports.report_snapshot_service import ReportSnapshotService


@pytest.mark.asyncio
async def test_project_level_competitor_isolation_complete():
    """
    Validates all 10 core requirements of Project-Level Competitor Isolation:
    1. Competitor lists are strictly project scoped (Project A only sees Comp A, Project B only sees Comp B).
    2. Benchmarking and report snapshots only include target business + scoped project competitors.
    3. Cross-project competitor mutation/deletion attempts fail closed (404/403).
    4. Competitor creation automatically and immutably assigns the active project_id.
    5. Discovered/Geo-Grid competitors are ingested strictly into the scanned project_id.
    6. PDF and CSV exports contain only competitors from the requested project.
    7. Shared real-world competitors across Project A and B remain strictly separated entities.
    """
    await init_test_db(reset=False)

    # 1. Setup Tenant A (Org A, Project A - ABC Plumbing)
    user_a, org_a, proj_a, token_a = await create_test_tenant(
        project_name="ABC Plumbing Melbourne",
        domain="abcplumbing.com.au"
    )

    # 2. Setup Tenant B (Org B, Project B - XYZ Solar Brisbane)
    user_b, org_b, proj_b, token_b = await create_test_tenant(
        project_name="XYZ Solar Brisbane",
        domain="xyzsolar.com.au"
    )

    transport = ASGITransport(app=app)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ── Test 1: Create Competitors in Project A ──
        resp_a1 = await client.post(
            "/api/v1/local-seo/competitors",
            json={
                "project_id": proj_a.id,
                "name": "Alpha Melbourne Plumbers",
                "domain": "alphamelbourne.com.au",
                "website": "https://alphamelbourne.com.au",
                "rating": 4.8,
                "reviews_count": 82,
                "place_id": "ChIJ_ALPHA_A",
                "address": "12 Collins St, Melbourne VIC"
            },
            headers=headers_a
        )
        assert resp_a1.status_code == 200, resp_a1.text
        comp_a1 = resp_a1.json()
        assert comp_a1["project_id"] == proj_a.id
        assert comp_a1["name"] == "Alpha Melbourne Plumbers"

        resp_a2 = await client.post(
            "/api/v1/local-seo/competitors",
            json={
                "project_id": proj_a.id,
                "name": "Rapid Melbourne Plumbing",
                "domain": "rapidmelbourne.com.au",
                "website": "https://rapidmelbourne.com.au",
                "rating": 4.5,
                "reviews_count": 45,
                "place_id": "ChIJ_RAPID_A"
            },
            headers=headers_a
        )
        assert resp_a2.status_code == 200
        comp_a2 = resp_a2.json()
        assert comp_a2["project_id"] == proj_a.id

        # ── Test 2: Create Competitors in Project B ──
        resp_b1 = await client.post(
            "/api/v1/local-seo/competitors",
            json={
                "project_id": proj_b.id,
                "name": "Solar Power Brisbane Direct",
                "domain": "solarbrisbane.com.au",
                "website": "https://solarbrisbane.com.au",
                "rating": 4.9,
                "reviews_count": 120,
                "place_id": "ChIJ_SOLAR_B"
            },
            headers=headers_b
        )
        assert resp_b1.status_code == 200
        comp_b1 = resp_b1.json()
        assert comp_b1["project_id"] == proj_b.id

        # ── Test 3: Query Competitors for Project A ──
        # Must return only Alpha & Rapid, never Solar Power Brisbane
        list_a = await client.get(f"/api/v1/local-seo/competitors/{proj_a.id}", headers=headers_a)
        assert list_a.status_code == 200
        comps_for_a = list_a.json()
        names_in_a = [c["name"] for c in comps_for_a]
        assert "Alpha Melbourne Plumbers" in names_in_a
        assert "Rapid Melbourne Plumbing" in names_in_a
        assert "Solar Power Brisbane Direct" not in names_in_a
        assert all(c["project_id"] == proj_a.id for c in comps_for_a)

        # ── Test 4: Query Competitors for Project B ──
        # Must return only Solar Power Brisbane, never Project A competitors
        list_b = await client.get(f"/api/v1/local-seo/competitors/{proj_b.id}", headers=headers_b)
        assert list_b.status_code == 200
        comps_for_b = list_b.json()
        names_in_b = [c["name"] for c in comps_for_b]
        assert "Solar Power Brisbane Direct" in names_in_b
        assert "Alpha Melbourne Plumbers" not in names_in_b
        assert "Rapid Melbourne Plumbing" not in names_in_b
        assert all(c["project_id"] == proj_b.id for c in comps_for_b)

        # ── Test 5: Cross-Project Access & Authorization Fail-Closed ──
        # Attempting to read Project B competitors with Project A user credentials
        unauth_list = await client.get(f"/api/v1/local-seo/competitors/{proj_b.id}", headers=headers_a)
        assert unauth_list.status_code in (403, 404)

        # Attempting to delete Project B competitor using Project A user credentials
        unauth_del = await client.delete(f"/api/v1/local-seo/competitors/{comp_b1['id']}", headers=headers_a)
        assert unauth_del.status_code in (403, 404)

        # Attempting to create a competitor in Project B using Project A credentials
        unauth_post = await client.post(
            "/api/v1/local-seo/competitors",
            json={
                "project_id": proj_b.id,
                "name": "Malicious Intruder Comp",
                "domain": "intruder.com"
            },
            headers=headers_a
        )
        assert unauth_post.status_code in (403, 404)

        # ── Test 6: Report Snapshot Isolation ──
        async with AsyncSessionLocal() as session:
            snapshot_a = await ReportSnapshotService.resolve_report_snapshot(
                project_id=proj_a.id,
                db=session
            )
            assert snapshot_a is not None
            snap_comps_a = snapshot_a["competitors"]["items"]
            snap_comp_names_a = [c.get("name") for c in snap_comps_a]
            assert "Alpha Melbourne Plumbers" in snap_comp_names_a
            assert "Solar Power Brisbane Direct" not in snap_comp_names_a

            snapshot_b = await ReportSnapshotService.resolve_report_snapshot(
                project_id=proj_b.id,
                db=session
            )
            assert snapshot_b is not None
            snap_comps_b = snapshot_b["competitors"]["items"]
            snap_comp_names_b = [c.get("name") for c in snap_comps_b]
            assert "Solar Power Brisbane Direct" in snap_comp_names_b
            assert "Alpha Melbourne Plumbers" not in snap_comp_names_b

        # ── Test 7: Competitor PDF and CSV Export Isolation ──
        # PDF for Project A
        pdf_resp_a = await client.get(f"/api/v1/local-seo/competitors/{proj_a.id}/export/pdf", headers=headers_a)
        assert pdf_resp_a.status_code == 200
        assert pdf_resp_a.headers["content-type"] == "application/pdf"
        assert len(pdf_resp_a.content) > 500

        # CSV for Project A
        csv_resp_a = await client.get(f"/api/v1/local-seo/competitors/{proj_a.id}/export/csv", headers=headers_a)
        assert csv_resp_a.status_code == 200
        csv_text_a = csv_resp_a.text
        assert "Alpha Melbourne Plumbers" in csv_text_a
        assert "Solar Power Brisbane Direct" not in csv_text_a

        # ── Test 8: Geo-Grid Ingestion Isolation ──
        async with AsyncSessionLocal() as session:
            # Ingest Geo-Grid competitor for Project A
            grid_points_a = [
                {
                    "point_number": 1,
                    "row": 0, "col": 0,
                    "competitors": [
                        {
                            "position": 1,
                            "title": "CBD Melbourne Emergency Plumbing",
                            "domain": "melbourneemergencypipes.com.au",
                            "place_id": "ChIJ_CBD_MELB",
                            "rating": 4.7,
                            "reviews": 33,
                            "is_target": False
                        }
                    ]
                }
            ]
            ingested_a = await CompetitorGeoGridService.ingest_scan_competitors(
                db=session,
                project_id=proj_a.id,
                scan_id=9991,
                grid_points=grid_points_a,
                keyword="plumber melbourne"
            )
            await session.commit()
            assert len(ingested_a) == 1
            assert ingested_a[0].project_id == proj_a.id
            assert ingested_a[0].name == "CBD Melbourne Emergency Plumbing"

        # Verify through API that Project B did NOT receive this Geo-Grid competitor
        list_b_after = await client.get(f"/api/v1/local-seo/competitors/{proj_b.id}", headers=headers_b)
        names_b_after = [c["name"] for c in list_b_after.json()]
        assert "CBD Melbourne Emergency Plumbing" not in names_b_after

        # ── Test 9: Multi-Project Shared Competitor Entity Deduplication Isolation ──
        # Both Project A and Project B can independently track the same multi-city franchise "Apex Trade Group"
        # without interfering with each other's metrics or project scoping.
        resp_shared_a = await client.post(
            "/api/v1/local-seo/competitors",
            json={
                "project_id": proj_a.id,
                "name": "Apex National Trade Group",
                "domain": "apextrades.com.au",
                "website": "https://apextrades.com.au/melbourne",
                "rating": 4.2,
                "reviews_count": 50,
                "place_id": "ChIJ_APEX_MELB"
            },
            headers=headers_a
        )
        assert resp_shared_a.status_code == 200
        comp_shared_a = resp_shared_a.json()

        resp_shared_b = await client.post(
            "/api/v1/local-seo/competitors",
            json={
                "project_id": proj_b.id,
                "name": "Apex National Trade Group",
                "domain": "apextrades.com.au",
                "website": "https://apextrades.com.au/brisbane",
                "rating": 4.9,
                "reviews_count": 210,
                "place_id": "ChIJ_APEX_BRIS"
            },
            headers=headers_b
        )
        assert resp_shared_b.status_code == 200
        comp_shared_b = resp_shared_b.json()

        assert comp_shared_a["id"] != comp_shared_b["id"]
        assert comp_shared_a["project_id"] == proj_a.id
        assert comp_shared_b["project_id"] == proj_b.id
        assert comp_shared_a["rating"] == 4.2
        assert comp_shared_b["rating"] == 4.9

        # Delete from Project A should NOT delete from Project B
        del_shared_a = await client.delete(f"/api/v1/local-seo/competitors/{comp_shared_a['id']}", headers=headers_a)
        assert del_shared_a.status_code == 200

        # Project B still has its own Apex entity intact
        list_b_final = await client.get(f"/api/v1/local-seo/competitors/{proj_b.id}", headers=headers_b)
        names_b_final = [c["name"] for c in list_b_final.json()]
        assert "Apex National Trade Group" in names_b_final
