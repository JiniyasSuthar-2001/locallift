import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.local_seo import Competitor
from app.services.local_seo.competitor_geogrid_service import CompetitorGeoGridService


@pytest.mark.asyncio
async def test_geogrid_competitor_ingestion_and_deduplication():
    await init_test_db(reset=False)
    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Metro Plumbing Services",
        domain="metroplumbing.com"
    )

    async with AsyncSessionLocal() as session:
        # Scan 1 grid points containing duplicate competitors across points
        grid_points_scan1 = [
            {
                "point_number": 1,
                "row": 0, "col": 0,
                "lat": -27.47, "lng": 153.02,
                "competitors": [
                    {
                        "position": 1,
                        "title": "Alpha Emergency Plumbers",
                        "domain": "alphaplumbing.com.au",
                        "place_id": "ChIJ_ALPHA_123",
                        "rating": 4.9,
                        "reviews": 85,
                        "address": "100 Queen St, Brisbane",
                        "phone": "07 3333 1111",
                        "is_target": False
                    },
                    {
                        "position": 2,
                        "title": "Beta 24/7 Pipes",
                        "domain": "betapipes.com.au",
                        "place_id": "ChIJ_BETA_456",
                        "rating": 4.6,
                        "reviews": 42,
                        "address": "200 Adelaide St, Brisbane",
                        "phone": "07 3333 2222",
                        "is_target": False
                    }
                ]
            },
            {
                "point_number": 2,
                "row": 0, "col": 1,
                "lat": -27.48, "lng": 153.03,
                "competitors": [
                    # Alpha Emergency Plumbers appears again at point #2 with different rank position
                    {
                        "position": 3,
                        "title": "Alpha Emergency Plumbers",
                        "domain": "alphaplumbing.com.au",
                        "place_id": "ChIJ_ALPHA_123",
                        "rating": 4.9,
                        "reviews": 85,
                        "address": "100 Queen St, Brisbane",
                        "is_target": False
                    },
                    {
                        "position": 1,
                        "title": "Gamma Drainage Pros",
                        "domain": "gammadrainage.com.au",
                        "place_id": "ChIJ_GAMMA_789",
                        "rating": 4.8,
                        "reviews": 60,
                        "is_target": False
                    }
                ]
            }
        ]

        ingested1 = await CompetitorGeoGridService.ingest_scan_competitors(
            db=session,
            project_id=proj1.id,
            scan_id=101,
            grid_points=grid_points_scan1,
            keyword="emergency plumber brisbane"
        )

        # Expected 3 unique competitors: Alpha, Beta, Gamma (not 4)
        assert len(ingested1) == 3

        alpha = next(c for c in ingested1 if c.place_id == "ChIJ_ALPHA_123")
        assert alpha.source == "geogrid"
        assert alpha.best_rank == 1
        assert alpha.worst_rank == 3
        assert alpha.grid_appearances == 2
        assert "emergency plumber brisbane" in alpha.keywords_found
        assert len(alpha.scans_data) == 1

        # Scan 2: Run second scan with Alpha and a new competitor Delta
        grid_points_scan2 = [
            {
                "point_number": 1,
                "row": 0, "col": 0,
                "competitors": [
                    {
                        "position": 2,
                        "title": "Alpha Emergency Plumbers",
                        "domain": "alphaplumbing.com.au",
                        "place_id": "ChIJ_ALPHA_123",
                        "rating": 5.0,
                        "reviews": 90,
                        "is_target": False
                    },
                    {
                        "position": 4,
                        "title": "Delta Leak Specialists",
                        "domain": "deltaleaks.com.au",
                        "place_id": "ChIJ_DELTA_999",
                        "rating": 4.5,
                        "reviews": 20,
                        "is_target": False
                    }
                ]
            }
        ]

        ingested2 = await CompetitorGeoGridService.ingest_scan_competitors(
            db=session,
            project_id=proj1.id,
            scan_id=102,
            grid_points=grid_points_scan2,
            keyword="pipe leak repair"
        )

        # Re-query all competitors for proj1
        from sqlalchemy.future import select
        res_all = await session.execute(select(Competitor).where(Competitor.project_id == proj1.id))
        all_comps = res_all.scalars().all()

        # Total competitors should now be exactly 4: Alpha, Beta, Gamma, Delta (no duplicate Alpha)
        assert len(all_comps) == 4

        alpha_updated = next(c for c in all_comps if c.place_id == "ChIJ_ALPHA_123")
        assert alpha_updated.reviews_count == 90
        assert alpha_updated.grid_appearances == 3  # 2 in scan 1 + 1 in scan 2
        assert len(alpha_updated.keywords_found) == 2
        assert "emergency plumber brisbane" in alpha_updated.keywords_found
        assert "pipe leak repair" in alpha_updated.keywords_found
        assert len(alpha_updated.scans_data) == 2


