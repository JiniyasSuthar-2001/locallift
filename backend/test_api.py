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

async def test_all_apis():
    # Initialize DB tables and seed demo data matching test requirements
    await init_test_db(seed_demo=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Health / Root
        r = await client.get("/")
        assert r.status_code == 200, f"Root failed: {r.text}"
        print("[OK] Root endpoint working:", r.json())

        # 2. Login
        login_res = await client.post("/api/v1/auth/login", data={"username": "demo@locallift.io", "password": "password123"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[OK] Authentication & JWT generation working")

        # 3. Current User
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        print("[OK] User profile:", me_res.json()["email"], "| Role:", me_res.json()["role"])

        # 4. List Projects
        p_res = await client.get("/api/v1/projects", headers=headers)
        assert p_res.status_code == 200
        projects = p_res.json()
        assert len(projects) > 0
        # Select the seeded Queenshine Electricals project or first project with issues
        seeded_proj = next((p for p in projects if p.get("name") == "Queenshine Electricals"), projects[0])
        proj_id = seeded_proj["id"]
        print(f"[OK] Projects listed: Found {len(projects)} projects. Selected: {seeded_proj['name']} (ID: {proj_id})")

        # 5. Dashboard Summary
        d_res = await client.get(f"/api/v1/projects/{proj_id}/dashboard", headers=headers)
        assert d_res.status_code == 200
        dash = d_res.json()
        print(f"[OK] Dashboard Health Score: {dash['health_score']}/100 | Open Issues: {dash['counts']['open_issues']}")

        # 6. SEO Issues & Tasks
        issues_res = await client.get(f"/api/v1/audits/{proj_id}/issues", headers=headers)
        assert issues_res.status_code == 200
        issues = issues_res.json()
        print(f"[OK] SEO Issues count: {len(issues)} | First issue: {issues[0]['title']}")

        tasks_res = await client.get(f"/api/v1/tasks/{proj_id}", headers=headers)
        assert tasks_res.status_code == 200
        tasks = tasks_res.json()
        print(f"[OK] SEO Tasks count: {len(tasks)} | First task: {tasks[0]['title']}")

        # 7. Convert Issue to Task
        if issues:
            conv_res = await client.post(f"/api/v1/tasks/convert-issue/{issues[0]['id']}", json={"priority": "high"}, headers=headers)
            assert conv_res.status_code == 200
            print("[OK] Problem -> Solution -> Task Conversion pipeline verified")

        # 7b. Audit Diagnostic Summary (Citations NAP Discrepancy Matrix)
        diag_res = await client.get(f"/api/v1/audits/diagnostic-summary/{proj_id}", headers=headers)
        assert diag_res.status_code == 200
        diag_data = diag_res.json()
        assert "discrepancy_matrix" in diag_data
        print(f"[OK] Audit Diagnostic Summary verified (Pillars: {list(diag_data['pillar_scores'].keys())})")

        # 8. Keywords & GeoGrid
        kw_res = await client.get(f"/api/v1/keywords/{proj_id}", headers=headers)
        assert kw_res.status_code == 200
        kws = kw_res.json()
        print(f"[OK] Tracked Keywords count: {len(kws)} | Top keyword: {kws[0]['keyword']} (Rank #{kws[0]['current_rank']})")

        grid_res = await client.get(f"/api/v1/keywords/grid-scan/{proj_id}/latest", headers=headers)
        assert grid_res.status_code == 200
        grid = grid_res.json()
        print(f"[OK] 5x5 GeoGrid Scan: Local Visibility {grid['local_visibility_pct']}% | Avg Rank: {grid['average_rank']}")

        # 9. Local SEO (Reviews, Citations, NAP)
        rev_res = await client.get(f"/api/v1/local-seo/reviews/{proj_id}", headers=headers)
        assert rev_res.status_code == 200
        revs = rev_res.json()
        print(f"[OK] Reviews count: {len(revs)} | Sentiment: {revs[0]['sentiment']}")

        # Test Draft Response
        if revs:
            draft_res = await client.post("/api/v1/local-seo/reviews/draft-response", json={"review_id": revs[0]["id"]}, headers=headers)
            assert draft_res.status_code in (200, 400), f"Unexpected draft response status: {draft_res.text}"
            if draft_res.status_code == 200:
                print("[OK] AI Review Response drafting verified")
            else:
                print(f"[OK] AI Review Response returned honest unconfigured response (HTTP {draft_res.status_code})")

        cit_res = await client.get(f"/api/v1/local-seo/citations/{proj_id}", headers=headers)
        assert cit_res.status_code == 200
        print(f"[OK] Citations tracked: {len(cit_res.json())}")

        nap_res = await client.get(f"/api/v1/local-seo/nap/{proj_id}", headers=headers)
        assert nap_res.status_code == 200
        print(f"[OK] NAP Consistency Score: {nap_res.json()['nap_score']}%")

        # 10. AI Diagnostic Chat
        ai_res = await client.post("/api/v1/ai/diagnostic", json={"project_id": proj_id, "query": "Why did my ranking drop?"}, headers=headers)
        assert ai_res.status_code in (200, 400), f"Unexpected AI diagnostic status: {ai_res.text}"
        if ai_res.status_code == 200:
            ai_data = ai_res.json()
            print(f"[OK] AI Diagnostic Assistant: {len(ai_data.get('likely_causes', []))} causes identified")
        else:
            print(f"[OK] AI Diagnostic Assistant returned honest unconfigured response (HTTP {ai_res.status_code})")

        # 11. Executive Report
        rep_res = await client.get(f"/api/v1/reports/{proj_id}/executive", headers=headers)
        assert rep_res.status_code == 200
        print("[OK] Executive Report generation verified")

        print("\n=======================================================")
        print(">> ALL 11 BACKEND CORE MODULES & APIS PASSED VALIDATION!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_all_apis())
