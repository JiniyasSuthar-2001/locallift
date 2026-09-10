import asyncio
import sys
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User, Organization
from app.models.project import Project, Location, Website
from app.models.audit import SEOIssue, SEOTask, IssueSeverity, IssueStatus, TaskStatus, TaskPriority
from app.models.connections import PublicBusinessListing
from app.core.security import get_password_hash, create_access_token
from app.test_helper import init_test_db, create_test_tenant

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

async def run_button_audit_tests():
    print("==================================================")
    print("STARTING BUTTON AUDIT & FEATURE INTEGRITY TEST SUITE")
    print("==================================================")

    await init_test_db(seed_demo=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup Tenant A and Tenant B
        suffix_a = str(uuid.uuid4())[:8]
        suffix_b = str(uuid.uuid4())[:8]
        
        user_a, org_a, project_a, token_a = await create_test_tenant(f"Tenant A {suffix_a}", f"owner_a_{suffix_a}@example.com")
        user_b, org_b, project_b, token_b = await create_test_tenant(f"Tenant B {suffix_b}", f"owner_b_{suffix_b}@example.com")

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with AsyncSessionLocal() as session:
            # Create an issue for Tenant A's project
            issue_a = SEOIssue(
                project_id=project_a.id,
                title="Missing LocalBusiness Schema Markup",
                category="schema_structured_data",
                severity=IssueSeverity.CRITICAL,
                status=IssueStatus.OPEN,
                evidence="No JSON-LD script found on homepage",
                why_it_matters="Google cannot extract entity details for Local Pack without schema",
                recommended_solution="Inject standard LocalBusiness JSON-LD template into header"
            )
            session.add(issue_a)
            await session.commit()
            await session.refresh(issue_a)

        # -------------------------------------------------------------
        # TEST 1: PRIORITY 1 - Convert Issue to Task
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing Convert Issue to Task (/api/v1/tasks/convert-issue/{id})...")

        # 1a. Convert valid issue
        conv_res = await client.post(
            f"/api/v1/tasks/convert-issue/{issue_a.id}",
            json={"priority": "high"},
            headers=headers_a
        )
        assert conv_res.status_code == 200, f"Expected 200, got {conv_res.status_code}: {conv_res.text}"
        task_data = conv_res.json()
        assert task_data["issue_id"] == issue_a.id
        assert task_data["project_id"] == project_a.id
        assert task_data["title"] == f"Resolve: {issue_a.title}"
        assert task_data["priority"] == "high"
        assert task_data["status"] == "open"
        print(f"  [PASS] Task successfully created from issue (Task ID: {task_data['id']})")

        # 1b. Duplicate conversion idempotency
        dup_res = await client.post(
            f"/api/v1/tasks/convert-issue/{issue_a.id}",
            headers=headers_a
        )
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert dup_data["id"] == task_data["id"], "Idempotent conversion should return existing task"
        print(f"  [PASS] Duplicate conversion handled idempotently without duplicating tasks")

        # 1c. Cross-Tenant IDOR protection
        cross_res = await client.post(
            f"/api/v1/tasks/convert-issue/{issue_a.id}",
            json={"priority": "high"},
            headers=headers_b
        )
        assert cross_res.status_code in [403, 404], f"Expected 403 or 404 for cross-tenant issue conversion, got {cross_res.status_code}"
        print(f"  [PASS] Cross-tenant issue conversion blocked ({cross_res.status_code})")

        # 1d. Nonexistent issue 404
        nonexist_res = await client.post(
            "/api/v1/tasks/convert-issue/999999",
            headers=headers_a
        )
        assert nonexist_res.status_code == 404
        print("  [PASS] Nonexistent issue returned 404 Not Found")

        # -------------------------------------------------------------
        # TEST 2: PRIORITY 2 - Public Google Maps Business Listing Table
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing Public Google Maps Listing API & Field Contract...")

        full_maps_url = "https://www.google.com/maps/place/Brisbane+Dental+Studio/@-27.4705,153.0260,17z/data=!1s0x6b915a1b2c3d4e5f:0x9876543210fedcba"
        import_res = await client.post(
            "/api/v1/connections/public-maps/import",
            json={
                "maps_url": full_maps_url,
                "project_id": project_a.id,
                "target_category": "Dentist"
            },
            headers=headers_a
        )
        assert import_res.status_code == 200, f"Import failed: {import_res.text}"
        pub_item = import_res.json()
        
        # Verify canonical field contract
        assert pub_item["name"] == "Brisbane Dental Studio"
        assert pub_item["maps_url"] == full_maps_url
        assert pub_item["primary_category"] == "Dentist"
        assert pub_item["rating"] is None, f"Expected rating=None, got {pub_item['rating']}"
        assert pub_item["review_count"] is None, f"Expected review_count=None, got {pub_item['review_count']}"
        assert pub_item["is_managed"] is False
        print(f"  [PASS] Public business imported with canonical fields: name='{pub_item['name']}', primary_category='{pub_item['primary_category']}', rating={pub_item['rating']}, review_count={pub_item['review_count']}")

        # Verify listing endpoint returns matching canonical fields
        list_res = await client.get("/api/v1/connections/public-maps", headers=headers_a)
        assert list_res.status_code == 200
        listings = list_res.json()
        assert len(listings) >= 1
        found_listing = next(l for l in listings if l["id"] == pub_item["id"])
        assert found_listing["name"] == "Brisbane Dental Studio"
        assert found_listing["maps_url"] == full_maps_url
        assert found_listing["primary_category"] == "Dentist"
        assert found_listing["rating"] is None
        assert found_listing["review_count"] is None
        print(f"  [PASS] GET /connections/public-maps correctly returned {len(listings)} listings matching schema")

        # -------------------------------------------------------------
        # TEST 3: PRIORITY 3 - Team Directory & Project Invitation
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing Team Directory & Invitation Endpoint...")

        # 3a. Verify Team Directory listing
        dir_res = await client.get("/api/v1/team", headers=headers_a)
        assert dir_res.status_code == 200
        dir_members = dir_res.json()
        assert len(dir_members) >= 1
        print(f"  [PASS] GET /team returned {len(dir_members)} organization member(s)")

        # 3b. Authorized owner invites a collaborator to project
        invite_email = f"specialist_{suffix_a}@agency.com"
        invite_res = await client.post(
            f"/api/v1/projects/{project_a.id}/team/invite",
            json={
                "email": invite_email,
                "role": "SEO Specialist",
                "permissions": ["project_overview", "seo_audit", "tasks"]
            },
            headers=headers_a
        )
        assert invite_res.status_code == 200, f"Invite failed: {invite_res.text}"
        inv_data = invite_res.json()
        assert inv_data["email"] == invite_email
        assert inv_data["role"] == "SEO Specialist"
        assert "seo_audit" in inv_data["permissions"]
        print(f"  [PASS] Invitation successfully created for {invite_email} on Project {project_a.id}")

        # 3c. Unauthorized user (Tenant B) cannot invite to Tenant A's project
        unauth_invite = await client.post(
            f"/api/v1/projects/{project_a.id}/team/invite",
            json={
                "email": "hacker@domain.com",
                "role": "Owner",
                "permissions": ["settings"]
            },
            headers=headers_b
        )
        assert unauth_invite.status_code == 403, f"Expected 403, got {unauth_invite.status_code}"
        print(f"  [PASS] Unauthorized user strictly blocked from inviting to another tenant's project (403)")

    print("\n==================================================")
    print("ALL BUTTON AUDIT & FEATURE INTEGRITY TESTS PASSED! (3/3)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_button_audit_tests())
