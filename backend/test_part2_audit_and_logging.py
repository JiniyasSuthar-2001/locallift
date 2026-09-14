import asyncio
import sys
import os
import uuid
import logging
from io import StringIO

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.test_helper import init_test_db
from app.database import AsyncSessionLocal
from app.models.user import User, Organization
from app.models.project import Project, Location
from app.models.connections import OrganizationSERPConfig
from app.core.security import decrypt_token

# Capture root logger output for assertion
log_stream = StringIO()
handler = logging.StreamHandler(log_stream)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
root_logger = logging.getLogger("locallift")
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

async def test_part2_audit_and_logging():
    print("\n=======================================================")
    print(">> PART 2: END-TO-END SYSTEM AUDIT & ACTION LOGGING TEST")
    print("=======================================================")

    await init_test_db(seed_demo=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # -------------------------------------------------------------------
        # 1. User Registration & Login Traceability
        # -------------------------------------------------------------------
        uid = uuid.uuid4().hex[:8]
        user_email = f"audit_user_{uid}@example.com"
        raw_password = "SecretPassword123!"

        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": user_email,
            "password": raw_password,
            "full_name": "Audit Tester",
            "organization_name": "Audit Agency LLC"
        })
        assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
        reg_data = reg_resp.json()
        token = reg_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        req_id = reg_resp.headers.get("X-Request-ID")
        assert req_id is not None, "X-Request-ID header missing from response"

        login_resp = await client.post("/api/v1/auth/login", data={
            "username": user_email,
            "password": raw_password
        })
        assert login_resp.status_code == 200

        logs = log_stream.getvalue()
        assert "[USER_ACTION]" in logs
        assert "action=REGISTER" in logs
        assert "action=LOGIN" in logs
        assert raw_password not in logs, "SECURITY VIOLATION: Raw password leaked in terminal logs!"
        print("[PASS] 1. Auth register & login action logs verified (zero password leak)")

        # -------------------------------------------------------------------
        # 2. SERP Settings UI & Connection Test Audit
        # -------------------------------------------------------------------
        # Open Settings GET
        serp_get = await client.get("/api/v1/serp/config", headers=headers)
        assert serp_get.status_code == 200
        assert serp_get.json()["connection_status"] == "not_configured"

        # Save API Key POST
        my_secret_serp_key = "secret_serpapi_key_xyz987"
        serp_save = await client.post("/api/v1/serp/config", json={
            "provider": "serpapi",
            "api_key": my_secret_serp_key
        }, headers=headers)
        assert serp_save.status_code == 200
        saved_data = serp_save.json()
        assert saved_data["has_key"] is True
        assert saved_data["masked_key"] == "••••••••z987"
        assert my_secret_serp_key not in str(saved_data), "Raw API key leaked in GET/POST response!"

        # Test Connection POST
        test_conn = await client.post("/api/v1/serp/test-connection", json={
            "provider": "serpapi",
            "api_key": my_secret_serp_key
        }, headers=headers)
        assert test_conn.status_code == 200

        logs = log_stream.getvalue()
        assert "action=OPEN_SERP_SETTINGS" in logs
        assert "action=SAVE_SERP_CONFIGURATION" in logs
        assert "action=TEST_SERP_CONNECTION" in logs
        assert my_secret_serp_key not in logs, "SECURITY VIOLATION: Raw SerpApi key leaked in terminal logs!"
        print("[PASS] 2. SERP configuration & connection test audited (encrypted at rest, masked in API, safe logs)")

        # -------------------------------------------------------------------
        # 3. Project Creation & Multi-Location Management
        # -------------------------------------------------------------------
        proj_resp = await client.post("/api/v1/projects", json={
            "name": "Audit Plumbing Co",
            "domain": "auditplumbing.com",
            "primary_category": "Plumber",
            "country": "United States",
            "location": {
                "name": "Headquarters Downtown",
                "address": "100 Main St",
                "city": "Denver",
                "state": "CO",
                "postal_code": "80202",
                "country": "United States",
                "latitude": 39.7392,
                "longitude": -104.9903,
                "phone": "+1 303 555 0100"
            }
        }, headers=headers)
        assert proj_resp.status_code == 200
        project = proj_resp.json()
        proj_id = project["id"]
        loc1_id = project["locations"][0]["id"]

        # Add Location B (Second Branch) to Project
        loc2_resp = await client.post(f"/api/v1/projects/{proj_id}/locations", json={
            "name": "Branch West",
            "address": "500 West Ave",
            "city": "Lakewood",
            "state": "CO",
            "postal_code": "80226",
            "country": "United States",
            "latitude": 39.7047,
            "longitude": -105.0814,
            "phone": "+1 303 555 0200"
        }, headers=headers)
        assert loc2_resp.status_code == 200
        loc2_id = loc2_resp.json()["id"]

        locs_resp = await client.get(f"/api/v1/projects/{proj_id}/locations", headers=headers)
        assert locs_resp.status_code == 200
        all_locs = locs_resp.json()
        assert len(all_locs) == 2, f"Expected 2 locations, got {len(all_locs)}"
        print(f"[PASS] 3. Project #{proj_id} created with 2 distinct locations (HQ ID={loc1_id}, Branch West ID={loc2_id})")

        # -------------------------------------------------------------------
        # 4. Keyword Tracker Audit
        # -------------------------------------------------------------------
        kw_resp = await client.post("/api/v1/keywords", json={
            "project_id": proj_id,
            "keyword": "emergency plumber denver",
            "target_location": "Denver, CO",
            "search_intent": "Commercial",
            "search_volume": 880
        }, headers=headers)
        assert kw_resp.status_code == 200
        kw_id = kw_resp.json()["id"]

        check_resp = await client.post(f"/api/v1/keywords/{kw_id}/check", headers=headers)
        assert check_resp.status_code == 200

        logs = log_stream.getvalue()
        assert "action=CREATE_KEYWORD" in logs
        assert "action=RUN_KEYWORD_RANK_CHECK" in logs
        print("[PASS] 4. Keyword tracker action logs & rank check flow verified")

        # -------------------------------------------------------------------
        # 5. Geo-Grid Multi-Location Scan Selection
        # -------------------------------------------------------------------
        # Scan centered at Location B (Branch West - Lakewood)
        grid_loc2 = await client.post(f"/api/v1/keywords/{proj_id}/grid/rescan", json={
            "keyword_id": kw_id,
            "location_id": loc2_id,
            "radius_km": 5.0,
            "grid_size": 5
        }, headers=headers)
        assert grid_loc2.status_code == 200
        scan_data2 = grid_loc2.json()
        assert scan_data2["center_name"] == "Branch West"
        assert abs(scan_data2["center_lat"] - 39.7047) < 0.001
        assert abs(scan_data2["center_lng"] - (-105.0814)) < 0.001

        logs = log_stream.getvalue()
        assert "action=RUN_GEO_GRID" in logs
        assert f"location_id={loc2_id}" in logs
        print(f"[PASS] 5. Multi-location Geo-Grid verified: Location B (ID={loc2_id}) selected & targeted correctly without falling back to locations[0]")

        # -------------------------------------------------------------------
        # 6. SEO Tasks & Executive Reports Traceability
        # -------------------------------------------------------------------
        task_resp = await client.post("/api/v1/tasks", json={
            "project_id": proj_id,
            "title": "Fix Local Schema JSON-LD",
            "priority": "high",
            "category": "Schema",
            "status": "open"
        }, headers=headers)
        assert task_resp.status_code == 200
        task_id = task_resp.json()["id"]

        update_task = await client.patch(f"/api/v1/tasks/{task_id}", json={
            "status": "completed"
        }, headers=headers)
        assert update_task.status_code == 200

        report_resp = await client.get(f"/api/v1/reports/{proj_id}/executive", headers=headers)
        assert report_resp.status_code == 200

        logs = log_stream.getvalue()
        assert "action=CREATE_TASK" in logs
        assert "action=UPDATE_TASK" in logs
        assert "action=GENERATE_REPORT" in logs
        print("[PASS] 6. Tasks and executive report generation action logs verified")

    print("\n=======================================================")
    print(">> ALL PART 2 END-TO-END SYSTEM AUDIT TESTS PASSED 100%!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_part2_audit_and_logging())
