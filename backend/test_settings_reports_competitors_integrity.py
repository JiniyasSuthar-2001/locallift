import asyncio
import sys
import httpx
from app.main import app
from app.test_helper import init_test_db

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

async def test_settings_reports_competitors_integrity():
    # 1. Initialize test database
    await init_test_db(seed_demo=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Authenticate
        login_res = await client.post("/api/v1/auth/login", data={"username": "demo@locallift.io", "password": "password123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a brand new, fresh, un-audited project
        create_res = await client.post("/api/v1/projects", json={
            "name": "Fresh Test Project",
            "domain": "freshtestproject.com",
            "primary_category": "Electrician",
            "country": "United States"
        }, headers=headers)
        assert create_res.status_code == 200, f"Project creation failed: {create_res.text}"
        project = create_res.json()
        proj_id = project["id"]

        # -------------------------------------------------------------
        # 1. TEST SETTINGS: Update Project via PUT
        # -------------------------------------------------------------
        update_res = await client.put(f"/api/v1/projects/{proj_id}", json={
            "name": "Updated Fresh Project Name",
            "domain": "updated-domain.com",
            "primary_category": "Plumber",
            "country": "Australia"
        }, headers=headers)
        assert update_res.status_code == 200, f"Project update failed: {update_res.text}"
        updated_proj = update_res.json()
        assert updated_proj["name"] == "Updated Fresh Project Name"
        assert updated_proj["domain"] == "updated-domain.com"
        assert updated_proj["primary_category"] == "Plumber"
        assert updated_proj["country"] == "Australia"
        print("[OK] Settings project update API successfully verified and persisted")

        # -------------------------------------------------------------
        # 2. TEST COMPETITOR: Star Rating Integrity (no fake 0.0 rating)
        # -------------------------------------------------------------
        comp_res = await client.post("/api/v1/local-seo/competitors", json={
            "project_id": proj_id,
            "name": "Rival Electrical Co",
            "domain": "rivalelectrical.com"
        }, headers=headers)
        assert comp_res.status_code == 200, f"Competitor add failed: {comp_res.text}"
        comp = comp_res.json()
        assert comp["rating"] is None, f"Expected competitor rating to be None, got: {comp['rating']}"
        print("[OK] Competitor added without rating correctly preserves None instead of fake 0.0")

        # Verify competitor retrieval also returns None
        list_comps = await client.get(f"/api/v1/local-seo/competitors/{proj_id}", headers=headers)
        assert list_comps.status_code == 200
        comps_data = list_comps.json()
        assert len(comps_data) == 1
        assert comps_data[0]["rating"] is None
        print("[OK] Competitor listing honestly returns None rating for unrated competitors")

        # -------------------------------------------------------------
        # 3. TEST EXECUTIVE REPORTS: Truthfulness on Fresh Project
        # -------------------------------------------------------------
        report_res = await client.get(f"/api/v1/reports/{proj_id}/executive", headers=headers)
        assert report_res.status_code == 200
        report = report_res.json()

        # Check summary does not claim false "strong performance" with 0 keywords
        summary = report["executive_summary"]
        assert "strong performance across regional map packs" not in summary, f"Found contradictory fake text in summary: {summary}"
        assert "No local search keywords are currently configured or tracked" in summary or "No local search keywords" in summary
        assert "No optimization tasks have been completed" in summary
        print(f"[OK] Executive Summary on fresh project is truthful:\n     -> \"{summary}\"")

        # Check ratings and metrics
        metrics = report["metrics"]
        assert metrics["total_keywords"] == 0
        assert metrics["total_reviews"] == 0
        assert metrics["avg_rating"] is None, f"Expected avg_rating to be None when 0 reviews, got {metrics['avg_rating']}"
        assert metrics["completed_tasks_count"] == 0
        print("[OK] Executive Report metrics correctly report 0 keywords and None rating")

        # Check dynamic recommendations
        recs = report["next_month_recommendations"]
        assert len(recs) > 0
        # Should recommend adding keywords or crawling since project is unaudited and has no keywords
        has_relevant_rec = any("keyword" in r.lower() or "audit" in r.lower() or "review" in r.lower() for r in recs)
        assert has_relevant_rec, f"Recommendations lack context-relevance: {recs}"
        print(f"[OK] Dynamic recommendations for fresh project generated ({len(recs)} items):")
        for r in recs:
            print(f"     * {r}")

        print("\n=======================================================================")
        print(">> ALL SETTINGS, COMPETITORS & EXECUTIVE REPORT INTEGRITY CHECKS PASSED!")
        print("=======================================================================")

if __name__ == "__main__":
    asyncio.run(test_settings_reports_competitors_integrity())
