import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
import app.models  # noqa: F401
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Website
from app.models.ranking import Keyword
from app.models.local_seo import Review, Citation
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.audit import SEOAudit, SEOTask
from app.core.security import get_password_hash, create_access_token
from app.main import app


async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def test_user_central_dashboard_isolation_and_aggregation():
    async def _run():
        await init_tables()
        u_id = uuid.uuid4().hex[:8]

        async with AsyncSessionLocal() as db:
            # Customer A (Owns Org A with 2 projects: UIS Digital, Box Food)
            user_a = User(
                email=f"cust_a_{u_id}@example.com",
                full_name="Customer A",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=False,
                platform_role=None
            )
            # Customer B (Owns Org B with 1 project: Competitor Corp)
            user_b = User(
                email=f"cust_b_{u_id}@example.com",
                full_name="Customer B",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=False,
                platform_role=None
            )
            # Platform Owner (Superuser)
            admin_user = User(
                email=f"admin_{u_id}@example.com",
                full_name="Platform Owner",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=True,
                platform_role="super_admin"
            )
            db.add_all([user_a, user_b, admin_user])
            await db.commit()
            await db.refresh(user_a)
            await db.refresh(user_b)
            await db.refresh(admin_user)

            # Create Organizations
            org_a = Organization(name=f"Org A {u_id}", slug=f"org-a-{u_id}", plan="agency_pro", status="active")
            org_b = Organization(name=f"Org B {u_id}", slug=f"org-b-{u_id}", plan="starter", status="active")
            db.add_all([org_a, org_b])
            await db.commit()
            await db.refresh(org_a)
            await db.refresh(org_b)

            # Memberships
            mem_a = OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role=OrgRole.OWNER)
            mem_b = OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role=OrgRole.OWNER)
            db.add_all([mem_a, mem_b])
            await db.commit()

            # Projects for Org A
            proj_a1 = Project(organization_id=org_a.id, name="UIS Digital", domain="uisdigital.com", primary_category="Digital Marketing Agency", health_score=88)
            proj_a2 = Project(organization_id=org_a.id, name="box food", domain="boxseafoodrestaurant.com.au", primary_category="Restaurant", health_score=75)
            # Project for Org B
            proj_b1 = Project(organization_id=org_b.id, name="Competitor Corp", domain="competitor.com", primary_category="Retail", health_score=60)
            db.add_all([proj_a1, proj_a2, proj_b1])
            await db.commit()
            await db.refresh(proj_a1)
            await db.refresh(proj_a2)
            await db.refresh(proj_b1)

            # Keywords for Org A (5 keywords total)
            kw1 = Keyword(project_id=proj_a1.id, keyword="local seo melbourne", current_rank=3)
            kw2 = Keyword(project_id=proj_a1.id, keyword="seo digital agency", current_rank=7)
            kw3 = Keyword(project_id=proj_a2.id, keyword="best seafood melbourne", current_rank=1)
            # Keywords for Org B (10 keywords total)
            kw4 = Keyword(project_id=proj_b1.id, keyword="competitor keyword 1", current_rank=15)
            db.add_all([kw1, kw2, kw3, kw4])

            # Reviews for Org A
            rev1 = Review(project_id=proj_a1.id, author_name="John Doe", rating=5.0, text="Great SEO agency", review_id=f"r1_{u_id}")
            rev2 = Review(project_id=proj_a2.id, author_name="Jane Smith", rating=4.0, text="Delicious seafood", review_id=f"r2_{u_id}")
            # Reviews for Org B
            rev3 = Review(project_id=proj_b1.id, author_name="Bob", rating=1.0, text="Bad service", review_id=f"r3_{u_id}")
            db.add_all([rev1, rev2, rev3])

            # Scan Jobs for Org A
            job1 = ScanJob(
                organization_id=org_a.id,
                project_id=proj_a1.id,
                job_type=JobType.KEYWORD_RANK.value,
                status=JobStatus.COMPLETED.value,
                total_items=10,
                processed_items=10
            )
            job2 = ScanJob(
                organization_id=org_a.id,
                project_id=proj_a2.id,
                job_type=JobType.GEO_GRID.value,
                status=JobStatus.RUNNING.value,
                total_items=25,
                processed_items=12
            )
            # Scan Job for Org B
            job3 = ScanJob(
                organization_id=org_b.id,
                project_id=proj_b1.id,
                job_type=JobType.WEBSITE_AUDIT.value,
                status=JobStatus.COMPLETED.value,
                total_items=50,
                processed_items=50
            )
            db.add_all([job1, job2, job3])
            await db.commit()

        # Generate tokens
        token_a = create_access_token(data={"sub": str(user_a.id)})
        token_b = create_access_token(data={"sub": str(user_b.id)})
        token_admin = create_access_token(data={"sub": str(admin_user.id)})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Customer A requests User Central Dashboard Overview
            res_a = await client.get("/api/v1/dashboard/overview", headers={"Authorization": f"Bearer {token_a}"})
            assert res_a.status_code == 200, f"Failed: {res_a.text}"
            data_a = res_a.json()

            # Customer A has 2 projects (UIS Digital, box food), 3 keywords, 2 reviews, 1 active job, 1 completed job
            summary_a = data_a["summary"]
            assert summary_a["total_projects"] == 2
            assert summary_a["tracked_keywords"] == 3
            assert summary_a["total_reviews"] == 2
            assert summary_a["active_scan_jobs"] == 1
            assert summary_a["completed_scans"] == 1

            # Projects list for Customer A
            proj_names_a = [p["name"] for p in data_a["projects"]]
            assert "UIS Digital" in proj_names_a
            assert "box food" in proj_names_a
            assert "Competitor Corp" not in proj_names_a  # Tenant isolation!

            # 2. Customer B requests User Central Dashboard Overview
            res_b = await client.get("/api/v1/dashboard/overview", headers={"Authorization": f"Bearer {token_b}"})
            assert res_b.status_code == 200
            data_b = res_b.json()
            assert data_b["summary"]["total_projects"] == 1
            assert data_b["summary"]["tracked_keywords"] == 1
            assert data_b["projects"][0]["name"] == "Competitor Corp"
            assert "UIS Digital" not in [p["name"] for p in data_b["projects"]]

            # 3. Customer A requests Analytics
            res_analytics_a = await client.get(
                "/api/v1/dashboard/analytics?date_range=30d",
                headers={"Authorization": f"Bearer {token_a}"}
            )
            assert res_analytics_a.status_code == 200
            an_data_a = res_analytics_a.json()
            comp_names_a = [p["project_name"] for p in an_data_a["project_comparison"]]
            assert "UIS Digital" in comp_names_a
            assert "box food" in comp_names_a
            assert "Competitor Corp" not in comp_names_a

            # 4. Security: Customer A tries to access /api/v1/masterplace/overview -> MUST BE 403 Forbidden!
            res_mp_a = await client.get("/api/v1/masterplace/overview", headers={"Authorization": f"Bearer {token_a}"})
            assert res_mp_a.status_code == 403, f"Expected 403 for normal customer, got {res_mp_a.status_code}"

            # 5. Platform Admin accesses /api/v1/masterplace/overview -> 200 OK with platform-wide data
            res_mp_admin = await client.get("/api/v1/masterplace/overview", headers={"Authorization": f"Bearer {token_admin}"})
            assert res_mp_admin.status_code == 200

    asyncio.run(_run())
