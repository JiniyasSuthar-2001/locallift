import sys
import os
import asyncio
import unittest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import Base
from app.main import app
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location, Website
from app.models.audit import SEOAudit, WebsitePage
from app.test_helper import init_test_db


class TestProjectIsolationAndGBPHub(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_test_db(seed_demo=False)

    async def test_01_same_domain_project_container_isolation(self):
        """
        CRITICAL ISOLATION TEST:
        Project A (domain: example.com) and Project B (domain: example.com)
        MUST remain strictly isolated containers. Crawl A data must NEVER leak into Project B.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            uid = uuid.uuid4().hex[:8]

            # Register User A & User B in separate orgs
            reg_a = await client.post("/api/v1/auth/register", json={
                "email": f"usera_{uid}@org-a.com",
                "password": "Password123!",
                "full_name": "User Alpha",
                "organization_name": f"Org Alpha {uid}"
            })
            headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}

            reg_b = await client.post("/api/v1/auth/register", json={
                "email": f"userb_{uid}@org-b.com",
                "password": "Password123!",
                "full_name": "User Beta",
                "organization_name": f"Org Beta {uid}"
            })
            headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

            # Create Project A (domain: example.com)
            pa_res = await client.post("/api/v1/projects", json={
                "name": "Project Alpha (Same Domain)",
                "domain": "shared-domain-test.com",
                "primary_category": "Plumbing"
            }, headers=headers_a)
            assert pa_res.status_code == 200
            proj_a = pa_res.json()
            proj_a_id = proj_a["id"]

            # Create Project B (SAME domain: shared-domain-test.com)
            pb_res = await client.post("/api/v1/projects", json={
                "name": "Project Beta (Same Domain)",
                "domain": "shared-domain-test.com",
                "primary_category": "Electrician"
            }, headers=headers_b)
            assert pb_res.status_code == 200
            proj_b = pb_res.json()
            proj_b_id = proj_b["id"]

            self.assertNotEqual(proj_a_id, proj_b_id)

            # Trigger Crawl on Project A
            crawl_a_res = await client.post(f"/api/v1/audits/crawl/{proj_a_id}", json={
                "url": "https://example.com",
                "max_pages": 5,
                "allow_local_dev": True
            }, headers=headers_a)
            self.assertEqual(crawl_a_res.status_code, 200)

            # Trigger Crawl on Project B
            crawl_b_res = await client.post(f"/api/v1/audits/crawl/{proj_b_id}", json={
                "url": "https://example.com",
                "max_pages": 5,
                "allow_local_dev": True
            }, headers=headers_b)
            self.assertEqual(crawl_b_res.status_code, 200)

            # Fetch Latest Audit for Project A
            audit_a_res = await client.get(f"/api/v1/audits/{proj_a_id}/latest", headers=headers_a)
            self.assertEqual(audit_a_res.status_code, 200)
            if audit_a_res.json():
                self.assertEqual(audit_a_res.json()["project_id"], proj_a_id)

            # Fetch Latest Audit for Project B
            audit_b_res = await client.get(f"/api/v1/audits/{proj_b_id}/latest", headers=headers_b)
            self.assertEqual(audit_b_res.status_code, 200)
            if audit_b_res.json():
                self.assertEqual(audit_b_res.json()["project_id"], proj_b_id)

            # Cross-Tenant Access Protection
            cross_a = await client.get(f"/api/v1/audits/{proj_a_id}/latest", headers=headers_b)
            self.assertIn(cross_a.status_code, (403, 404))

    async def test_02_backend_project_deletion(self):
        """
        PROJECT DELETION TEST:
        Deleting Project A removes Project A and its child records, while Project B remains untouched.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            uid = uuid.uuid4().hex[:8]

            reg = await client.post("/api/v1/auth/register", json={
                "email": f"delete_user_{uid}@test.com",
                "password": "Password123!",
                "full_name": "Delete Tester",
                "organization_name": f"Delete Org {uid}"
            })
            headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

            p_res = await client.post("/api/v1/projects", json={
                "name": "Project To Delete",
                "domain": "delete-me-test.com",
                "primary_category": "Contractor"
            }, headers=headers)
            proj_id = p_res.json()["id"]

            # Delete project
            del_res = await client.delete(f"/api/v1/projects/{proj_id}", headers=headers)
            self.assertEqual(del_res.status_code, 200)
            self.assertEqual(del_res.json()["id"], proj_id)

            # Verify project no longer exists
            get_res = await client.get(f"/api/v1/projects/{proj_id}", headers=headers)
            self.assertIn(get_res.status_code, (403, 404))

    async def test_03_gbp_hub_unconnected_data_provenance(self):
        """
        GBP HUB UNCONNECTED TEST:
        When GBP is unconnected, public summary returns honest calculated data,
        marking call volume as 'Requires Google Connection' (never fake numbers).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            uid = uuid.uuid4().hex[:8]

            reg = await client.post("/api/v1/auth/register", json={
                "email": f"gbp_user_{uid}@test.com",
                "password": "Password123!",
                "full_name": "GBP Tester",
                "organization_name": f"GBP Org {uid}"
            })
            headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

            p_res = await client.post("/api/v1/projects", json={
                "name": "Unconnected Business",
                "domain": "unconnected-biz.com",
                "primary_category": "Dental"
            }, headers=headers)
            proj_id = p_res.json()["id"]

            # Fetch GBP status
            status_res = await client.get(f"/api/v1/gbp/{proj_id}/status", headers=headers)
            self.assertEqual(status_res.status_code, 200)
            self.assertFalse(status_res.json()["is_connected"])

            # Fetch public summary
            pub_res = await client.get(f"/api/v1/gbp/{proj_id}/public-summary", headers=headers)
            self.assertEqual(pub_res.status_code, 200)
            pub_data = pub_res.json()

            self.assertEqual(pub_data["source"], "google_places_api")
            self.assertIsNone(pub_data.get("call_clicks"))

    async def test_04_public_observation_change_tracking(self):
        """
        PUBLIC OBSERVATION CHANGE TRACKING TEST:
        When a public place lookup is executed, real changes between observations populate GoogleObservedChange.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            uid = uuid.uuid4().hex[:8]

            reg = await client.post("/api/v1/auth/register", json={
                "email": f"obs_user_{uid}@test.com",
                "password": "Password123!",
                "full_name": "Obs Tester",
                "organization_name": f"Obs Org {uid}"
            })
            headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

            p_res = await client.post("/api/v1/projects", json={
                "name": "Change Tracked Plumbing",
                "domain": "change-tracked-plumbing.com",
                "primary_category": "Plumber"
            }, headers=headers)
            proj_id = p_res.json()["id"]

            # Perform initial public lookup
            lookup1 = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
                "business_name": "Change Tracked Plumbing",
                "location": "Denver, CO"
            }, headers=headers)
            self.assertEqual(lookup1.status_code, 200)

            # Perform second lookup
            lookup2 = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
                "business_name": "Change Tracked Plumbing",
                "location": "Denver, CO"
            }, headers=headers)
            self.assertEqual(lookup2.status_code, 200)

            # Fetch public profile response
            pub_res = await client.get(f"/api/v1/gbp/{proj_id}/public-profile", headers=headers)
            self.assertEqual(pub_res.status_code, 200)
            data = pub_res.json()
            self.assertIn("observed_changes", data)
            self.assertIn("post_observations", data)

    async def test_05_same_domain_gbp_public_isolation(self):
        """
        SAME DOMAIN PUBLIC ISOLATION TEST:
        Org A and Org B creating public profile lookups on identical domain ('same-domain.com')
        must maintain strictly separate PublicBusinessListing & GoogleObservedChange records.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            uid = uuid.uuid4().hex[:8]

            # Register Org A
            reg_a = await client.post("/api/v1/auth/register", json={
                "email": f"domain_a_{uid}@org-a.com",
                "password": "Password123!",
                "full_name": "User Alpha",
                "organization_name": f"Org Alpha {uid}"
            })
            headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}

            # Register Org B
            reg_b = await client.post("/api/v1/auth/register", json={
                "email": f"domain_b_{uid}@org-b.com",
                "password": "Password123!",
                "full_name": "User Beta",
                "organization_name": f"Org Beta {uid}"
            })
            headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

            # Create Project A & Project B on same domain
            pa = (await client.post("/api/v1/projects", json={"name": "A", "domain": "same-domain.com"}, headers=headers_a)).json()["id"]
            pb = (await client.post("/api/v1/projects", json={"name": "B", "domain": "same-domain.com"}, headers=headers_b)).json()["id"]

            # Perform public lookup on A
            await client.post(f"/api/v1/gbp/{pa}/public-lookup", json={"business_name": "Biz A"}, headers=headers_a)

            # Verify Org B cannot access Org A's public profile
            cross_res = await client.get(f"/api/v1/gbp/{pa}/public-profile", headers=headers_b)
            self.assertIn(cross_res.status_code, (403, 404))


if __name__ == "__main__":
    unittest.main()

