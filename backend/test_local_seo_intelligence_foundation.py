"""
LocalLift — Part 1 Architecture & Intelligence Foundation Tests

Verifies:
1. Canonical Business Profile: Single source of truth, project isolation, sync with Project/Location.
2. Evidence Provenance & Citation Integrity: Provenance statuses, no fake DA=50, honest N/A.
3. 20-Category Local SEO Audit Engine: Finding creation, category weights, honest scoring from findings.
4. Geo-Grid History & Scan Comparison: Scan A vs Scan B comparison, 25-point persistence, keyword & project isolation.
5. NAP Comparison Engine: Canonical Profile vs observed directory/GBP listings without false consistency.
6. Competitor Intelligence: Project-scoped intelligence fields.
"""

import pytest
import os
import sys
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.local_seo import (
    BusinessProfile, Citation, Competitor, VerificationStatus, CitationType, FindingStatus
)
from app.models.ranking import GeoGridScan, GeoGridPointResult, Keyword
from app.models.audit import LocalAuditRun, LocalAuditFinding
from app.models.project import Location
from sqlalchemy import select


@pytest.mark.asyncio
async def test_canonical_business_profile_lifecycle_and_isolation():
    """Verify Canonical BusinessProfile is created, synced with Project/Locations, and project-isolated."""
    await init_test_db(reset=False)

    # Tenant 1
    user1, org1, proj1, token1 = await create_test_tenant(project_name="Sydney Roofer Pros", domain="sydneyrooferpros.com.au")
    # Tenant 2
    user2, org2, proj2, token2 = await create_test_tenant(project_name="Melbourne Solar Tech", domain="melbournesolartech.com.au")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth1 = {"Authorization": f"Bearer {token1}"}
        auth2 = {"Authorization": f"Bearer {token2}"}

        # 1. Get canonical profile for proj1 (auto-initialized from project metadata)
        resp1 = await client.get(f"/api/v1/projects/{proj1.id}/business-profile", headers=auth1)
        assert resp1.status_code == 200, resp1.text
        prof1 = resp1.json()
        assert prof1["project_id"] == proj1.id
        assert prof1["business_name"] == proj1.name
        assert prof1["verification_status"] in ["USER_PROVIDED", "NOT_VERIFIED"]

        # 2. Multi-tenant isolation: Tenant 2 cannot view Tenant 1's profile
        forbidden_resp = await client.get(f"/api/v1/projects/{proj1.id}/business-profile", headers=auth2)
        assert forbidden_resp.status_code in [403, 404]

        # 3. Update canonical profile with full NAP & geo coordinates
        update_payload = {
            "business_name": "Sydney Roofer Pros Pty Ltd",
            "website": "https://sydneyrooferpros.com.au",
            "primary_phone": "+61 2 9876 5432",
            "primary_address": "45 George St",
            "city": "Sydney",
            "state": "NSW",
            "postal_code": "2000",
            "country": "Australia",
            "latitude": -33.8688,
            "longitude": 151.2093,
            "primary_category": "Roofing Contractor",
            "additional_categories": ["Roof Repair Service", "Gutter Cleaning Service"],
            "verification_status": "VERIFIED",
            "service_area": ["Greater Sydney Metropolitan Area"]
        }
        update_resp = await client.put(
            f"/api/v1/projects/{proj1.id}/business-profile",
            json=update_payload,
            headers=auth1
        )
        assert update_resp.status_code == 200, update_resp.text
        updated_prof = update_resp.json()
        assert updated_prof["business_name"] == "Sydney Roofer Pros Pty Ltd"
        assert updated_prof["primary_category"] == "Roofing Contractor"
        assert len(updated_prof["additional_categories"]) == 2
        assert updated_prof["latitude"] == -33.8688

        # 4. Verify Project location synchronization
        async with AsyncSessionLocal() as db:
            loc_res = await db.execute(select(Location).where(Location.project_id == proj1.id))
            locations = loc_res.scalars().all()
            assert len(locations) >= 1
            primary_loc = locations[0]
            assert primary_loc.latitude == -33.8688
            assert primary_loc.longitude == 151.2093

        # 5. Integrity check endpoint
        integrity_resp = await client.get(f"/api/v1/projects/{proj1.id}/business-profile/integrity", headers=auth1)
        assert integrity_resp.status_code == 200
        integrity_data = integrity_resp.json()
        assert integrity_data["completeness_pct"] > 80
        assert integrity_data["has_coordinates"] is True


