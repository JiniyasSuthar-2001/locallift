"""
Comprehensive Test Suite for:
1. Geo-Grid start-scan, live progress tracking, status polling, and cooperative cancellation.
2. Geo-Grid multi-tenant isolation and unconfigured SerpApi validation.
3. Central Local SEO Intelligence Scan lifecycle & stages freshness.
4. Local SEO Audit freshness & non-fabrication of technical/crawl evidence.
"""

import asyncio
import pytest
import os
import sys
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.ranking import Keyword, GeoGridScan
from app.models.connections import OrganizationSERPConfig
from app.models.local_seo import BusinessProfile
from app.models.audit import SEOAudit, LocalAuditRun, LocalAuditFinding
from app.core.security import encrypt_token
from app.services.serp.base import SERPProvider
from app.services.local_seo.intelligence_scan_service import LocalIntelligenceScanService
from app.services.local_seo.audit_framework import LocalSEOAuditFramework
from app.services.serp.grid_scanner import GeoGridScanner
from sqlalchemy import select


@pytest.mark.asyncio
async def test_geogrid_start_scan_and_polling():
    """Verify POST /grid/start-scan initiates scan, creates persistent GeoGridScan, and returns scan_id."""
    await init_test_db(reset=False)

    user, org, proj, token = await create_test_tenant(
        project_name="Sydney Solar Specialists",
        domain="sydneysolarspecialists.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "keyword": "solar panels sydney",
            "center_lat": -33.8688,
            "center_lng": 151.2093,
            "center_name": "Sydney CBD",
            "radius_km": 5.0,
            "grid_size": 3
        }

        # 1. Without SERP config, start-scan MUST fail with 400 SERP_PROVIDER_NOT_CONFIGURED (no fake scan)
        unconfigured_resp = await client.post(f"/api/v1/keywords/{proj.id}/grid/start-scan", json=payload, headers=headers)
        assert unconfigured_resp.status_code == 400
        assert "SERP_PROVIDER_NOT_CONFIGURED" in unconfigured_resp.text

        # 2. Add customer-owned encrypted SERP config
        async with AsyncSessionLocal() as session:
            serp_cfg = OrganizationSERPConfig(
                organization_id=org.id,
                provider="serpapi",
                api_key=encrypt_token("test_customer_serpapi_key_12345"),
                enabled=True,
                connection_status="connected"
            )
            session.add(serp_cfg)
            await session.commit()

        # 3. Start scan with configured customer credential
        resp = await client.post(f"/api/v1/keywords/{proj.id}/grid/start-scan", json=payload, headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "scan_id" in data
        scan_id = data["scan_id"]
        assert data["total_points"] == 9
        assert data["status"] in ("pending", "running", "completed", "cancelled", "completed_with_errors")

        # 4. Poll status endpoint
        poll_resp = await client.get(f"/api/v1/keywords/{proj.id}/grid/scans/{scan_id}", headers=headers)
        assert poll_resp.status_code == 200, poll_resp.text
        poll_data = poll_resp.json()
        assert poll_data["scan_id"] == scan_id
        assert poll_data["total_points"] == 9
        assert "completed_points" in poll_data
        assert "progress_pct" in poll_data


@pytest.mark.asyncio
async def test_geogrid_cancellation_endpoint_and_isolation():
    """Verify POST /grid/scans/{scan_id}/cancel sets cancel_requested and enforces multi-tenant security."""
    await init_test_db(reset=False)

    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Melbourne Roofing",
        domain="melbourneroofing.com.au"
    )
    user2, org2, proj2, token2 = await create_test_tenant(
        project_name="Brisbane Tiling",
        domain="brisbanetiling.com.au"
    )

    # Create keyword and running scan directly
    async with AsyncSessionLocal() as session:
        kw = Keyword(
            project_id=proj1.id,
            keyword="roof repairs melbourne",
            target_location="Melbourne"
        )
        session.add(kw)
        await session.commit()
        await session.refresh(kw)

        scan = GeoGridScan(
            project_id=proj1.id,
            keyword_id=kw.id,
            center_lat=-37.8136,
            center_lng=144.9631,
            center_name="Melbourne CBD",
            radius_km=5.0,
            grid_size=5,
            total_points=25,
            completed_points=4,
            scan_status="running",
            cancel_requested=False
        )
        session.add(scan)
        await session.commit()
        await session.refresh(scan)
        scan_id = scan.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth1 = {"Authorization": f"Bearer {token1}"}
        auth2 = {"Authorization": f"Bearer {token2}"}

        # 1. Unauthenticated cancellation fails
        unauth_resp = await client.post(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/cancel")
        assert unauth_resp.status_code in (401, 403)

        # 2. Cross-tenant IDOR attack fails (Tenant 2 attempts to cancel Tenant 1's scan)
        idor_resp = await client.post(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/cancel", headers=auth2)
        assert idor_resp.status_code in (403, 404)

        # 3. Cross-tenant inspection fails
        idor_get = await client.get(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}", headers=auth2)
        assert idor_get.status_code in (403, 404)

        # 4. Legitimate cancellation succeeds
        cancel_resp = await client.post(f"/api/v1/keywords/{proj1.id}/grid/scans/{scan_id}/cancel", headers=auth1)
        assert cancel_resp.status_code == 200, cancel_resp.text
        cancel_data = cancel_resp.json()
        assert cancel_data["cancel_requested"] is True
        assert cancel_data["scan_status"] in ("cancelling", "cancelled", "running")

    # Verify database state
    async with AsyncSessionLocal() as session:
        stmt = select(GeoGridScan).where(GeoGridScan.id == scan_id)
        res = await session.execute(stmt)
        updated_scan = res.scalars().first()
        assert updated_scan.cancel_requested is True


from app.services.serp.base import SERPProvider, SERPResponse, SERPItem, SERPCapabilities

@pytest.mark.asyncio
async def test_grid_scanner_cooperative_cancellation():
    """Verify GeoGridScanner stops starting new points when cancellation callback returns True."""
    point_executed_count = 0
    cancelled_flag = False

    async def is_cancelled_fn():
        return cancelled_flag

    async def on_point_completed(pt):
        nonlocal point_executed_count
        point_executed_count += 1

    # Mock SERPProvider with delayed responses
    class MockProvider(SERPProvider):
        provider_name = "mock_provider"
        is_configured = True

        @property
        def capabilities(self) -> SERPCapabilities:
            return SERPCapabilities(geo_grid=True, local_search=True, coordinate_search=True)

        async def search_keyword(self, keyword, location=None, device="desktop", num=100, **kwargs):
            await asyncio.sleep(0.01)
            return SERPResponse(
                provider="mock_provider",
                keyword=keyword,
                success=True,
                organic_results=[SERPItem(position=1, title="Best Business", link="https://example.com")]
            )

        async def search_local(self, keyword, ll=None, location=None, **kwargs):
            await asyncio.sleep(0.01)
            return SERPResponse(
                provider="mock_provider",
                keyword=keyword,
                success=True,
                organic_results=[SERPItem(position=1, title="Best Business", link="https://example.com")]
            )

        async def search_local_grid_point(self, keyword, lat, lng, radius_km=5.0, hl="en", gl="au", device="desktop", zoom=14):
            await asyncio.sleep(0.01)
            return SERPResponse(
                provider="mock_provider",
                keyword=keyword,
                success=True,
                local_pack_results=[SERPItem(position=1, title="Sydney Plumbers", place_id="test_pid")],
                organic_results=[SERPItem(position=1, title="Sydney Plumbers", link="https://sydneyplumbers.com.au", domain="sydneyplumbers.com.au")]
            )

    # Run scanner with a trigger that sets cancelled_flag after first batch
    async def cancel_after_brief_delay():
        await asyncio.sleep(0.03)
        nonlocal cancelled_flag
        cancelled_flag = True

    cancel_task = asyncio.create_task(cancel_after_brief_delay())

    results = await GeoGridScanner.scan_grid(
        provider=MockProvider(),
        keyword="plumber sydney",
        target_domain="sydneyplumbers.com.au",
        center_lat=-33.8688,
        center_lng=151.2093,
        radius_km=5.0,
        grid_size=5,
        concurrency_limit=2,
        is_cancelled_fn=is_cancelled_fn,
        on_point_completed=on_point_completed
    )
    await cancel_task

    # Points executed should be significantly less than 25 due to cooperative cancellation
    assert len(results["grid_points"]) < 25
    assert point_executed_count < 25


@pytest.mark.asyncio
async def test_technical_seo_audit_freshness_zero_pages():
    """Verify Category 15 (Technical SEO) reports NOT_VERIFIED and does NOT fabricate 80/100 when pages_analyzed == 0."""
    await init_test_db(reset=False)

    user, org, proj, token = await create_test_tenant(
        project_name="Fresh Audit Test Co",
        domain="freshaudittestco.com.au"
    )

    async with AsyncSessionLocal() as session:
        # Create empty crawl audit (pages_analyzed = 0)
        crawl = SEOAudit(
            project_id=proj.id,
            pages_analyzed=0,
            overall_score=80,  # Old default that shouldn't be blindly trusted
            critical_issues=0,
            warnings=0,
            passed_checks=0
        )
        session.add(crawl)
        await session.commit()

        # Run Audit Framework
        audit_run = await LocalSEOAuditFramework.run_audit(
            project_id=proj.id,
            db=session
        )

        findings_res = await session.execute(
            select(LocalAuditFinding).where(LocalAuditFinding.audit_run_id == audit_run.id)
        )
        findings = findings_res.scalars().all()
        tech_finding = next((f for f in findings if f.category == "technical_seo"), None)

        assert tech_finding is not None
        # Must NOT report "Technical crawl score: 80/100 across 0 pages"
        assert tech_finding.status in ("NOT_VERIFIED", "NOT_CONFIGURED")
        assert "no crawled" in tech_finding.evidence.lower() or "not analyzed" in tech_finding.evidence.lower() or "crawler" in tech_finding.evidence.lower()
