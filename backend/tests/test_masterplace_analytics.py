import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from app.database import AsyncSessionLocal
from app.models.user import User, Organization
from app.models.project import Project, Website
from app.models.scan_job import ScanJob, JobStatus
from app.models.provider_usage import ProviderUsageRecord
from app.models.ai_control import AIUsageLog
from app.models.platform_audit import PlatformAuditLog
from app.services.masterplace_analytics_service import MasterPlaceAnalyticsService


def test_masterplace_analytics_ranges_and_empty_state():
    """
    Verifies that MasterPlaceAnalyticsService generates all standard range intervals
    and correctly handles empty / zero-state datasets without crashing.
    """
    async def _run():
        async with AsyncSessionLocal() as db:
            # 1. Test 30d range
            res_30d = await MasterPlaceAnalyticsService.get_analytics_overview(db, range_str="30d")
            assert "time_series" in res_30d
            assert "kpis" in res_30d
            assert "customer_growth" in res_30d["time_series"]
            assert "scan_activity" in res_30d["time_series"]
            assert "google_api_usage" in res_30d["time_series"]
            assert "serp_usage" in res_30d["time_series"]
            assert "ai_token_usage" in res_30d["time_series"]

            # 2. Test 7d range
            res_7d = await MasterPlaceAnalyticsService.get_analytics_overview(db, range_str="7d")
            assert len(res_7d["time_series"]["customer_growth"]) == 7

            # 3. Test today range
            res_today = await MasterPlaceAnalyticsService.get_analytics_overview(db, range_str="today")
            assert len(res_today["time_series"]["customer_growth"]) == 24

    asyncio.run(_run())


def test_masterplace_analytics_aggregation_with_real_records():
    """
    Verifies that real ScanJob, ProviderUsageRecord, and AIUsageLog records
    are aggregated accurately into time buckets and tenant rankings.
    """
    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            # Create isolated test org & project
            test_org = Organization(name="Analytics Corp", slug=f"analytics-corp-{int(now.timestamp())}", status="active")
            db.add(test_org)
            await db.commit()
            await db.refresh(test_org)

            test_proj = Project(name="Analytics Site", domain="analytics-corp.com", organization_id=test_org.id, status="active")
            db.add(test_proj)
            await db.commit()
            await db.refresh(test_proj)

            test_web = Website(url="https://analytics-corp.com", project_id=test_proj.id)
            db.add(test_web)
            await db.commit()
            await db.refresh(test_web)

            # Add ScanJob
            job = ScanJob(
                organization_id=test_org.id,
                project_id=test_proj.id,
                job_type="keyword_rank",
                status=JobStatus.COMPLETED.value,
                processed_items=10,
                total_items=10,
                started_at=now - timedelta(days=2, seconds=42),
                completed_at=now - timedelta(days=2),
                created_at=now - timedelta(days=2)
            )
            db.add(job)

            # Add ProviderUsageRecord (SERP)
            serp_usage = ProviderUsageRecord(
                organization_id=test_org.id,
                project_id=test_proj.id,
                provider="serpapi",
                operation="keyword_search",
                units_consumed=15,
                cost_estimate=0.15,
                status="success",
                created_at=now - timedelta(days=2)
            )
            db.add(serp_usage)

            # Add ProviderUsageRecord (Google)
            google_usage = ProviderUsageRecord(
                organization_id=test_org.id,
                project_id=test_proj.id,
                provider="google_places",
                operation="places_search",
                units_consumed=5,
                cost_estimate=0.08,
                status="success",
                created_at=now - timedelta(days=1)
            )
            db.add(google_usage)

            # Add AIUsageLog
            ai_log = AIUsageLog(
                organization_id=test_org.id,
                project_id=test_proj.id,
                provider="gemini",
                task_type="diagnostic",
                input_tokens=1200,
                output_tokens=600,
                total_tokens=1800,
                estimated_cost=0.0036,
                status="success",
                created_at=now - timedelta(days=1)
            )
            db.add(ai_log)

            await db.commit()

            # Query analytics for this customer
            res = await MasterPlaceAnalyticsService.get_analytics_overview(
                db=db,
                range_str="7d",
                customer_id=test_org.id
            )

            # Verify KPIs
            kpis = res["kpis"]
            assert kpis["total_scans"] >= 1
            assert kpis["total_serp_requests"] >= 15
            assert kpis["total_ai_tokens"] >= 1800
            assert kpis["total_google_requests"] >= 5

            # Verify Top Customers ranking includes test_org
            top_custs = res["top_customers_usage"]
            matched_cust = next((c for c in top_custs if c["id"] == test_org.id), None)
            assert matched_cust is not None
            assert matched_cust["serp_requests"] >= 15
            assert matched_cust["ai_tokens"] >= 1800
            assert matched_cust["google_requests"] >= 5

            # Verify AI Provider breakdown includes gemini
            ai_provs = res["ai_provider_comparison"]
            gemini_prov = next((p for p in ai_provs if p["provider"] == "gemini"), None)
            assert gemini_prov is not None
            assert gemini_prov["total_tokens"] >= 1800

    asyncio.run(_run())
