import pytest
import math
from datetime import datetime, timezone, timedelta
from app.models.user import User, Organization
from app.models.project import Project
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.services.reports.geogrid_pdf_service import GeoGridPDFService


@pytest.fixture
def test_organization():
    return Organization(id=1, name="Acme Local Org", slug="acme-local")


@pytest.fixture
def test_project(test_organization):
    return Project(
        id=10,
        name="Apex Plumbing Services",
        domain="apexplumbing.com",
        organization_id=test_organization.id
    )


@pytest.fixture
def other_project():
    return Project(
        id=99,
        name="Competitor Services",
        domain="otherbiz.com",
        organization_id=2
    )


@pytest.fixture
def test_keyword(test_project):
    return Keyword(
        id=100,
        project_id=test_project.id,
        keyword="emergency drain cleaning"
    )


def create_mock_scan(project, keyword, grid_size=5, radius_km=5.0, scan_id=1, scan_status="completed", time_offset_hours=0):
    total_pts = grid_size * grid_size
    now = datetime.now(timezone.utc) - timedelta(hours=time_offset_hours)
    scan = GeoGridScan(
        id=scan_id,
        project_id=project.id,
        keyword_id=keyword.id,
        center_name="Austin Headquarters",
        center_lat=30.2672,
        center_lng=-97.7431,
        radius_km=radius_km,
        grid_size=grid_size,
        average_rank=4.2,
        local_visibility_pct=72.0,
        scan_status=scan_status,
        total_points=total_pts,
        completed_points=total_pts if scan_status == "completed" else int(total_pts * 0.6),
        ranking_found_points=int(total_pts * 0.7),
        not_found_points=int(total_pts * 0.2),
        provider_error_points=0,
        timeout_points=0,
        successful_points=total_pts,
        failed_points=0,
        scanned_at=now
    )
    scan.keyword_rel = keyword

    points = []
    for idx in range(total_pts):
        pt_num = idx + 1
        row = idx // grid_size
        col = idx % grid_size
        lat = 30.2672 + (row - grid_size // 2) * 0.015
        lng = -97.7431 + (col - grid_size // 2) * 0.015

        if pt_num % 5 == 0:
            status = "NOT_FOUND"
            rank = None
        else:
            status = "SUCCESS"
            rank = (pt_num % 8) + 1

        competitors = [
            {"title": f"Metro Flow #{i+1}", "position": i + 1, "domain": f"metroflow{i+1}.com"}
            for i in range(5)
        ]

        pt = GeoGridPointResult(
            id=1000 + idx,
            scan_id=scan.id,
            project_id=project.id,
            keyword_id=keyword.id,
            point_number=pt_num,
            row=row,
            col=col,
            latitude=lat,
            longitude=lng,
            distance_km=round(math.sqrt((row - grid_size // 2)**2 + (col - grid_size // 2)**2) * 1.2, 2),
            direction="North" if row < grid_size // 2 else "South",
            keyword=keyword.keyword,
            provider="SerpApi (Google Maps Engine)",
            status=status,
            rank=rank,
            matched_business=project.name if rank else None,
            matched_domain=project.domain if rank else None,
            ranking_url=f"https://{project.domain}/local" if rank else None,
            competitors=competitors,
            searched_at=now
        )
        points.append(pt)

    scan.point_results = points
    return scan, points


# ─── 1. TEST FULL SCAN PDF GENERATION (3x3, 5x5, 7x7) ───

def test_full_scan_pdf_3x3(test_project, test_keyword):
    scan, points = create_mock_scan(test_project, test_keyword, grid_size=3)
    assert len(points) == 9

    pdf_bytes = GeoGridPDFService.generate_single_scan_pdf(test_project, scan, points)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_full_scan_pdf_5x5(test_project, test_keyword):
    scan, points = create_mock_scan(test_project, test_keyword, grid_size=5)
    assert len(points) == 25

    pdf_bytes = GeoGridPDFService.generate_single_scan_pdf(test_project, scan, points)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 3000
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_full_scan_pdf_7x7(test_project, test_keyword):
    scan, points = create_mock_scan(test_project, test_keyword, grid_size=7)
    assert len(points) == 49

    pdf_bytes = GeoGridPDFService.generate_single_scan_pdf(test_project, scan, points)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 4000
    assert pdf_bytes.startswith(b"%PDF-1.")


# ─── 2. TEST CURRENT + PREVIOUS 2 SCANS (1, 2, 3, 10 Scans) ───

def test_multi_scan_comparison_1_scan(test_project, test_keyword):
    scan1, pts1 = create_mock_scan(test_project, test_keyword, grid_size=5, scan_id=1, time_offset_hours=0)
    scans_with_points = [(scan1, pts1)]

    pdf_bytes = GeoGridPDFService.generate_multi_scan_comparison_pdf(test_project, scans_with_points)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_multi_scan_comparison_2_scans(test_project, test_keyword):
    scan1, pts1 = create_mock_scan(test_project, test_keyword, grid_size=5, scan_id=2, time_offset_hours=0)
    scan2, pts2 = create_mock_scan(test_project, test_keyword, grid_size=5, scan_id=1, time_offset_hours=24)
    scans_with_points = [(scan1, pts1), (scan2, pts2)]

    pdf_bytes = GeoGridPDFService.generate_multi_scan_comparison_pdf(test_project, scans_with_points)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2500
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_multi_scan_comparison_3_scans(test_project, test_keyword):
    scan1, pts1 = create_mock_scan(test_project, test_keyword, grid_size=5, scan_id=3, time_offset_hours=0)
    scan2, pts2 = create_mock_scan(test_project, test_keyword, grid_size=5, scan_id=2, time_offset_hours=24)
    scan3, pts3 = create_mock_scan(test_project, test_keyword, grid_size=5, scan_id=1, time_offset_hours=48)
    scans_with_points = [(scan1, pts1), (scan2, pts2), (scan3, pts3)]

    pdf_bytes = GeoGridPDFService.generate_multi_scan_comparison_pdf(test_project, scans_with_points)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 3000
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_multi_scan_comparison_capped_at_latest_3(test_project, test_keyword):
    scans_all = []
    for i in range(10):
        scan_i, pts_i = create_mock_scan(
            test_project, test_keyword, grid_size=5, scan_id=10 - i, time_offset_hours=i * 12
        )
        scans_all.append((scan_i, pts_i))

    # Taking the latest 3
    latest_3 = scans_all[:3]
    assert len(latest_3) == 3
    assert [s[0].id for s in latest_3] == [10, 9, 8]

    pdf_bytes = GeoGridPDFService.generate_multi_scan_comparison_pdf(test_project, latest_3)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 3000
    assert pdf_bytes.startswith(b"%PDF-1.")


# ─── 3. TEST SELECTED GRID POINT PDF (Pt 1, 13, 49) ───

def test_selected_point_pdf_pt1(test_project, test_keyword):
    scan, points = create_mock_scan(test_project, test_keyword, grid_size=5)
    pt1 = next(p for p in points if p.point_number == 1)

    analysis_data = {
        "point_number": 1,
        "row": pt1.row,
        "col": pt1.col,
        "location": {
            "latitude": pt1.latitude,
            "longitude": pt1.longitude,
            "distance_km": pt1.distance_km,
            "direction": pt1.direction
        },
        "ranking": {
            "business_name": test_project.name,
            "rank": pt1.rank,
            "status": pt1.status,
            "result_depth": 20,
            "provider": "SerpApi"
        },
        "competitors_hierarchy": {
            "competitors_above": pt1.competitors[:2],
            "target_business": {"title": test_project.name, "position": pt1.rank, "domain": test_project.domain},
            "competitors_below": pt1.competitors[2:],
            "total_competitors_evaluated": 5,
            "result_depth": 20
        },
        "diagnostics": {
            "what": "High Page 1 visibility in immediate central radius.",
            "where": "0.5km North of business center.",
            "how": [{"field": "Distance Proximity", "value": "Strong", "provider_observed": True}],
            "why": ["Optimal local authority and geographic proximity in core zone."]
        }
    }

    pdf_bytes = GeoGridPDFService.generate_selected_point_pdf(test_project, scan, pt1, analysis_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_selected_point_pdf_pt13(test_project, test_keyword):
    scan, points = create_mock_scan(test_project, test_keyword, grid_size=5)
    pt13 = next(p for p in points if p.point_number == 13)

    analysis_data = {
        "point_number": 13,
        "row": pt13.row,
        "col": pt13.col,
        "location": {
            "latitude": pt13.latitude,
            "longitude": pt13.longitude,
            "distance_km": pt13.distance_km,
            "direction": pt13.direction
        },
        "ranking": {
            "business_name": test_project.name,
            "rank": pt13.rank,
            "status": pt13.status,
            "result_depth": 20,
            "provider": "SerpApi"
        },
        "competitors_hierarchy": {
            "competitors_above": [],
            "target_business": None,
            "competitors_below": pt13.competitors,
            "total_competitors_evaluated": 5,
            "result_depth": 20
        },
        "diagnostics": {
            "what": "Mid-tier local ranking.",
            "where": "2.5km East of business center.",
            "how": [],
            "why": []
        }
    }

    pdf_bytes = GeoGridPDFService.generate_selected_point_pdf(test_project, scan, pt13, analysis_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_selected_point_pdf_pt49(test_project, test_keyword):
    scan, points = create_mock_scan(test_project, test_keyword, grid_size=7)
    pt49 = next(p for p in points if p.point_number == 49)

    analysis_data = {
        "point_number": 49,
        "row": pt49.row,
        "col": pt49.col,
        "location": {
            "latitude": pt49.latitude,
            "longitude": pt49.longitude,
            "distance_km": pt49.distance_km,
            "direction": pt49.direction
        },
        "ranking": {
            "business_name": test_project.name,
            "rank": pt49.rank,
            "status": pt49.status,
            "result_depth": 50,
            "provider": "SerpApi"
        },
        "competitors_hierarchy": {
            "competitors_above": [],
            "target_business": None,
            "competitors_below": pt49.competitors,
            "total_competitors_evaluated": 5,
            "result_depth": 50
        },
        "diagnostics": {
            "what": "Outer perimeter ranking analysis.",
            "where": "Outer South-East coordinate.",
            "how": [],
            "why": []
        }
    }

    pdf_bytes = GeoGridPDFService.generate_selected_point_pdf(test_project, scan, pt49, analysis_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-1.")


# ─── 4. TEST PAGINATION ACCURACY (9, 20, 21, 40, 41, 49) ───

@pytest.mark.parametrize("total_count,page,expected_items_count,expected_total_pages", [
    (9, 1, 9, 1),
    (20, 1, 20, 1),
    (21, 1, 20, 2),
    (21, 2, 1, 2),
    (40, 1, 20, 2),
    (40, 2, 20, 2),
    (41, 1, 20, 3),
    (41, 2, 20, 3),
    (41, 3, 1, 3),
    (49, 1, 20, 3),
    (49, 2, 20, 3),
    (49, 3, 9, 3),
])
def test_pagination_logic(total_count, page, expected_items_count, expected_total_pages):
    page_size = 20
    all_scans = list(range(1, total_count + 1))

    offset = (page - 1) * page_size
    page_items = all_scans[offset:offset + page_size]
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    assert len(page_items) == expected_items_count
    assert total_pages == expected_total_pages


# ─── 5. TEST FASTAPI ENDPOINTS & MULTI-TENANT AUTHORIZATION ───

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_pdf_endpoints_and_tenant_authorization():
    await init_test_db(reset=False)

    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Phase2 Plumbing Austin",
        domain="phase2austin.com"
    )
    user2, org2, proj2, token2 = await create_test_tenant(
        project_name="Other Tenant Austin",
        domain="othertenantphase2.com"
    )

    async with AsyncSessionLocal() as db:
        kw = Keyword(
            project_id=proj1.id,
            keyword="austin plumbing repairs",
            target_location="Austin, TX",
            last_checked_at=datetime.now(timezone.utc)
        )
        db.add(kw)
        await db.flush()

        scan = GeoGridScan(
            project_id=proj1.id,
            keyword_id=kw.id,
            center_name="Austin Hub",
            center_lat=30.2672,
            center_lng=-97.7431,
            radius_km=5.0,
            grid_size=3,
            average_rank=3.5,
            local_visibility_pct=75.0,
            scan_status="completed",
            total_points=9,
            completed_points=9,
            successful_points=9,
            failed_points=0,
            ranking_found_points=7,
            not_found_points=2,
            provider_error_points=0,
            timeout_points=0,
            started_at=datetime.now(timezone.utc),
            grid_points=[]
        )
        db.add(scan)
        await db.flush()

        # Add grid point
        pt1 = GeoGridPointResult(
            scan_id=scan.id,
            project_id=proj1.id,
            keyword_id=kw.id,
            point_number=1,
            row=0,
            col=0,
            latitude=30.28,
            longitude=-97.76,
            distance_km=2.1,
            direction="NW",
            competitors=[{"position": 1, "title": "Top Austin Plumbing", "domain": "topaustin.com"}],
            keyword="austin plumbing repairs",
            provider="serpapi",
            status="RANKED",
            rank=2,
            matched_business=proj1.name,
            matched_place_id="ChIJAustin1",
            matched_domain=proj1.domain,
            ranking_url="https://google.com/maps/place/austin1",
            searched_at=datetime.now(timezone.utc)
        )
        db.add(pt1)
        await db.commit()
        scan_id = scan.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = {"Authorization": f"Bearer {token1}"}
        h2 = {"Authorization": f"Bearer {token2}"}

        # 1. Download single scan PDF (User 1 - Success)
        res1 = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/pdf", headers=h1)
        assert res1.status_code == 200
        assert res1.headers["content-type"] == "application/pdf"
        assert len(res1.content) > 1000

        # 2. Download latest scan PDF (User 1 - Success)
        res_lat = await client.get(f"/api/v1/keywords/{proj1.id}/grid/pdf/latest", headers=h1)
        assert res_lat.status_code == 200
        assert res_lat.headers["content-type"] == "application/pdf"

        # 3. Download recent scans comparison PDF (User 1 - Success)
        res_rec = await client.get(f"/api/v1/keywords/{proj1.id}/grid/pdf/recent-scans", headers=h1)
        assert res_rec.status_code == 200
        assert res_rec.headers["content-type"] == "application/pdf"

        # 4. Download selected point PDF (User 1 - Success)
        res_pt = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/1/pdf", headers=h1)
        assert res_pt.status_code == 200
        assert res_pt.headers["content-type"] == "application/pdf"

        # 5. Paginated history (User 1 - Success)
        res_hist = await client.get(f"/api/v1/keywords/{proj1.id}/grid/history?page=1&page_size=20", headers=h1)
        assert res_hist.status_code == 200
        hist_data = res_hist.json()
        assert "items" in hist_data or "records" in hist_data
        assert hist_data["total"] >= 1
        assert hist_data["page"] == 1
        assert hist_data["page_size"] == 20

        # 6. Unauthorized Project Access Check (User 2 attempting to access Proj 1's scan PDF)
        res_unauth = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/pdf", headers=h2)
        assert res_unauth.status_code in [403, 404]

        # 7. Unauthorized Point Access Check (User 2 attempting to access Proj 1's point PDF)
        res_pt_unauth = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/1/pdf", headers=h2)
        assert res_pt_unauth.status_code in [403, 404]

        # 8. Non-existent scan PDF (404)
        res_nonexistent = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/9999999/pdf", headers=h1)
        assert res_nonexistent.status_code == 404

        # 9. Non-existent point PDF (404)
        res_pt_nonexistent = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/points/999/pdf", headers=h1)
        assert res_pt_nonexistent.status_code == 404