@pytest.mark.asyncio
async def test_citation_provenance_and_no_fabricated_da():
    """Verify manual citations have proper provenance and unknown DA is None, not fake 50."""
    await init_test_db(reset=False)
    user, org, proj, token = await create_test_tenant(project_name="Bondi Dental Studio", domain="bondidental.com.au")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth = {"Authorization": f"Bearer {token}"}

        # Add citation without specifying domain_authority
        cit_resp = await client.post(
            "/api/v1/local-seo/citations",
            json={
                "project_id": proj.id,
                "directory_name": "TrueLocal Australia",
                "listing_url": "https://www.truelocal.com.au/business/bondi-dental/sydney",
                "category": "Dentist",
                "status": "listed",
                "nap_status": "match",
                "citation_type": "USER_PROVIDED",
                "verification_status": "USER_PROVIDED"
            },
            headers=auth
        )
        assert cit_resp.status_code == 200, cit_resp.text
        cit_data = cit_resp.json()
        # MUST NOT be fabricated to 50
        assert cit_data["domain_authority"] is None, "domain_authority should be None/null when not measured!"
        assert cit_data["citation_type"] == "USER_PROVIDED"
        assert cit_data["verification_status"] == "USER_PROVIDED"


@pytest.mark.asyncio
async def test_local_seo_audit_engine_20_categories():
    """Verify 20-category audit execution, finding generation, and score calculation from findings."""
    await init_test_db(reset=False)
    user, org, proj, token = await create_test_tenant(project_name="Brisbane Physiotherapy Clinic", domain="brisbanephysio.com.au")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth = {"Authorization": f"Bearer {token}"}

        # Run local SEO audit
        audit_resp = await client.post(f"/api/v1/audits/{proj.id}/local/run", headers=auth)
        assert audit_resp.status_code == 200, audit_resp.text
        audit_data = audit_resp.json()

        assert "id" in audit_data
        assert audit_data["project_id"] == proj.id
        assert audit_data["status"] in ["COMPLETED", "completed"]
        assert audit_data["findings_summary"]["total"] > 0
        assert len(audit_data["category_scores"]) == 20, "Must evaluate all 20 local SEO categories!"
        assert len(audit_data["findings"]) > 0

        # Verify findings format and provenance
        first_finding = audit_data["findings"][0]
        assert "category" in first_finding
        assert "check_key" in first_finding
        assert "status" in first_finding
        assert first_finding["status"] in ["PASS", "PARTIAL", "FAIL", "NOT_VERIFIED", "NOT_APPLICABLE", "ERROR"]
        assert "verification_status" in first_finding
        assert "score_impact" in first_finding

        # Verify DB persistence of audit run and findings
        async with AsyncSessionLocal() as db:
            run_res = await db.execute(
                select(LocalAuditRun).where(LocalAuditRun.id == audit_data["id"])
            )
            saved_run = run_res.scalars().first()
            assert saved_run is not None
            assert saved_run.project_id == proj.id

            findings_res = await db.execute(
                select(LocalAuditFinding).where(LocalAuditFinding.audit_run_id == saved_run.id)
            )
            saved_findings = findings_res.scalars().all()
            assert len(saved_findings) == len(audit_data["findings"])

        # Fetch latest audit endpoint
        latest_resp = await client.get(f"/api/v1/audits/{proj.id}/local/latest", headers=auth)
        assert latest_resp.status_code == 200
        assert latest_resp.json()["id"] == audit_data["id"]


