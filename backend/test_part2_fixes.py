"""
Part 2 Verification Test Suite for LocalLift
Tests all 11 requirements in Part 2 Acceptance Table:
1. Save valid coordinates
2. Reload coordinates
3. Scan Geo-Grid
4. Change location
5. Invalid latitude
6. Invalid longitude
7. Missing coordinates
8. SerpApi test
9. Invalid SerpApi key
10. Login
11. Existing ranking workflow
"""

import asyncio

import sys
import os
import uuid

from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import AsyncSessionLocal
from app.models.project import Project, Location
from app.models.connections import OrganizationSERPConfig

async def test_part2_full_suite():
    print("=======================================================")
    print(">> STARTING PART 2 END-TO-END VERIFICATION SUITE")
    print("=======================================================")

    results = {}
    uid = uuid.uuid4().hex[:6]
    email = f"part2_tester_{uid}@example.com"
    password = "Password123!"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register & Login Test (Test 10)
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "Part 2 Tester",
            "organization_name": "Part 2 Agency"
        })
        login_res = await client.post("/api/v1/auth/login", data={
            "username": email,
            "password": password
        })
        results["Login"] = "PASS" if login_res.status_code == 200 and "access_token" in login_res.json() else "FAIL"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. SerpApi Configuration & Connection Tests (Tests 8 & 9)
        # Test 9: Invalid SerpApi key test
        invalid_key_res = await client.post("/api/v1/serp/config", json={
            "api_key": "invalid_serp_key_9999"
        }, headers=headers)
        test_conn_invalid = await client.post("/api/v1/serp/test-connection", headers=headers)
        conn_res_data = test_conn_invalid.json()
        print(f"DEBUG Invalid SerpApi Key Test: status_code={test_conn_invalid.status_code}, data={conn_res_data}")
        results["Invalid SerpApi key"] = "PASS" if test_conn_invalid.status_code == 200 and conn_res_data.get("status") in ("invalid_key", "error", "failed") and not conn_res_data.get("success") else "FAIL"

        # Test 8: Save valid key format & check masked output
        valid_key_res = await client.post("/api/v1/serp/config", json={
            "api_key": "valid_serpapi_test_key_1234567890abcdef"
        }, headers=headers)
        serp_config = await client.get("/api/v1/serp/config", headers=headers)
        results["SerpApi test"] = "PASS" if serp_config.status_code == 200 and serp_config.json()["has_key"] and "api_key" not in serp_config.json() else "FAIL"

        # 3. Create Project with Location A & Location B (Multi-location test setup)
        proj_res = await client.post("/api/v1/projects", json={
            "name": "Part 2 Plumbing Co",
            "domain": "part2plumbing.com",
            "primary_category": "Plumber",
            "location": {
                "name": "Location A (HQ)",
                "address": "100 Main St",
                "city": "Denver",
                "state": "CO",
                "country": "United States",
                "latitude": 39.7392,
                "longitude": -104.9903
            }
        }, headers=headers)
        proj_data = proj_res.json()
        proj_id = proj_data["id"]
        loc_a_id = proj_data["locations"][0]["id"]

        # Create Location B
        loc_b_res = await client.post(f"/api/v1/projects/{proj_id}/locations", json={
            "name": "Location B (West Branch)",
            "address": "500 West Ave",
            "city": "Lakewood",
            "state": "CO",
            "country": "United States",
            "latitude": 39.7499,
            "longitude": -105.1397
        }, headers=headers)
        loc_b_id = loc_b_res.json()["id"]

        # 4. Save Valid Coordinates via PUT /projects/{id}/locations/{loc_id} (Test 1)
        update_loc_res = await client.put(f"/api/v1/projects/{proj_id}/locations/{loc_a_id}", json={
            "latitude": 39.7400,
            "longitude": -104.9910
        }, headers=headers)
        results["Save valid coordinates"] = "PASS" if update_loc_res.status_code == 200 and update_loc_res.json()["latitude"] == 39.7400 else "FAIL"

        # 5. Reload Coordinates via GET /projects/{id}/locations (Test 2)
        get_locs_res = await client.get(f"/api/v1/projects/{proj_id}/locations", headers=headers)
        locs_list = get_locs_res.json()
        reloaded_loc_a = next((l for l in locs_list if l["id"] == loc_a_id), None)
        results["Reload coordinates"] = "PASS" if reloaded_loc_a and reloaded_loc_a["latitude"] == 39.7400 else "FAIL"

        # 6. Scan Geo-Grid (Test 3)
        scan_res = await client.post(f"/api/v1/keywords/{proj_id}/grid/rescan", json={
            "keyword": "plumber denver",
            "location_id": loc_a_id,
            "grid_size": 3,
            "radius_km": 5.0
        }, headers=headers)
        results["Scan Geo-Grid"] = "PASS" if scan_res.status_code == 200 and scan_res.json().get("center_lat") == 39.7400 else "FAIL"

        # 7. Change Location (Test 4) - Verify Location B scan targets Location B coords, not Location A
        scan_loc_b_res = await client.post(f"/api/v1/keywords/{proj_id}/grid/rescan", json={
            "keyword": "plumber lakewood",
            "location_id": loc_b_id,
            "grid_size": 3,
            "radius_km": 5.0
        }, headers=headers)
        results["Change location"] = "PASS" if scan_loc_b_res.status_code == 200 and scan_loc_b_res.json().get("center_lat") == 39.7499 else "FAIL"

        # 8. Invalid Latitude Test (Test 5)
        inv_lat_res = await client.post(f"/api/v1/keywords/{proj_id}/grid/rescan", json={
            "keyword": "plumber denver",
            "center_lat": 140.0,
            "center_lng": -104.9910
        }, headers=headers)
        results["Invalid latitude"] = "PASS" if inv_lat_res.status_code in (400, 422) else "FAIL"

        # 9. Invalid Longitude Test (Test 6)
        inv_lng_res = await client.post(f"/api/v1/keywords/{proj_id}/grid/rescan", json={
            "keyword": "plumber denver",
            "center_lat": 39.7400,
            "center_lng": -250.0
        }, headers=headers)
        results["Invalid longitude"] = "PASS" if inv_lng_res.status_code in (400, 422) else "FAIL"

        # 10. Missing Coordinates Test (Test 7)
        # Create a new project with location having NULL coords and no address to geocode
        proj_no_coords = await client.post("/api/v1/projects", json={
            "name": "No Coords Proj",
            "domain": "nocoords.com",
            "primary_category": "Plumber",
            "location": {
                "name": "",
                "address": ""
            }
        }, headers=headers)
        no_coords_id = proj_no_coords.json()["id"]

        # Null out coords and address fields directly in DB for testing missing coords rejection
        async with AsyncSessionLocal() as db:
            loc_db = (await db.execute(select(Location).where(Location.project_id == no_coords_id))).scalars().first()
            if loc_db:
                loc_db.latitude = None
                loc_db.longitude = None
                loc_db.address = None
                loc_db.city = None
                loc_db.state = None
                loc_db.country = None
                loc_db.name = "Test Location"
                await db.commit()

        missing_coords_res = await client.post(f"/api/v1/keywords/{no_coords_id}/grid/rescan", json={
            "keyword": "plumber denver"
        }, headers=headers)
        results["Missing coordinates"] = "PASS" if missing_coords_res.status_code == 400 and "LOCATION_COORDINATES_REQUIRED" in str(missing_coords_res.json().get("detail")) else "FAIL"

        # 11. Existing Ranking Workflow (Test 11)
        kw_res = await client.post("/api/v1/keywords", json={
            "project_id": proj_id,
            "keyword": "emergency plumber denver",
            "target_location": "Denver, CO"
        }, headers=headers)
        check_kw = await client.post(f"/api/v1/keywords/{kw_res.json()['id']}/check", headers=headers)
        results["Existing ranking workflow"] = "PASS" if check_kw.status_code == 200 else "FAIL"

    print("\n=======================================================")
    print(">> PART 2 ACCEPTANCE TEST RESULTS TABLE")
    print("=======================================================")
    all_passed = True
    for test_name, status in results.items():
        print(f"| {test_name:<30} | {status:<10} |")
        if status != "PASS":
            all_passed = False
    print("=======================================================")

    if all_passed:
        print(">> ALL 11 ACCEPTANCE TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_part2_full_suite())
