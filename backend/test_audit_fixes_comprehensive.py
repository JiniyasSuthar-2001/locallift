import asyncio
import os
import sys
from datetime import datetime, timezone

from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.project import Project
from app.models.user import User, Organization
from app.models.connections import GoogleConnection, GoogleSearchConsoleProperty, GoogleAnalyticsProperty
from app.models.analytics import GSCMetric, GA4Metric, ScheduledJob
from app.services.seo_auditor import SEOAuditor
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.gsc_client import GoogleSearchConsoleClient
from app.services.google.ga4_client import GoogleAnalytics4Client
from app.services.scheduler import JobSchedulerService


async def run_audit_fixes_verification():
    print("==================================================")
    print("STARTING AUDIT FIXES COMPREHENSIVE VERIFICATION")
    print("==================================================")

    async with AsyncSessionLocal() as db:
        # TEST 1: SEO Pillar Weights Sum to Exactly 100%
        print("\n[TEST 1] Verifying SEO Auditor Pillar Weights...")
        weights = SEOAuditor.PILLAR_WEIGHTS
        total_weight = sum(weights.values())
        print(f"  Pillar weights: {weights}")
        print(f"  Total weight sum: {total_weight}%")
        assert total_weight == 100, f"Pillar weights must sum to 100%, got {total_weight}"
        assert weights["crawl_health"] == 20
        assert weights["onpage_seo"] == 20
        assert weights["schema_local"] == 25
        assert weights["gbp_status"] == 15
        assert weights["citations_presence"] == 10
        assert weights["reviews_rating"] == 10
        print("  [PASS] Pillar weights correctly configured and sum to 100%!")

        # TEST 2: GSC Property Model & Project ID Foreign Key
        print("\n[TEST 2] Verifying GSC & GA4 Property DB Models...")
        # Create a test project
        org_res = await db.execute(select(Organization))
        org = org_res.scalars().first()
        if not org:
            org = Organization(name="Test Org")
            db.add(org)
            await db.flush()

        proj = Project(
            organization_id=org.id,
            name=f"Audit Test {int(datetime.now().timestamp())}",
            domain=f"audit-test-{int(datetime.now().timestamp())}.com"
        )
        db.add(proj)
        await db.flush()

        # Add GoogleConnection
        conn = GoogleConnection(
            organization_id=org.id,
            service="search_console",
            status="connected",
            account_email="test@example.com",
            access_token="encrypted_test_token"
        )
        db.add(conn)
        await db.flush()

        # Map GSC Property
        gsc_prop = GoogleSearchConsoleProperty(
            connection_id=conn.id,
            project_id=proj.id,
            site_url=f"sc-domain:{proj.domain}",
            permission_level="siteOwner",
            is_linked=True
        )
        db.add(gsc_prop)

        # Map GA4 Property
        ga4_prop = GoogleAnalyticsProperty(
            connection_id=conn.id,
            project_id=proj.id,
            property_id="properties/123456789",
            display_name="Audit Test GA4",
            account_name="Audit Test Account",
            is_linked=True
        )
        db.add(ga4_prop)
        await db.commit()

        # Verify mapping query
        res_gsc = await db.execute(
            select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.project_id == proj.id)
        )
        mapped_gsc = res_gsc.scalars().first()
        assert mapped_gsc is not None
        assert mapped_gsc.site_url == f"sc-domain:{proj.domain}"
        print(f"  [PASS] Successfully mapped GSC property to project {proj.id} (site_url: {mapped_gsc.site_url})")

        res_ga4 = await db.execute(
            select(GoogleAnalyticsProperty).where(GoogleAnalyticsProperty.project_id == proj.id)
        )
        mapped_ga4 = res_ga4.scalars().first()
        assert mapped_ga4 is not None
        assert mapped_ga4.property_id == "properties/123456789"
        print(f"  [PASS] Successfully mapped GA4 property to project {proj.id} (property_id: {mapped_ga4.property_id})")

        # TEST 3: ScheduledJob Creation, Frequency Calculation, and Execution
        print("\n[TEST 3] Verifying Background Scheduler Job Execution...")
        from app.services.scheduler import JobSchedulerService
        
        job = ScheduledJob(
            project_id=proj.id,
            job_type="rank_check",
            frequency="daily",
            status="idle"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        exec_res = await JobSchedulerService.execute_job(job.id, db)
        assert exec_res["status"] == "completed"
        print(f"  [PASS] Scheduled job {job.id} executed successfully: {exec_res['last_result_summary']}")

        # Verify job was marked completed with next_run_at populated
        await db.refresh(job)
        assert job.status == "completed"
        assert job.last_run_at is not None
        assert job.next_run_at is not None
        print(f"  [PASS] Job status={job.status}, last_run={job.last_run_at.isoformat()}, next_run={job.next_run_at.isoformat()}")

        # Clean up test project
        await db.delete(job)
        await db.delete(gsc_prop)
        await db.delete(ga4_prop)
        await db.delete(conn)
        await db.delete(proj)
        await db.commit()

    print("\n==================================================")
    print("ALL AUDIT FIXES VERIFICATION TESTS PASSED! (3/3)")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_audit_fixes_verification())
