"""
LocalLift — Part 2 Product Experience & Local SEO Intelligence Integration Tests

Verifies:
1. End-to-End Product Flow: Project creation -> Business Profile -> Keyword & GeoGrid -> Local Audit -> Intelligence Summary.
2. Local Intelligence Summary API (/api/v1/projects/{id}/local-intelligence-summary): Aggregates all metrics truthfully without fake numbers.
3. Geo-Grid History & Scan Comparison: History listing and point-by-point comparison between scans.
4. Local SEO Report API (/api/v1/reports/{id}/local-seo): Comprehensive report payload assembly with 20 categories and 90-day plan.
5. Strict Multi-Tenant Security & Isolation: IDOR protection across summary, audit history, grid compare, and report endpoints.
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
from app.models.local_seo import BusinessProfile, Citation, Competitor, Review, VerificationStatus
from app.models.ranking import GeoGridScan, GeoGridPointResult, Keyword
from app.models.audit import LocalAuditRun, LocalAuditFinding
from sqlalchemy import select


@pytest.mark.asyncio
async def test_part2_full_product_experience_lifecycle():
    """Complete product verification test for Local SEO Intelligence Platform."""
    await init_test_db(reset=False)

    # 1. Setup Tenant 1 (Bondi Dental Care) and Tenant 2 (Isolation Check)
    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Bondi Dental Care",
        domain="bondidentalcare.com.au"
    )
    user2, org2, proj2, token2 = await create_test_tenant(
        project_name="Manly Surf School",
        domain="manlysurfschool.com.au"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth1 = {"Authorization": f"Bearer {token1}"}
        auth2 = {"Authorization": f"Bearer {token2}"}

        # 2. Update Business Profile with rich canonical information
        prof_payload = {
            "business_name": "Bondi Dental Care Clinic",
            "website": "https://bondidentalcare.com.au",
            "primary_phone": "+61 2 9365 7890",
            "primary_address": "120 Campbell Parade",
            "city": "Bondi Beach",
            "state": "NSW",
            "postal_code": "2026",
            "country": "Australia",
            "latitude": -33.8915,
            "longitude": 151.2767,
            "primary_category": "Dentist",
            "additional_categories": ["Cosmetic Dentist", "Emergency Dental Service"],
            "verification_status": "VERIFIED",
            "service_area": ["Bondi", "Tamarama", "Bronte", "Waverley"]
        }
        prof_resp = await client.put(
            f"/api/v1/projects/{proj1.id}/business-profile",
            json=prof_payload,
            headers=auth1
        )
        assert prof_resp.status_code == 200, prof_resp.text

        # 3. Add tracked keywords
        kw_resp = await client.post(
            f"/api/v1/keywords",
            json={"project_id": proj1.id, "keyword": "emergency dentist bondi", "target_location": "Bondi NSW"},
            headers=auth1
        )
        assert kw_resp.status_code == 200, kw_resp.text
        kw_data = kw_resp.json()
        kw_id = kw_data["id"]

        # 4. Insert historical GeoGrid scans for testing history and comparison
        async with AsyncSessionLocal() as db:
            # Baseline Scan A
            scan_a = GeoGridScan(
                project_id=proj1.id,
                keyword_id=kw_id,
                center_lat=-33.8915,
                center_lng=151.2767,
                center_name="Bondi Beach Central",
                radius_km=5.0,
                grid_size=5,
                average_rank=4.2,
                local_visibility_pct=68.0,
                total_points=25,
                completed_points=25,
                ranking_found_points=17,
                not_found_points=8,
                provider_error_points=0,
                scan_status="COMPLETED"
            )
            db.add(scan_a)
            await db.flush()

            for i in range(1, 26):
                db.add(GeoGridPointResult(
                    scan_id=scan_a.id,
                    project_id=proj1.id,
                    keyword_id=kw_id,
                    keyword="emergency dentist bondi",
                    provider="serpapi",
                    point_number=i,
                    latitude=-33.8915 + (i * 0.001),
                    longitude=151.2767 + (i * 0.001),
                    rank=3 if i <= 10 else (8 if i <= 17 else None),
                    status="RANKING_FOUND" if i <= 17 else "NOT_FOUND",
                    matched_business="Bondi Dental Care Clinic" if i <= 17 else None
                ))

            # Later Scan B (showing improvement)
            scan_b = GeoGridScan(
                project_id=proj1.id,
                keyword_id=kw_id,
                center_lat=-33.8915,
                center_lng=151.2767,
                center_name="Bondi Beach Central",
                radius_km=5.0,
                grid_size=5,
                average_rank=2.8,
                local_visibility_pct=88.0,
                total_points=25,
                completed_points=25,
                ranking_found_points=22,
                not_found_points=3,
                provider_error_points=0,
                scan_status="COMPLETED"
            )
            db.add(scan_b)
            await db.flush()

            for i in range(1, 26):
                db.add(GeoGridPointResult(
                    scan_id=scan_b.id,
                    project_id=proj1.id,
                    keyword_id=kw_id,
                    keyword="emergency dentist bondi",
                    provider="serpapi",
                    point_number=i,
                    latitude=-33.8915 + (i * 0.001),
                    longitude=151.2767 + (i * 0.001),
                    rank=2 if i <= 15 else (5 if i <= 22 else None),
                    status="RANKING_FOUND" if i <= 22 else "NOT_FOUND",
                    matched_business="Bondi Dental Care Clinic" if i <= 22 else None
                ))

            # Add reviews and citations
            db.add(Review(
                project_id=proj1.id,
                author_name="Sarah Miller",
                rating=5,
                review_text="Best dentist in Bondi, highly recommended!",
                source="Google"
            ))
            db.add(Citation(
                project_id=proj1.id,
                source_name="Yellow Pages Australia",
                domain="yellowpages.com.au",
                listing_url="https://yellowpages.com.au/bondi-dental",
                nap_status="match",
                verification_status="OBSERVED"
            ))
            db.add(Competitor(
                project_id=proj1.id,
                name="Bondi Junction Smiles",
                domain="bondijunctionsmiles.com.au",
                local_visibility_score=75,
                reviews_count=45,
                rating=4.7
            ))

            await db.commit()
            scan_a_id = scan_a.id
            scan_b_id = scan_b.id

        # 5. Run Local SEO Audit
        audit_run_resp = await client.post(f"/api/v1/audits/{proj1.id}/local/run", headers=auth1)
        assert audit_run_resp.status_code == 200, audit_run_resp.text
        audit_run = audit_run_resp.json()
        assert "overall_score" in audit_run
        assert "category_scores" in audit_run
        assert len(audit_run["findings"]) > 0

        # 6. Verify Local Intelligence Summary API
        summary_resp = await client.get(
            f"/api/v1/projects/{proj1.id}/local-intelligence-summary",
            headers=auth1
        )
        assert summary_resp.status_code == 200, summary_resp.text
        summary = summary_resp.json()
        assert summary["project_id"] == proj1.id
        assert summary["business_name"] == "Bondi Dental Care Clinic"
        assert summary["overall_score"] is not None
        assert summary["geo_visibility_pct"] == 88.0  # From latest scan B
        assert summary["total_keywords"] >= 1
        assert summary["total_reviews"] == 1
        assert summary["average_rating"] == 5.0
        assert summary["total_citations"] == 1
        assert summary["citations_matching_nap"] == 1
        assert len(summary["category_scores"]) > 0
        assert len(summary["priority_findings"]) > 0

        # 7. Verify Geo-Grid History endpoint
        history_resp = await client.get(
            f"/api/v1/keywords/{proj1.id}/grid/history",
            headers=auth1
        )
        assert history_resp.status_code == 200, history_resp.text
        hist_data = history_resp.json()
        assert len(hist_data) >= 2
        assert hist_data[0]["id"] == scan_b_id  # Latest first
        assert hist_data[0]["local_visibility_pct"] == 88.0
        assert hist_data[1]["id"] == scan_a_id
        assert hist_data[1]["local_visibility_pct"] == 68.0

        # 8. Verify Geo-Grid Compare endpoint
        compare_resp = await client.get(
            f"/api/v1/keywords/{proj1.id}/grid/compare?scan_a_id={scan_a_id}&scan_b_id={scan_b_id}",
            headers=auth1
        )
        assert compare_resp.status_code == 200, compare_resp.text
        comp_data = compare_resp.json()
        assert comp_data["scan_a_id"] == scan_a_id
        assert comp_data["scan_b_id"] == scan_b_id
        assert comp_data["visibility_pct_a"] == 68.0
        assert comp_data["visibility_pct_b"] == 88.0
        assert comp_data["visibility_delta"] == 20.0  # 88 - 68
        assert "point_comparisons" in comp_data
        assert len(comp_data["point_comparisons"]) == 25

        # 9. Verify Local SEO Report Generator endpoint
        report_resp = await client.get(
            f"/api/v1/reports/{proj1.id}/local-seo",
            headers=auth1
        )
        assert report_resp.status_code == 200, report_resp.text
        report = report_resp.json()
        assert report["project_id"] == proj1.id
        assert "Bondi Dental Care Clinic" in report["title"]
        assert report["business_profile"]["primary_category"] == "Dentist"
        assert report["audit"]["overall_score"] is not None
        assert report["geo_visibility"]["local_visibility_pct"] == 88.0
        assert report["reputation"]["total_reviews"] == 1
        assert report["citations"]["total"] == 1
        assert len(report["competitors"]) == 1
        assert "action_plan" in report
        assert "month_1" in report["action_plan"]
        assert "month_2" in report["action_plan"]
        assert "month_3" in report["action_plan"]
        assert "provenance_legend" in report

        # 10. Multi-Tenant Isolation / IDOR Security checks
        # Tenant 2 cannot view Tenant 1's summary, history, compare, or report
        t2_summary = await client.get(f"/api/v1/projects/{proj1.id}/local-intelligence-summary", headers=auth2)
        assert t2_summary.status_code in [403, 404]

        t2_history = await client.get(f"/api/v1/keywords/{proj1.id}/grid/history", headers=auth2)
        assert t2_history.status_code in [403, 404]

        t2_compare = await client.get(
            f"/api/v1/keywords/{proj1.id}/grid/compare?scan_a_id={scan_a_id}&scan_b_id={scan_b_id}",
            headers=auth2
        )
        assert t2_compare.status_code in [403, 404]

        t2_report = await client.get(f"/api/v1/reports/{proj1.id}/local-seo", headers=auth2)
        assert t2_report.status_code in [403, 404]
