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

async def test_multi_tenant_security():
    await init_test_db(seed_demo=True)

    import uuid
    uid = uuid.uuid4().hex[:8]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register User A (Tenant A)
        res_a = await client.post("/api/v1/auth/register", json={
            "email": f"user_a_{uid}@tenant-a.com",
            "full_name": "User Alpha",
            "password": "Password123!",
            "organization_name": f"Tenant A Organization {uid}"
        })
        assert res_a.status_code == 200, f"User A registration failed: {res_a.text}"
        data_a = res_a.json()
        token_a = data_a["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        org_a_id = data_a["user"]["organization_id"]

        # 2. Register User B (Tenant B)
        res_b = await client.post("/api/v1/auth/register", json={
            "email": f"user_b_{uid}@tenant-b.com",
            "full_name": "User Beta",
            "password": "Password123!",
            "organization_name": f"Tenant B Organization {uid}"
        })
        assert res_b.status_code == 200, f"User B registration failed: {res_b.text}"
        data_b = res_b.json()
        token_b = data_b["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        org_b_id = data_b["user"]["organization_id"]

        print(f"[OK] Tenants registered: Org A ({org_a_id}) vs Org B ({org_b_id})")

        # 3. User A creates Project A
        proj_a_res = await client.post("/api/v1/projects", json={
            "name": "Project Alpha",
            "domain": "project-alpha.com",
            "primary_category": "Electrician",
            "country": "United States"
        }, headers=headers_a)
        assert proj_a_res.status_code == 200
        proj_a = proj_a_res.json()
        proj_a_id = proj_a["id"]

        # 4. User B creates Project B
        proj_b_res = await client.post("/api/v1/projects", json={
            "name": "Project Beta",
            "domain": "project-beta.com",
            "primary_category": "Plumber",
            "country": "Australia"
        }, headers=headers_b)
        assert proj_b_res.status_code == 200
        proj_b = proj_b_res.json()
        proj_b_id = proj_b["id"]

        # -------------------------------------------------------------
        # TEST: Cross-Tenant Project Access Isolation
        # -------------------------------------------------------------
        # User B attempts to read Project A -> Must be 403 Forbidden
        cross_get = await client.get(f"/api/v1/projects/{proj_a_id}", headers=headers_b)
        assert cross_get.status_code in (403, 404), f"Expected 403/404 for cross-tenant project get, got {cross_get.status_code}"
        print("[OK] Cross-tenant GET project blocked")

        # User B attempts to update Project A -> Must be 403 Forbidden
        cross_put = await client.put(f"/api/v1/projects/{proj_a_id}", json={"name": "Hacked Name"}, headers=headers_b)
        assert cross_put.status_code in (403, 404), f"Expected 403/404 for cross-tenant project update, got {cross_put.status_code}"
        print("[OK] Cross-tenant PUT project blocked")

        # User B attempts to delete Project A -> Must be 403 Forbidden
        cross_del = await client.delete(f"/api/v1/projects/{proj_a_id}", headers=headers_b)
        assert cross_del.status_code in (403, 404), f"Expected 403/404 for cross-tenant project delete, got {cross_del.status_code}"
        print("[OK] Cross-tenant DELETE project blocked")

        # -------------------------------------------------------------
        # TEST: Cross-Tenant Project Creation Escape Prevention
        # -------------------------------------------------------------
        # User A attempts to create a project under User B's organization_id -> Must be 403 Forbidden
        escape_res = await client.post("/api/v1/projects", json={
            "name": "Malicious Project In Org B",
            "domain": "malicious.com",
            "organization_id": org_b_id,
            "primary_category": "Locksmith"
        }, headers=headers_a)
        assert escape_res.status_code == 403, f"Expected 403 for unauthorized org_id creation, got {escape_res.status_code}"
        print("[OK] Cross-organization project creation escape blocked")

        # -------------------------------------------------------------
        # TEST: Cross-Tenant Templates Security
        # -------------------------------------------------------------
        # User A creates a custom template in Org A
        tmpl_a_res = await client.post("/api/v1/templates", json={
            "name": "Alpha Custom Schema",
            "category": "schema",
            "template_type": "schema_jsonld",
            "description": "Tenant A proprietary template",
            "content": '{"@context": "https://schema.org", "@type": "LocalBusiness", "name": "{{business_name}}"}'
        }, headers=headers_a)
        assert tmpl_a_res.status_code == 201, f"Template creation failed: {tmpl_a_res.text}"
        tmpl_a = tmpl_a_res.json()
        tmpl_a_id = tmpl_a["id"]

        # User B lists templates -> Should see system templates, but NOT User A's custom template
        b_list = await client.get("/api/v1/templates", headers=headers_b)
        assert b_list.status_code == 200
        b_tmpl_ids = [t["id"] for t in b_list.json()]
        assert tmpl_a_id not in b_tmpl_ids, "User B leaked User A's custom template in list!"
        print("[OK] Cross-tenant template listing isolation verified")

        # User B attempts to read User A's template directly -> 403
        b_get_tmpl = await client.get(f"/api/v1/templates/{tmpl_a_id}", headers=headers_b)
        assert b_get_tmpl.status_code == 403, f"Expected 403 for cross-tenant template get, got {b_get_tmpl.status_code}"
        print("[OK] Cross-tenant GET template directly blocked")

        # User B attempts to update User A's template -> 403
        b_put_tmpl = await client.put(f"/api/v1/templates/{tmpl_a_id}", json={"name": "Tampered Template"}, headers=headers_b)
        assert b_put_tmpl.status_code == 403, f"Expected 403 for cross-tenant template update, got {b_put_tmpl.status_code}"
        print("[OK] Cross-tenant PUT template blocked")

        # User B attempts to delete User A's template -> 403
        b_del_tmpl = await client.delete(f"/api/v1/templates/{tmpl_a_id}", headers=headers_b)
        assert b_del_tmpl.status_code == 403, f"Expected 403 for cross-tenant template delete, got {b_del_tmpl.status_code}"
        print("[OK] Cross-tenant DELETE template blocked")

        # User B attempts to apply User A's template to Project B -> 403
        b_apply = await client.post(f"/api/v1/templates/{tmpl_a_id}/apply", json={
            "project_id": proj_b_id
        }, headers=headers_b)
        assert b_apply.status_code == 403, f"Expected 403 for applying another tenant's template, got {b_apply.status_code}"
        print("[OK] Cross-tenant template apply blocked")

        # User A attempts to apply their template to User B's Project B -> 403
        a_apply_cross_proj = await client.post(f"/api/v1/templates/{tmpl_a_id}/apply", json={
            "project_id": proj_b_id
        }, headers=headers_a)
        assert a_apply_cross_proj.status_code in (403, 404), f"Expected 403/404 for applying template to foreign project, got {a_apply_cross_proj.status_code}"
        print("[OK] Template apply to foreign project blocked")

        # -------------------------------------------------------------
        # TEST: Cross-Tenant Task Creation & Assignment
        # -------------------------------------------------------------
        # User A attempts to assign task in Project A to User B (different org) -> 400
        cross_assign = await client.post("/api/v1/tasks", json={
            "project_id": proj_a_id,
            "title": "Unauthorized Assignment Task",
            "assigned_to_id": data_b["user"]["id"],
            "priority": "high",
            "status": "open"
        }, headers=headers_a)
        assert cross_assign.status_code == 400, f"Expected 400 for cross-org user assignment, got {cross_assign.status_code}"
        print("[OK] Cross-org task assignment blocked")

        print("\n=======================================================================")
        print(">> ALL MULTI-TENANT SECURITY & ISOLATION CHECKS PASSED!")
        print("=======================================================================")

if __name__ == "__main__":
    asyncio.run(test_multi_tenant_security())
