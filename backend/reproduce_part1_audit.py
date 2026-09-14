"""
Part 1 Audit & Reproduction Diagnostic Script for LocalLift
Tests exact coordinate handling, edge cases, location creation, manual scans, and location update flows.
"""

import asyncio

import sys
import os

from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User, Organization, OrganizationMember
from app.models.project import Project, Location
from app.models.ranking import Keyword, GeoGridScan

async def run_reproduction_tests():
    print("=======================================================")
    print(">> STARTING PART 1 REPRODUCTION & DIAGNOSTIC TESTS")
    print("=======================================================")

    import uuid
    uid = uuid.uuid4().hex[:6]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Test User & Org
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": f"audit_user_p1_{uid}@example.com",
            "password": "Password123!",
            "full_name": "Audit Tester",
            "organization_name": "Audit Corp P1"
        })
        if reg_resp.status_code != 200:
            print(f"REGISTRATION FAILED: {reg_resp.status_code} {reg_resp.text}")
        assert reg_resp.status_code == 200
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Project with location without coordinates
        proj_resp = await client.post("/api/v1/projects", json={
            "name": "Audit Geo Project",
            "domain": "auditgeoplumbing.com",
            "primary_category": "Plumber",
            "location": {
                "name": "Audit Main Branch",
                "address": "123 Test St",
                "city": "Denver",
                "state": "CO",
                "country": "United States"
                # Note: No latitude/longitude passed!
            }
        }, headers=headers)
        assert proj_resp.status_code == 200
        project = proj_resp.json()
        project_id = project["id"]
        locations = project.get("locations", [])
        loc_id = locations[0]["id"] if locations else None

        print(f"[INFO] Created Project #{project_id}, Location #{loc_id}")
        print(f"[INFO] Initial Location DB record: lat={locations[0].get('latitude')}, lng={locations[0].get('longitude')}")

        # Add keyword for project
        kw_resp = await client.post("/api/v1/keywords", json={
            "project_id": project_id,
            "keyword": "emergency plumber denver",
            "target_location": "Denver, CO"
        }, headers=headers)
        assert kw_resp.status_code == 200
        kw = kw_resp.json()

        results = []

        # --- TEST A: Run Geo-Grid scan using saved location with NULL coordinates ---
        res_a = await client.post(f"/api/v1/keywords/{project_id}/grid/rescan", json={
            "keyword": "emergency plumber denver",
            "location_id": loc_id,
            "grid_size": 5,
            "radius_km": 5.0
        }, headers=headers)
        results.append({
            "test": "Test A: Scan using saved location with NULL coordinates",
            "input": f"location_id={loc_id} (lat=None, lng=None)",
            "status_code": res_a.status_code,
            "response": res_a.json(),
            "expected": "400 LOCATION_COORDINATES_REQUIRED",
            "pass": res_a.status_code == 400 and "LOCATION_COORDINATES_REQUIRED" in str(res_a.json().get("detail"))
        })

        # --- TEST B: Run Geo-Grid scan with valid manual coordinates ---
        res_b = await client.post(f"/api/v1/keywords/{project_id}/grid/rescan", json={
            "keyword": "emergency plumber denver",
            "center_lat": 39.7392,
            "center_lng": -104.9903,
            "center_name": "Denver Manual Center",
            "grid_size": 3,
            "radius_km": 2.5
        }, headers=headers)
        results.append({
            "test": "Test B: Scan with valid manual coordinates (39.7392, -104.9903)",
            "input": "center_lat=39.7392, center_lng=-104.9903",
            "status_code": res_b.status_code,
            "response": "Success (GeoGridScan created)" if res_b.status_code == 200 else res_b.json(),
            "expected": "200 OK",
            "pass": res_b.status_code == 200
        })

        # --- TEST C: Check if Location record in DB was updated with manual coordinates ---
        async with AsyncSessionLocal() as db:
            loc_db = (await db.execute(select(Location).where(Location.id == loc_id))).scalars().first()
            loc_lat_after_manual = loc_db.latitude
            loc_lng_after_manual = loc_db.longitude

        results.append({
            "test": "Test C: Verify if Location DB record persisted manual coordinates from Test B",
            "input": f"Location ID {loc_id}",
            "status_code": 200,
            "response": f"Location DB coordinates after manual scan: lat={loc_lat_after_manual}, lng={loc_lng_after_manual}",
            "expected": "Manual scan SHOULD update location in DB (Currently NULL - Bug Identified!)",
            "pass": loc_lat_after_manual is not None  # Will fail, exposing root cause!
        })

        # --- TEST D: Test empty string coordinates ---
        res_d = await client.post(f"/api/v1/keywords/{project_id}/grid/rescan", json={
            "keyword": "emergency plumber denver",
            "center_lat": None,
            "center_lng": None
        }, headers=headers)
        results.append({
            "test": "Test D: None/Empty coordinates input",
            "input": "center_lat=None, center_lng=None",
            "status_code": res_d.status_code,
            "response": res_d.json().get("detail"),
            "expected": "400 LOCATION_COORDINATES_REQUIRED",
            "pass": res_d.status_code == 400
        })

        # --- TEST E: Test invalid latitude bounds (> 90) ---
        res_e = await client.post(f"/api/v1/keywords/{project_id}/grid/rescan", json={
            "keyword": "emergency plumber denver",
            "center_lat": 125.0,
            "center_lng": -104.9903
        }, headers=headers)
        results.append({
            "test": "Test E: Out of bounds latitude (> 90)",
            "input": "center_lat=125.0",
            "status_code": res_e.status_code,
            "response": res_e.json().get("detail"),
            "expected": "422 Unprocessable Entity / 400 Invalid Latitude",
            "pass": res_e.status_code in (400, 422)
        })

        # --- TEST F: Test invalid longitude bounds (< -180) ---
        res_f = await client.post(f"/api/v1/keywords/{project_id}/grid/rescan", json={
            "keyword": "emergency plumber denver",
            "center_lat": 39.7392,
            "center_lng": -210.0
        }, headers=headers)
        results.append({
            "test": "Test F: Out of bounds longitude (< -180)",
            "input": "center_lng=-210.0",
            "status_code": res_f.status_code,
            "response": res_f.json().get("detail"),
            "expected": "422 Unprocessable Entity / 400 Invalid Longitude",
            "pass": res_f.status_code in (400, 422)
        })

        # --- TEST G: Test latitude 0.0 (Zero value coordinate test) ---
        res_g = await client.post(f"/api/v1/keywords/{project_id}/grid/rescan", json={
            "keyword": "emergency plumber denver",
            "center_lat": 0.0,
            "center_lng": 0.0
        }, headers=headers)
        results.append({
            "test": "Test G: Zero coordinate value (lat=0.0, lng=0.0 Equator/Null Island)",
            "input": "center_lat=0.0, center_lng=0.0",
            "status_code": res_g.status_code,
            "response": "Passed validation" if res_g.status_code == 200 else res_g.json().get("detail"),
            "expected": "200 OK (0.0 treated as valid number, not falsy)",
            "pass": res_g.status_code == 200
        })

        print("\n=======================================================")
        print(">> REPRODUCTION TEST RESULTS TABLE")
        print("=======================================================")
        for idx, r in enumerate(results, 1):
            status = "PASS" if r["pass"] else "FAIL (KNOWN BUG)"
            print(f"[{status}] {r['test']}")
            print(f"       Input:    {r['input']}")
            print(f"       Status:   {r['status_code']}")
            print(f"       Response: {r['response']}")
            print(f"       Expected: {r['expected']}\n")

if __name__ == "__main__":
    asyncio.run(run_reproduction_tests())
