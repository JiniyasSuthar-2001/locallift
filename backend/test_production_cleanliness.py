"""
LocalLift — Production Cleanliness & Demo-Data Isolation Test Suite

Validates that:
1. A fresh user registration starts with 0 projects and 0 fake data.
2. A newly created project contains 0 fake scores, 0 fake keywords, 0 fake reviews, 0 fake citations, and 0 fake GBP records.
3. Dashboard summaries, diagnostic summaries, and reports return honest zeros/empty states without fake fallback numbers.
4. Seeder execution is strictly blocked in production mode.
5. Mock SERP provider initialization is strictly blocked in production mode.
"""

import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.services.seeder import seed_initial_demo_data
from app.services.serp.factory import get_serp_provider

async def test_production_cleanliness():
    print("\n=======================================================")
    print(">> TEST 1: ENVIRONMENT GUARDS (SEEDER & MOCK PROVIDER)")
    print("=======================================================")

    # 1. Test Seeder Guard in Production
    original_env = settings.ENVIRONMENT
    original_allow_seed = settings.ALLOW_DEV_SEEDING

    try:
        settings.ENVIRONMENT = "production"
        settings.ALLOW_DEV_SEEDING = False

        blocked = False
        try:
            await seed_initial_demo_data(force=False)
        except RuntimeError as e:
            blocked = True
            print(f"[OK] Seeder correctly blocked in production: {e}")

        assert blocked, "Seeder failed to block execution in production mode!"

        # 2. Test Mock SERP Provider Guard in Production
        mock_blocked = False
        try:
            get_serp_provider("mock")
        except RuntimeError as e:
            mock_blocked = True
            print(f"[OK] Mock SERP Provider correctly blocked in production: {e}")

        assert mock_blocked, "Mock SERP Provider failed to block in production mode!"

    finally:
        settings.ENVIRONMENT = original_env
        settings.ALLOW_DEV_SEEDING = original_allow_seed

    print("\n=======================================================")
    print(">> TEST 2: FRESH ACCOUNT ZERO-DATA ISOLATION")
    print("=======================================================")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_id = uuid.uuid4().hex[:8]
        user_email = f"fresh_client_{unique_id}@production-domain.com"

        # Register fresh user
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Dr. Sarah Jenkins",
            "organization_name": "Metro Healthcare Group"
        })
        assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
        auth_data = reg_res.json()
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[OK] Registered clean user: {user_email}")

        # List projects: MUST be empty (0 automatic demo projects)
        proj_list_res = await client.get("/api/v1/projects", headers=headers)
        assert proj_list_res.status_code == 200
        projects = proj_list_res.json()
        assert len(projects) == 0, f"Fresh user should have 0 projects, found {len(projects)}"
        print("[OK] Fresh account has 0 projects (no automatic demo projects created)")

        # Create a real project
        create_res = await client.post("/api/v1/projects", json={
            "name": "Metro Dental Clinic",
            "domain": "metrodentalclinic.com.au",
            "primary_category": "Dentist",
            "country": "Australia",
            "location": {
                "name": "Brisbane Clinic",
                "address": "50 Ann Street",
                "city": "Brisbane",
                "state": "QLD",
                "postal_code": "4000",
                "country": "Australia",
                "phone": "+61 7 3000 1111"
            }
        }, headers=headers)
        assert create_res.status_code == 200
        new_proj = create_res.json()
        proj_id = new_proj["id"]
        assert new_proj["health_score"] == 0, f"Expected initial health_score 0, got {new_proj['health_score']}"
        print(f"[OK] Created real project #{proj_id}: {new_proj['name']} with initial score 0")

        # Check Dashboard Summary for new project
        dash_res = await client.get(f"/api/v1/projects/{proj_id}/dashboard", headers=headers)
        assert dash_res.status_code == 200
        dash = dash_res.json()
        assert dash["health_score"] == 0
        assert dash["counts"]["open_issues"] == 0
        assert dash["counts"]["active_tasks"] == 0
        assert dash["counts"]["tracked_keywords"] == 0
        assert dash["counts"]["reviews_total"] == 0
        assert dash["gbp_summary"]["connected"] is False
        assert dash["gsc_summary"]["clicks"] == 0
        assert dash["gsc_summary"]["impressions"] == 0
        print("[OK] Project Dashboard Summary returns honest zero-state metrics (no fake fallbacks)")

        # Check Diagnostic Summary
        diag_res = await client.get(f"/api/v1/audits/diagnostic-summary/{proj_id}", headers=headers)
        assert diag_res.status_code == 200
        diag = diag_res.json()
        assert diag["overall_score"] == 0
        assert diag["gbp_status"]["connected"] is False
        assert diag["citations_status"]["total"] == 0
        assert diag["reviews_status"]["total"] == 0
        assert diag["issues"] == []
        print("[OK] Audit Diagnostic Summary returns clean zero-state (no fake pillar scores)")

        # Check Executive Report
        rep_res = await client.get(f"/api/v1/reports/{proj_id}/executive", headers=headers)
        assert rep_res.status_code == 200
        rep = rep_res.json()
        assert rep["metrics"]["total_keywords"] == 0
        assert rep["metrics"]["total_reviews"] == 0
        assert rep["metrics"]["avg_rating"] == 0.0
        assert rep["metrics"]["nap_consistency_score"] == 0
        print("[OK] Executive Report returns 0.0 avg rating and 0 NAP score when no data exists")

        # Check GSC & GA4 routes
        gsc_res = await client.get(f"/api/v1/google/gsc/{proj_id}", headers=headers)
        assert gsc_res.status_code == 200
        gsc = gsc_res.json()
        assert gsc["connected"] is False
        assert gsc["total_clicks"] == 0

        ga4_res = await client.get(f"/api/v1/google/ga4/{proj_id}", headers=headers)
        assert ga4_res.status_code == 200
        ga4 = ga4_res.json()
        assert ga4["connected"] is False
        assert ga4["total_users"] == 0
        print("[OK] Google Search Console and GA4 endpoints return honest unintegrated empty state")

        # Check Keywords List
        kw_res = await client.get(f"/api/v1/keywords/{proj_id}", headers=headers)
        assert kw_res.status_code == 200
        assert kw_res.json() == []

        # Check Reviews List
        rev_res = await client.get(f"/api/v1/local-seo/reviews/{proj_id}", headers=headers)
        assert rev_res.status_code == 200
        assert rev_res.json() == []

        # Check Citations List
        cit_res = await client.get(f"/api/v1/local-seo/citations/{proj_id}", headers=headers)
        assert cit_res.status_code == 200
        assert cit_res.json() == []

        # Add a real user citation
        add_cit_res = await client.post("/api/v1/local-seo/citations", json={
            "project_id": proj_id,
            "directory_name": "TrueLocal",
            "listing_url": "https://www.truelocal.com.au/business/metro-dental",
            "nap_status": "match",
            "domain_authority": 65
        }, headers=headers)
        assert add_cit_res.status_code == 200
        cit_out = add_cit_res.json()
        assert cit_out["source_name"] == "TrueLocal"
        print("[OK] Real user citation tracking verified")

        print("\n=======================================================")
        print(">> ALL PRODUCTION CLEANLINESS VALIDATIONS PASSED 100%!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_production_cleanliness())