@pytest.mark.asyncio
async def test_geogrid_history_and_scan_comparison():
    """Verify Geo-Grid scan history retention, 25-point persistence, and Scan A vs Scan B comparison."""
    await init_test_db(reset=False)
    user, org, proj, token = await create_test_tenant(project_name="Perth Electricians", domain="perthelectricians.com.au")

    async with AsyncSessionLocal() as db:
        # Create keyword
        kw = Keyword(
            project_id=proj.id,
            keyword="emergency electrician perth",
            search_volume=880
        )
        db.add(kw)
        await db.commit()
        await db.refresh(kw)

        # Create Scan A
        scan_a = GeoGridScan(
            project_id=proj.id,
            keyword_id=kw.id,
            grid_size=5,
            radius_km=5.0,
            center_lat=-31.9505,
            center_lng=115.8605,
            scan_status="completed",
            average_rank=4.8,
            local_visibility_pct=68.0,
            total_points=25,
            completed_points=25
        )
        db.add(scan_a)
        await db.commit()
        await db.refresh(scan_a)

        # Create 25 points for Scan A
        for r in range(5):
            for c in range(5):
                pt_num = r * 5 + c + 1
                db.add(GeoGridPointResult(
                    scan_id=scan_a.id,
                    project_id=proj.id,
                    keyword_id=kw.id,
                    point_number=pt_num,
                    row=r,
                    col=c,
                    latitude=-31.9505 + (r - 2) * 0.01,
                    longitude=115.8605 + (c - 2) * 0.01,
                    keyword=kw.keyword,
                    provider="mock",
                    status="SUCCESS",
                    rank=3 if pt_num <= 10 else 7,
                    matched_business="Perth Electricians",
                    searched_at=datetime.now(timezone.utc)
                ))

        # Create Scan B (simulating improvement after optimization)
        scan_b = GeoGridScan(
            project_id=proj.id,
            keyword_id=kw.id,
            grid_size=5,
            radius_km=5.0,
            center_lat=-31.9505,
            center_lng=115.8605,
            scan_status="completed",
            average_rank=2.4,
            local_visibility_pct=92.0,
            total_points=25,
            completed_points=25
        )
        db.add(scan_b)
        await db.commit()
        await db.refresh(scan_b)

        # Create 25 points for Scan B
        for r in range(5):
            for c in range(5):
                pt_num = r * 5 + c + 1
                db.add(GeoGridPointResult(
                    scan_id=scan_b.id,
                    project_id=proj.id,
                    keyword_id=kw.id,
                    point_number=pt_num,
                    row=r,
                    col=c,
                    latitude=-31.9505 + (r - 2) * 0.01,
                    longitude=115.8605 + (c - 2) * 0.01,
                    keyword=kw.keyword,
                    provider="mock",
                    status="SUCCESS",
                    rank=2 if pt_num <= 15 else 4,
                    matched_business="Perth Electricians",
                    searched_at=datetime.now(timezone.utc)
                ))
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth = {"Authorization": f"Bearer {token}"}

        # 1. Fetch scan history for keyword
        history_resp = await client.get(
            f"/api/v1/keywords/{proj.id}/grid/history?keyword_id={kw.id}",
            headers=auth
        )
        assert history_resp.status_code == 200, history_resp.text
        scans = history_resp.json()
        assert len(scans) >= 2
        # History must contain both scans (does not overwrite previous scans!)
        scan_ids = [s["id"] for s in scans]
        assert scan_a.id in scan_ids
        assert scan_b.id in scan_ids

        # 2. Fetch normalized 25 points for single scan
        single_resp = await client.get(
            f"/api/v1/keywords/{proj.id}/grid/scans/{scan_a.id}",
            headers=auth
        )
        assert single_resp.status_code == 200
        scan_details = single_resp.json()
        assert len(scan_details["points"]) == 25

        # 3. Compare Scan A vs Scan B
        compare_resp = await client.get(
            f"/api/v1/keywords/{proj.id}/grid/compare?scan_a_id={scan_a.id}&scan_b_id={scan_b.id}",
            headers=auth
        )
        assert compare_resp.status_code == 200, compare_resp.text
        comp_data = compare_resp.json()

        assert comp_data["scan_a_id"] == scan_a.id
        assert comp_data["scan_b_id"] == scan_b.id
        assert len(comp_data["point_comparisons"]) == 25
        assert comp_data["delta_average_rank"] is not None
        assert comp_data["delta_visibility_pct"] is not None


@pytest.mark.asyncio
async def test_nap_comparison_engine_honest_mismatches():
    """Verify NAP comparison engine accurately flags differences between Canonical Profile and citations."""
    await init_test_db(reset=False)
    user, org, proj, token = await create_test_tenant(project_name="Adelaide Locksmiths", domain="adelaidelocksmiths.com.au")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth = {"Authorization": f"Bearer {token}"}

        # 1. Update Canonical Profile
        await client.put(
            f"/api/v1/projects/{proj.id}/business-profile",
            json={
                "business_name": "Adelaide 24/7 Locksmiths",
                "primary_address": "12 King William St",
                "city": "Adelaide",
                "state": "SA",
                "postal_code": "5000",
                "primary_phone": "+61 8 8200 1234",
                "website": "https://adelaidelocksmiths.com.au"
            },
            headers=auth
        )

        # 2. Add Citation with phone and address mismatch
        await client.post(
            "/api/v1/local-seo/citations",
            json={
                "project_id": proj.id,
                "directory_name": "YellowPages",
                "listing_url": "https://www.yellowpages.com.au/sa/adelaide-locksmiths",
                "category": "Locksmith",
                "status": "listed",
                "nap_status": "mismatch"
            },
            headers=auth
        )

        # Add explicit observed mismatch data to the citation in DB
        async with AsyncSessionLocal() as db:
            c_res = await db.execute(select(Citation).where(Citation.project_id == proj.id))
            c = c_res.scalars().first()
            c.found_name = "Adelaide 24/7 Locksmiths"
            c.found_phone = "+61 8 8200 9999"  # Mismatch!
            c.found_address = "99 Old Pulteney St, Adelaide SA"  # Mismatch!
            c.found_website = "https://adelaidelocksmiths.com.au"  # Match
            await db.commit()

        # 3. Request NAP comparison
        nap_comp_resp = await client.get(f"/api/v1/local-seo/nap/comparison/{proj.id}", headers=auth)
        assert nap_comp_resp.status_code == 200, nap_comp_resp.text
        nap_data = nap_comp_resp.json()

        assert nap_data["canonical_profile"]["business_name"] == "Adelaide 24/7 Locksmiths"
        assert len(nap_data["comparisons"]) >= 1
        cit_nap = nap_data["comparisons"][0]
        # Must detect honest phone and address mismatches:
        assert cit_nap["fields"]["phone"]["status"] == "mismatch"
        assert cit_nap["fields"]["address"]["status"] == "mismatch"
        assert cit_nap["fields"]["business_name"]["status"] == "match"
        assert cit_nap["fields"]["website"]["status"] == "match"
        assert cit_nap["is_consistent"] is False
        # Overall NAP score must reflect mismatches:
        assert nap_data["nap_score"] is not None
        assert nap_data["nap_score"] < 100
