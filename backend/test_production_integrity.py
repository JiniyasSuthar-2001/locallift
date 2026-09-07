import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User, Organization
from app.models.project import Project, Location, Website
from app.models.local_seo import SchemaRecord, Review
from app.models.gbp import GoogleAccount
from app.core.security import get_password_hash, create_access_token
from app.test_helper import init_test_db
from sqlalchemy.future import select

async def test_production_integrity():
    # Ensure DB tables exist for integrity tests
    await init_test_db(seed_demo=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with AsyncSessionLocal() as session:
            # 1. Setup Tenant
            import uuid
            uid = uuid.uuid4().hex[:8]
            org = Organization(name="Integrity Test Org", slug=f"integrity-org-{uid}")
            session.add(org)
            await session.flush()

            user = User(
                email=f"integrity-{uid}@example.com",
                hashed_password=get_password_hash("password123"),
                full_name="Integrity User",
                is_active=True
            )
            session.add(user)
            await session.flush()

            from app.models.user import OrganizationMember, OrgRole
            mem = OrganizationMember(
                user_id=user.id,
                organization_id=org.id,
                role=OrgRole.OWNER
            )
            session.add(mem)
            await session.flush()

            project = Project(
                organization_id=org.id,
                name="Integrity Denver Plumbing",
                domain="example.com",
                primary_category="Plumber"
            )
            session.add(project)
            await session.flush()

            loc = Location(
                project_id=project.id,
                name="HQ",
                city="Denver",
                state="CO",
                latitude=39.7392,
                longitude=-104.9903,
                phone="(303) 555-0199"
            )
            session.add(loc)
            await session.commit()
            
            user_id = user.id
            proj_id = project.id

        token = create_access_token(str(user_id))
        headers = {"Authorization": f"Bearer {token}"}

        # -------------------------------------------------------------
        # TEST 1: Schema Intelligence Pipeline & Persistence
        # -------------------------------------------------------------
        print("\n--- Testing Schema Intelligence Pipeline ---")
        # Run schema analysis
        resp_analyze = await client.post(f"/api/v1/local-seo/schema/analyze/{proj_id}", headers=headers)
        assert resp_analyze.status_code == 200, f"Analyze failed: {resp_analyze.text}"
        summary_data = resp_analyze.json()
        assert "health_score" in summary_data
        assert "stats" in summary_data
        assert "tier_1_status" in summary_data

        # Verify SchemaRecord entries were persisted to DB
        async with AsyncSessionLocal() as session:
            db_records = await session.execute(select(SchemaRecord).where(SchemaRecord.project_id == proj_id))
            records_list = db_records.scalars().all()
            assert len(records_list) > 0, "SchemaRecords were not persisted to database!"
            for r in records_list:
                assert r.page_url is not None
                assert r.quality_score >= 0
                assert r.project_id == proj_id

        # Verify summary endpoint reads the exact same persisted records
        resp_summary = await client.get(f"/api/v1/local-seo/schema/{proj_id}/intelligence", headers=headers)
        assert resp_summary.status_code == 200
        sum_get_data = resp_summary.json()
        assert len(sum_get_data["records"]) == len(records_list)
        print(f"[PASS] Schema Intelligence Pipeline ({len(records_list)} records persisted & verified)")

        # -------------------------------------------------------------
        # TEST 2: GBP Honest Disconnect Behavior
        # -------------------------------------------------------------
        print("\n--- Testing GBP Honest Disconnect Behavior ---")
        # Disconnect when not connected
        resp_disc1 = await client.post(f"/api/v1/gbp/{proj_id}/disconnect", headers=headers)
        assert resp_disc1.status_code == 200
        disc_json = resp_disc1.json()
        assert disc_json["message"] == "No Google Business Profile connection was active."
        assert disc_json["status"] == "not_connected"
        print("[PASS] GBP Disconnect when inactive returns honest state")

        # Now simulate an active GoogleAccount connection
        async with AsyncSessionLocal() as session:
            g_acc = GoogleAccount(
                project_id=proj_id,
                account_email="test@google.com",
                is_connected=True,
                access_token="fake-token"
            )
            session.add(g_acc)
            await session.commit()

        resp_disc2 = await client.post(f"/api/v1/gbp/{proj_id}/disconnect", headers=headers)
        assert resp_disc2.status_code == 200
        disc_json2 = resp_disc2.json()
        assert disc_json2["message"] == "Google Business Profile disconnected successfully."
        assert disc_json2["status"] == "disconnected"
        print("[PASS] GBP Disconnect when active successfully disconnects")

        # -------------------------------------------------------------
        # TEST 3: Content Opportunities Honest Search Volume
        # -------------------------------------------------------------
        print("\n--- Testing Content Opportunities Honest Search Volume ---")
        resp_opps = await client.get(f"/api/v1/ai/content-opportunities/{proj_id}", headers=headers)
        assert resp_opps.status_code == 200
        opps_list = resp_opps.json()
        assert len(opps_list) > 0
        for opp in opps_list:
            assert opp.get("search_volume") is None, f"Found hardcoded search volume: {opp.get('search_volume')}"
            assert "unavailable" in opp.get("search_volume_status", "").lower()
            assert "Denver" in opp["topic"] or "Plumber" in opp["topic"] or "Plumbing" in opp["topic"]
        print("[PASS] Content Opportunities uses real project location & honest search volume status")

        # -------------------------------------------------------------
        # TEST 4: Global Structured Error Handler
        # -------------------------------------------------------------
        print("\n--- Testing Global Structured Error Handler ---")
        resp_404 = await client.get("/api/v1/nonexistent-route", headers=headers)
        assert resp_404.status_code == 404
        err_json = resp_404.json()
        assert err_json["error"] is True
        assert err_json["code"] == "HTTP_404"
        assert "request_id" in err_json
        print(f"[PASS] Global Structured Error Handler (ReqID: {err_json['request_id']})")

if __name__ == "__main__":
    asyncio.run(test_production_integrity())
    print("\n[SUCCESS] ALL PRODUCTION INTEGRITY TESTS PASSED 100%!")
