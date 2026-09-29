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
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.platform_audit import PlatformAuditLog
from app.models.ai_control import SystemSetting
from app.core.security import get_password_hash, create_access_token
from app.main import app


async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        def _add_cols(connection):
            from sqlalchemy import inspect, text
            insp = inspect(connection)
            if "users" in insp.get_table_names():
                u_cols = [c["name"] for c in insp.get_columns("users")]
                if "platform_role" not in u_cols:
                    connection.execute(text("ALTER TABLE users ADD COLUMN platform_role VARCHAR(50);"))
            if "organizations" in insp.get_table_names():
                o_cols = [c["name"] for c in insp.get_columns("organizations")]
                if "status" not in o_cols:
                    connection.execute(text("ALTER TABLE organizations ADD COLUMN status VARCHAR(50) DEFAULT 'active';"))
        await conn.run_sync(_add_cols)


def test_masterplace_security_and_authorization():
    async def _run():
        await init_tables()
        u_id = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as db:
            # Create normal customer user
            normal_user = User(
                email=f"cust_{u_id}@example.com",
                full_name="Normal Customer",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=False,
                platform_role=None
            )
            # Create platform operator user
            admin_user = User(
                email=f"admin_{u_id}@example.com",
                full_name="Platform Operator",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=True,
                platform_role="super_admin"
            )
            db.add_all([normal_user, admin_user])
            await db.commit()
            await db.refresh(normal_user)
            await db.refresh(admin_user)

            normal_token = create_access_token(subject=normal_user.id)
            admin_token = create_access_token(subject=admin_user.id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Unauthenticated request should return 401
            res_unauth = await client.get("/api/v1/masterplace/overview")
            assert res_unauth.status_code == 401

            # 2. Normal customer should receive 403 Forbidden
            res_cust = await client.get(
                "/api/v1/masterplace/overview",
                headers={"Authorization": f"Bearer {normal_token}"}
            )
            assert res_cust.status_code == 403
            assert "MasterPlace platform operator privileges required" in res_cust.json()["detail"]

            # 3. Platform Admin should receive 200 OK
            res_admin = await client.get(
                "/api/v1/masterplace/overview",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert res_admin.status_code == 200
            data = res_admin.json()
            assert "kpis" in data
            assert "system_health" in data
            assert "alerts" in data
            assert data["kpis"]["global_ai_enabled"] is True

    asyncio.run(_run())


def test_masterplace_customer_lifecycle_and_audit():
    async def _run():
        await init_tables()
        u_id = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as db:
            # Create test admin
            admin = User(
                email=f"super_admin_{u_id}@example.com",
                full_name="Super Admin",
                hashed_password=get_password_hash("pass"),
                is_active=True,
                is_superuser=True,
                platform_role="super_admin"
            )
            # Create test customer organization
            org = Organization(
                name=f"Alpha Corp Client {u_id}",
                slug=f"alpha-corp-{u_id}",
                plan="agency_pro",
                status="active"
            )
            db.add_all([admin, org])
            await db.commit()
            await db.refresh(admin)
            await db.refresh(org)

            admin_token = create_access_token(subject=admin.id)
            org_id = org.id

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {admin_token}"}

            # 1. List customers
            res_list = await client.get("/api/v1/masterplace/customers", headers=headers)
            assert res_list.status_code == 200
            items = res_list.json()["items"]
            assert any(item["name"] == f"Alpha Corp Client {u_id}" for item in items)

            # 2. Customer 360
            res_360 = await client.get(f"/api/v1/masterplace/customers/{org_id}", headers=headers)
            assert res_360.status_code == 200
            assert res_360.json()["customer"]["id"] == org_id
            assert res_360.json()["customer"]["status"] == "active"

            # 3. Suspend Customer
            res_suspend = await client.post(
                f"/api/v1/masterplace/customers/{org_id}/status",
                headers=headers,
                json={"status": "suspended", "reason": "Test suspension from unit test"}
            )
            assert res_suspend.status_code == 200
            assert res_suspend.json()["new_status"] == "suspended"

            # 4. Verify in DB and Audit Log
            async with AsyncSessionLocal() as db:
                updated_org = await db.get(Organization, org_id)
                assert updated_org.status == "suspended"

                audit_res = await db.execute(
                    select(PlatformAuditLog).where(
                        PlatformAuditLog.action == "CUSTOMER_STATUS_CHANGED",
                        PlatformAuditLog.target_id == str(org_id)
                    )
                )
                audit = audit_res.scalars().first()
                assert audit is not None
                assert audit.before_state == {"status": "active"}
                assert audit.after_state == {"status": "suspended"}

    asyncio.run(_run())


def test_masterplace_global_ai_kill_switch():
    async def _run():
        await init_tables()
        u_id = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as db:
            admin = User(
                email=f"ai_admin_{u_id}@example.com",
                full_name="AI Super Admin",
                hashed_password=get_password_hash("pass"),
                is_active=True,
                is_superuser=True,
                platform_role="super_admin"
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            admin_token = create_access_token(subject=admin.id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {admin_token}"}

            # 1. Check AI Center
            res_ai = await client.get("/api/v1/masterplace/ai", headers=headers)
            assert res_ai.status_code == 200
            assert res_ai.json()["global_ai_enabled"] is True

            # 2. Engage Kill Switch
            res_kill = await client.post(
                "/api/v1/masterplace/ai/kill-switch",
                headers=headers,
                json={"enabled": False, "reason": "Emergency runaway token spike detected"}
            )
            assert res_kill.status_code == 200
            assert res_kill.json()["global_ai_enabled"] is False

            # 3. Verify SystemSetting updated
            async with AsyncSessionLocal() as db:
                setting = await db.get(SystemSetting, "global_ai_enabled")
                assert setting.value == "false"

                # Verify audit entry
                audit_res = await db.execute(
                    select(PlatformAuditLog).where(PlatformAuditLog.action == "GLOBAL_AI_KILL_SWITCH")
                )
                audit = audit_res.scalars().first()
                assert audit is not None
                assert audit.after_state == {"global_ai_enabled": False}

            # 4. Resume AI
            res_resume = await client.post(
                "/api/v1/masterplace/ai/kill-switch",
                headers=headers,
                json={"enabled": True, "reason": "System restored"}
            )
            assert res_resume.status_code == 200
            assert res_resume.json()["global_ai_enabled"] is True

    asyncio.run(_run())


def test_masterplace_job_cancellation():
    async def _run():
        await init_tables()
        u_id = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as db:
            admin = User(
                email=f"job_admin_{u_id}@example.com",
                full_name="Job Admin",
                hashed_password=get_password_hash("pass"),
                is_active=True,
                is_superuser=True,
                platform_role="super_admin"
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)

            job = ScanJob(
                organization_id=1,
                project_id=1,
                job_type=JobType.KEYWORD_RANK,
                status=JobStatus.RUNNING.value,
                provider="serpapi",
                total_items=30,
                processed_items=2
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

            admin_token = create_access_token(subject=admin.id)
            job_id = job.id

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {admin_token}"}

            # Cancel job
            res_cancel = await client.post(f"/api/v1/masterplace/jobs/{job_id}/cancel", headers=headers)
            assert res_cancel.status_code == 200
            assert res_cancel.json()["status"] == JobStatus.CANCEL_REQUESTED.value

            # Verify DB
            async with AsyncSessionLocal() as db:
                refreshed_job = await db.get(ScanJob, job_id)
                assert refreshed_job.status == JobStatus.CANCEL_REQUESTED.value
                assert refreshed_job.cancelled_at is not None

    asyncio.run(_run())