@pytest.mark.asyncio
async def test_manual_plus_geogrid_reconciliation():
    await init_test_db(reset=False)
    user, org, proj, token = await create_test_tenant(
        project_name="Brisbane Elite Electricians",
        domain="eliteelectricians.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = {"Authorization": f"Bearer {token}"}

        # 1. User manually creates competitor
        res_manual = await client.post(
            "/api/v1/local-seo/competitors",
            headers=h,
            json={
                "project_id": proj.id,
                "name": "Apex Sparks & Power",
                "domain": "apexsparks.com.au",
                "category": "Electrician",
                "rating": 4.7
            }
        )
        assert res_manual.status_code == 200
        manual_data = res_manual.json()
        assert manual_data["source"] == "manual"
        assert manual_data["name"] == "Apex Sparks & Power"

        # 2. Geo-Grid scan discovers Apex Sparks & Power with place_id and ranks
        async with AsyncSessionLocal() as session:
            await CompetitorGeoGridService.ingest_scan_competitors(
                db=session,
                project_id=proj.id,
                scan_id=201,
                grid_points=[
                    {
                        "point_number": 1,
                        "competitors": [
                            {
                                "position": 2,
                                "title": "Apex Sparks & Power",
                                "domain": "apexsparks.com.au",
                                "place_id": "ChIJ_APEX_SPARKS",
                                "rating": 4.8,
                                "reviews": 55,
                                "is_target": False
                            }
                        ]
                    }
                ],
                keyword="electrician near me"
            )

        # 3. Retrieve competitors from API
        res_list = await client.get(f"/api/v1/local-seo/competitors/{proj.id}", headers=h)
        assert res_list.status_code == 200
        comps = res_list.json()

        # Should still be exactly 1 competitor, reconciled as manual_and_geogrid
        assert len(comps) == 1
        c = comps[0]
        assert c["name"] == "Apex Sparks & Power"
        assert c["source"] == "manual_and_geogrid"
        assert c["best_rank"] == 2
        assert c["place_id"] == "ChIJ_APEX_SPARKS"
        assert c["reviews_count"] == 55


@pytest.mark.asyncio
async def test_competitor_exports_csv_and_pdf():
    await init_test_db(reset=False)
    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Sunny Coast Furniture",
        domain="sunnycoastfurniture.com"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = {"Authorization": f"Bearer {token1}"}

        # Add 2 competitors
        await client.post(
            "/api/v1/local-seo/competitors",
            headers=h1,
            json={"project_id": proj1.id, "name": "Coastline Sofas & Beds", "domain": "coastlinesofas.com"}
        )
        await client.post(
            "/api/v1/local-seo/competitors",
            headers=h1,
            json={"project_id": proj1.id, "name": "Timber & Craft Tables", "domain": "timbercraft.com"}
        )

        # 1. Download CSV
        res_csv = await client.get(f"/api/v1/local-seo/competitors/{proj1.id}/export/csv", headers=h1)
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["content-type"]
        csv_text = res_csv.text
        assert "Business Name" in csv_text
        assert "Coastline Sofas & Beds" in csv_text
        assert "Timber & Craft Tables" in csv_text

        # 2. Download PDF
        res_pdf = await client.get(f"/api/v1/local-seo/competitors/{proj1.id}/export/pdf", headers=h1)
        assert res_pdf.status_code == 200
        assert res_pdf.headers["content-type"] == "application/pdf"
        assert len(res_pdf.content) > 1000
        # Valid PDF header
        assert res_pdf.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_competitor_search_endpoint():
    await init_test_db(reset=False)
    user, org, proj, token = await create_test_tenant(
        project_name="Sydney Dental Clinic",
        domain="sydneydental.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = {"Authorization": f"Bearer {token}"}

        res_search = await client.post(
            "/api/v1/local-seo/competitors/search",
            headers=h,
            json={
                "project_id": proj.id,
                "query": "Dentist in Sydney",
                "location": "Sydney, NSW"
            }
        )
        assert res_search.status_code == 200
        data = res_search.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "Dentist in Sydney"
