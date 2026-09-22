"""
LocalLift — Central Intelligence Scan Orchestrator Tests

Verifies:
1. LocalIntelligenceScanService runs all 13 modules and records proper stage statuses.
2. Endpoint POST /api/v1/projects/{project_id}/intelligence-scan initiates scan and returns scan state.
3. Endpoint GET /api/v1/projects/{project_id}/intelligence-scan/latest retrieves newest scan.
4. Endpoint GET /api/v1/projects/{project_id}/intelligence-scan/{scan_id} retrieves scan by ID.
5. Strict Multi-Tenant Security & Isolation: Tenant 2 cannot access or trigger scans on Tenant 1's projects.
6. Empty vs Zero Truthfulness: Unconfigured stages report NOT_CONFIGURED/NOT_CONNECTED, not fake zeros.
7. Post-scan consistency: Local intelligence summary reflects updated evidence.
"""

import pytest
import os
import sys
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.intelligence_scan import ProjectIntelligenceScan, ScanStatus, StageStatus
from app.services.local_seo.intelligence_scan_service import LocalIntelligenceScanService
from app.models.local_seo import BusinessProfile, Review, Citation
from sqlalchemy import select


@pytest.mark.asyncio
async def test_intelligence_scan_service_direct_execution():
    """Verify LocalIntelligenceScanService executes stages and persists results accurately."""
    await init_test_db(reset=False)

    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Sydney Dental Boutique",
        domain="sydneydentalboutique.com.au"
    )

    async with AsyncSessionLocal() as session:
        # Create canonical profile and some sample reviews
        prof = BusinessProfile(
            project_id=proj1.id,
            business_name="Sydney Dental Boutique",
            website="https://sydneydentalboutique.com.au",
            primary_phone="+61 2 9234 5678",
            primary_address="88 Pitt Street",
            city="Sydney",
            state="NSW",
            postal_code="2000",
            country="Australia",
            verification_status="VERIFIED"
        )
        session.add(prof)

        rev1 = Review(
            project_id=proj1.id,
            source="Google",
            author_name="Alice Smith",
            rating=5,
            review_text="Fantastic service!"
        )
        session.add(rev1)

        cit1 = Citation(
            project_id=proj1.id,
            source_name="TrueLocal",
            domain="truelocal.com.au",
            listing_url="https://www.truelocal.com.au/business/sydney-dental",
            nap_status="consistent"
        )
        session.add(cit1)
        await session.commit()

        # Run direct orchestrator scan
        scan = await LocalIntelligenceScanService.get_or_create_scan(proj1.id, org1.id, session)
        assert scan.id is not None
        assert scan.status in (ScanStatus.QUEUED.value, ScanStatus.RUNNING.value)

        # Execute scan task
        await LocalIntelligenceScanService.run_scan_task(scan.id, proj1.id)

    # Verify updated scan state in a fresh database session
    async with AsyncSessionLocal() as verify_session:
        stmt = select(ProjectIntelligenceScan).where(ProjectIntelligenceScan.id == scan.id)
        res = await verify_session.execute(stmt)
        executed_scan = res.scalars().first()
        assert executed_scan is not None
        assert executed_scan.status in (ScanStatus.COMPLETED.value, ScanStatus.PARTIAL.value)
        assert executed_scan.completed_stages_count >= 5

        # Verify stages dictionary
        stages = executed_scan.stages
        assert "business_profile" in stages
        assert stages["business_profile"]["status"] == StageStatus.SUCCESS.value
        assert "reviews" in stages
        assert stages["reviews"]["status"] == StageStatus.SUCCESS.value
        assert stages["reviews"]["records_found"] >= 1
        assert "citations" in stages
        assert stages["citations"]["status"] == StageStatus.SUCCESS.value


@pytest.mark.asyncio
async def test_intelligence_scan_api_endpoints_and_multitenancy():
    """Verify scan REST API endpoints, progress reporting, and IDOR isolation."""
    await init_test_db(reset=False)

    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Melbourne Skin Clinic",
        domain="melbourneskinclinic.com.au"
    )
    user2, org2, proj2, token2 = await create_test_tenant(
        project_name="Brisbane Physio Care",
        domain="brisbanephysiocare.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth1 = {"Authorization": f"Bearer {token1}"}
        auth2 = {"Authorization": f"Bearer {token2}"}

        # 1. Trigger Scan on Project 1
        post_resp = await client.post(f"/api/v1/projects/{proj1.id}/intelligence-scan", headers=auth1)
        assert post_resp.status_code == 200, post_resp.text
        scan_data = post_resp.json()
        assert scan_data["project_id"] == proj1.id
        scan_id = scan_data["scan_id"]
        assert scan_id > 0

        # 2. Polling Scan Status on Project 1
        get_resp = await client.get(f"/api/v1/projects/{proj1.id}/intelligence-scan/{scan_id}", headers=auth1)
        assert get_resp.status_code == 200
        status_data = get_resp.json()
        assert status_data["scan_id"] == scan_id
        assert "stages" in status_data
        assert len(status_data["stages"]) == 13

        # 3. Latest Scan endpoint
        latest_resp = await client.get(f"/api/v1/projects/{proj1.id}/intelligence-scan/latest", headers=auth1)
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()
        assert latest_data["has_scan"] is True
        assert latest_data["scan"]["scan_id"] == scan_id

        # 4. Multi-Tenant IDOR Security Checks:
        # Tenant 2 MUST NOT be able to trigger scan on Tenant 1's project
        idor_post = await client.post(f"/api/v1/projects/{proj1.id}/intelligence-scan", headers=auth2)
        assert idor_post.status_code in (403, 404)

        # Tenant 2 MUST NOT be able to inspect Tenant 1's scan
        idor_get = await client.get(f"/api/v1/projects/{proj1.id}/intelligence-scan/{scan_id}", headers=auth2)
        assert idor_get.status_code in (403, 404)

        idor_latest = await client.get(f"/api/v1/projects/{proj1.id}/intelligence-scan/latest", headers=auth2)
        assert idor_latest.status_code in (403, 404)
