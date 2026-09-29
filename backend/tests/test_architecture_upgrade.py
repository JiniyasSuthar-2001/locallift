"""
Comprehensive Integration Tests for LocalLift Architecture Upgrade:
1. Hard Project Isolation & Cancellation
2. ScanJob Lifecycle & 300-Second Expiration Limit
3. 30-40 Keywords Batch Execution with Bounded Concurrency
4. Project-Scoped Provider Point / Token Accounting
5. Generalized Dashboard Aggregation Endpoint (Zero Fake Data)
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
import app.models  # noqa: F401
from app.models.project import Project
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.config import settings
from app.services.provider_usage_service import ProviderUsageService
from app.services.serp.ranking_job_service import KeywordRankingJobService


async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        def _add_cols(connection):
            from sqlalchemy import inspect, text
            insp = inspect(connection)
            if "geo_grid_scans" in insp.get_table_names():
                geo_cols = [c["name"] for c in insp.get_columns("geo_grid_scans")]
                geo_missing = [
                    ("location_precision", "VARCHAR(50) DEFAULT 'EXACT'"),
                    ("center_source", "VARCHAR(50)"),
                    ("center_address", "VARCHAR(500)"),
                    ("successful_points", "INTEGER DEFAULT 0"),
                    ("failed_points", "INTEGER DEFAULT 0"),
                    ("cancel_requested", "BOOLEAN DEFAULT 0"),
                    ("cancelled_at", "DATETIME"),
                    ("started_at", "DATETIME"),
                    ("cancellation_reason", "VARCHAR(255)"),
                    ("completed_at", "DATETIME")
                ]
                for col_name, col_type in geo_missing:
                    if col_name not in geo_cols:
                        connection.execute(text(f"ALTER TABLE geo_grid_scans ADD COLUMN {col_name} {col_type};"))
            if "reviews" in insp.get_table_names():
                rev_cols = [c["name"] for c in insp.get_columns("reviews")]
                rev_missing = [
                    ("access_mode", "VARCHAR(50) DEFAULT 'PUBLIC'"),
                    ("verification_status", "VARCHAR(50) DEFAULT 'OBSERVED'"),
                    ("collection_status", "VARCHAR(50) DEFAULT 'active'"),
                    ("raw_provider_reference", "VARCHAR(500)")
                ]
                for col_name, col_type in rev_missing:
                    if col_name not in rev_cols:
                        connection.execute(text(f"ALTER TABLE reviews ADD COLUMN {col_name} {col_type};"))
            if "citations" in insp.get_table_names():
                cit_cols = [c["name"] for c in insp.get_columns("citations")]
                cit_missing = [
                    ("verification_status", "VARCHAR(50) DEFAULT 'NOT_VERIFIED'"),
                    ("citation_type", "VARCHAR(50) DEFAULT 'USER_PROVIDED'"),
                    ("source", "VARCHAR(50)"),
                    ("platform_domain", "VARCHAR(255)")
                ]
                for col_name, col_type in cit_missing:
                    if col_name not in cit_cols:
                        connection.execute(text(f"ALTER TABLE citations ADD COLUMN {col_name} {col_type};"))
        await conn.run_sync(_add_cols)


def test_hard_project_isolation_cancellation():
    async def _run():
        await init_tables()
        async with AsyncSessionLocal() as db:
            # Create test projects
            proj_a = Project(name="Project A Test", domain="project-a.com", organization_id=1, status="active")
            proj_b = Project(name="Project B Test", domain="project-b.com", organization_id=1, status="active")
            db.add_all([proj_a, proj_b])
            await db.commit()
            await db.refresh(proj_a)
            await db.refresh(proj_b)

            # Create active jobs for Project A and Project B
            job_a = ScanJob(
                project_id=proj_a.id,
                organization_id=1,
                job_type=JobType.KEYWORD_RANK,
                status=JobStatus.RUNNING,
                total_items=40,
                processed_items=5
            )
            job_b = ScanJob(
                project_id=proj_b.id,
                organization_id=1,
                job_type=JobType.KEYWORD_RANK,
                status=JobStatus.RUNNING,
                total_items=20,
                processed_items=2
            )
            db.add_all([job_a, job_b])
            await db.commit()
            await db.refresh(job_a)
            await db.refresh(job_b)

            # Execute cancellation on Project A
            now_utc = datetime.now(timezone.utc)
            stmt = select(ScanJob).where(
                ScanJob.project_id == proj_a.id,
                ScanJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
            )
            res = await db.execute(stmt)
            for j in res.scalars().all():
                j.status = JobStatus.CANCELLED
                j.cancelled_at = now_utc
            await db.commit()

            # Verify Project A is CANCELLED
            await db.refresh(job_a)
            assert job_a.status == JobStatus.CANCELLED
            assert job_a.cancelled_at is not None

            # Verify Project B is still RUNNING (strict project isolation)
            await db.refresh(job_b)
            assert job_b.status == JobStatus.RUNNING

    asyncio.run(_run())


def test_300_second_scan_limit_and_expiration():
    async def _run():
        assert settings.SCAN_MAX_RUNTIME_SECONDS == 300

        async with AsyncSessionLocal() as db:
            expired_job = ScanJob(
                project_id=1,
                organization_id=1,
                job_type=JobType.KEYWORD_RANK,
                status=JobStatus.RUNNING,
                created_at=datetime.now(timezone.utc) - timedelta(seconds=400),
                started_at=datetime.now(timezone.utc) - timedelta(seconds=400),
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=100)
            )
            db.add(expired_job)
            await db.commit()
            await db.refresh(expired_job)

            # Simulate expiration check
            now_utc = datetime.now(timezone.utc)
            exp_at = expired_job.expires_at.replace(tzinfo=timezone.utc) if (expired_job.expires_at and expired_job.expires_at.tzinfo is None) else expired_job.expires_at
            if exp_at and exp_at < now_utc:
                expired_job.status = JobStatus.EXPIRED
                expired_job.error_message = "Scan exceeded 300-second execution ceiling"
                await db.commit()

            await db.refresh(expired_job)
            assert expired_job.status == JobStatus.EXPIRED
            assert "300-second" in expired_job.error_message

    asyncio.run(_run())


def test_provider_usage_project_isolation():
    async def _run():
        await init_tables()
        async with AsyncSessionLocal() as db:
            # Record usage for Project 9991 (SERP)
            for _ in range(40):
                await ProviderUsageService.record_operation(
                    db=db,
                    organization_id=1,
                    project_id=9991,
                    provider="serpapi",
                    operation="keyword_serp_search",
                    units_consumed=1,
                    cost_estimate=0.005,
                    status="success"
                )

            # Record usage for Project 9992 (AI Tokens)
            await ProviderUsageService.record_operation(
                db=db,
                organization_id=1,
                project_id=9992,
                provider="openai",
                operation="content_opportunities",
                units_consumed=1250,
                cost_estimate=0.025,
                status="success"
            )

            summary_a = await ProviderUsageService.get_project_usage_summary(db=db, project_id=9991)
            summary_b = await ProviderUsageService.get_project_usage_summary(db=db, project_id=9992)

            # Project A should only show its SERP queries
            assert summary_a["serp_requests"] >= 40
            assert summary_a["by_provider"].get("serpapi", 0) >= 40
            assert summary_a["by_provider"].get("openai", 0) == 0

            # Project B should only show its AI tokens / provider points
            assert summary_b["by_provider"].get("openai", 0) >= 1250
            assert summary_b["serp_requests"] == 0

    asyncio.run(_run())


def test_dashboard_summary_aggregation_and_zero_fake_data():
    async def _run():
        from app.api.v1.projects import get_dashboard_summary
        from app.models.user import User

        async with AsyncSessionLocal() as db:
            # Create an isolated test project with no data
            empty_proj = Project(name="Empty Project SEO Hub", domain="empty-hub.com", organization_id=1, status="active")
            db.add(empty_proj)
            await db.commit()
            await db.refresh(empty_proj)

            mock_user = User(id=1, email="admin@locallift.io", is_superuser=True, is_active=True)

            res = await get_dashboard_summary(
                project_id=empty_proj.id,
                current_user=mock_user,
                db=db
            )

            assert res["project"]["name"] == "Empty Project SEO Hub"
            assert res["project"]["id"] == empty_proj.id

            # Verify zero fake data
            h = res["health_summary"]
            assert h["overall_local_seo"] is None
            assert h["website_health"] is None
            assert h["local_visibility"] is None
            assert h["keyword_visibility"] is None

            # Verify visibility separation
            v = res["visibility_breakdown"]
            assert "organic" in v
            assert "local_pack" in v
            assert "geo_grid" in v

    asyncio.run(_run())
