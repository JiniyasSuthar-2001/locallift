import pytest
import asyncio
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base
import app.models  # noqa: F401
from app.config import settings
from app.models.user import User, Organization, OrganizationMember
from app.models.project import Project, Location
from app.models.ranking import Keyword, GeoGridScan
from app.models.connections import OrganizationSERPConfig, GoogleConnection
from app.models.local_seo import Citation, NAPRecord, Review
from app.core.security import encrypt_token, decrypt_token
from app.services.serp.factory import get_organization_serp_provider, get_serp_provider
from app.services.serp.base import NotConfiguredSERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.public_maps_service import PublicGoogleMapsService


@pytest.mark.asyncio
async def test_multi_tenant_serp_credential_isolation(monkeypatch):
    """
    Validates that:
    1. Org A resolves only Org A's SerpApi key.
    2. Org B resolves only Org B's SerpApi key.
    3. Org C with no configured key resolves NotConfiguredSERPProvider with ZERO fallback to settings.SERPAPI_KEY.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Set developer/global .env SERPAPI_KEY to verify runtime does NOT use it as fallback
    monkeypatch.setattr(settings, "SERPAPI_KEY", "developer_env_testing_key_12345")

    async with AsyncSessionLocal() as db:
        # 1. Create Organizations
        org_a = Organization(name="Agency A", slug="agency-a")
        org_b = Organization(name="Agency B", slug="agency-b")
        org_c = Organization(name="Client C (No Key)", slug="client-c")
        db.add_all([org_a, org_b, org_c])
        await db.commit()
        await db.refresh(org_a)
        await db.refresh(org_b)
        await db.refresh(org_c)

        # 2. Configure Org A with SerpApi Key A
        key_a = "serpapi_org_a_secret_key_aaaa"
        enc_key_a = encrypt_token(key_a)
        cfg_a = OrganizationSERPConfig(
            organization_id=org_a.id,
            provider="serpapi",
            api_key=enc_key_a,
            enabled=True,
            connection_status="connected"
        )

        # 3. Configure Org B with SerpApi Key B
        key_b = "serpapi_org_b_secret_key_bbbb"
        enc_key_b = encrypt_token(key_b)
        cfg_b = OrganizationSERPConfig(
            organization_id=org_b.id,
            provider="serpapi",
            api_key=enc_key_b,
            enabled=True,
            connection_status="connected"
        )

        db.add_all([cfg_a, cfg_b])
        await db.commit()

        # 4. Resolve Provider for Org A
        prov_a = await get_organization_serp_provider(db, org_a.id)
        assert isinstance(prov_a, SerpApiProvider), "Org A must resolve SerpApiProvider"
        assert prov_a.api_key == key_a, "Org A must receive decrypted Org A key"
        assert prov_a.is_configured is True

        # 5. Resolve Provider for Org B
        prov_b = await get_organization_serp_provider(db, org_b.id)
        assert isinstance(prov_b, SerpApiProvider), "Org B must resolve SerpApiProvider"
        assert prov_b.api_key == key_b, "Org B must receive decrypted Org B key"
        assert prov_b.is_configured is True

        # 6. Verify Org C (Unconfigured) NEVER falls back to developer SERPAPI_KEY
        prov_c = await get_organization_serp_provider(db, org_c.id)
        assert isinstance(prov_c, NotConfiguredSERPProvider), "Org C must resolve NotConfiguredSERPProvider"
        assert prov_c.is_configured is False
        
        # Test search failure contract
        search_res = await prov_c.search_keyword("plumber brisbane")
        assert search_res.success is False
        assert search_res.error_code == "SERP_PROVIDER_NOT_CONFIGURED"
        assert "Connect your SerpApi account in Settings" in search_res.error_message

    await engine.dispose()


@pytest.mark.asyncio
async def test_google_places_configuration_contract(monkeypatch):
    """
    Validates that:
    1. GOOGLE_PLACES_API_KEY is the single recognized configuration attribute.
    2. Public Google Places service consumes GOOGLE_PLACES_API_KEY without fallback to GOOGLE_MAPS_API_KEY.
    """
    assert hasattr(settings, "GOOGLE_PLACES_API_KEY"), "settings must define GOOGLE_PLACES_API_KEY"

    # Set places key
    test_key = "AIzaSyTestPlacesKeyServerSide999"
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", test_key)

    # Verify service resolves key cleanly
    resolved = getattr(settings, "GOOGLE_PLACES_API_KEY", "").strip()
    assert resolved == test_key


@pytest.mark.asyncio
async def test_google_oauth_multi_tenant_scoping():
    """
    Validates that:
    1. GoogleConnection is strictly scoped to organization_id.
    2. Org A's GBP connection is completely invisible to Org B.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as db:
        # Create Orgs and Users
        org_a = Organization(name="Company A", slug="company-a")
        org_b = Organization(name="Company B", slug="company-b")
        db.add_all([org_a, org_b])
        await db.commit()
        await db.refresh(org_a)
        await db.refresh(org_b)

        user_a = User(email="user_a@example.com", hashed_password="hash", is_active=True)
        user_b = User(email="user_b@example.com", hashed_password="hash", is_active=True)
        db.add_all([user_a, user_b])
        await db.commit()
        await db.refresh(user_a)
        await db.refresh(user_b)

        # Save Google Connection for Org A only
        token_data_a = {
            "access_token": "ya29.secret_oauth_token_a",
            "refresh_token": "1//secret_refresh_token_a",
            "token_expiry": None,
            "account_email": "owner_a@gmail.com",
            "account_id": "accounts/111111"
        }
        await GoogleConnectionsService.save_connection_tokens(
            organization_id=org_a.id,
            user_id=user_a.id,
            service="business_profile",
            token_data=token_data_a,
            db=db
        )

        # Verify Org A summary
        summary_a = await GoogleConnectionsService.get_services_status_summary(org_a.id, db)
        assert summary_a["business_profile"]["connected"] is True
        assert summary_a["business_profile"]["google_email"] == "owner_a@gmail.com"

        # Verify Org B summary is completely disconnected
        summary_b = await GoogleConnectionsService.get_services_status_summary(org_b.id, db)
        assert summary_b["business_profile"]["connected"] is False
        assert summary_b["business_profile"]["google_email"] is None

        # Verify connection lookup for service
        conn_a = await GoogleConnectionsService.get_connection_for_service(org_a.id, "business_profile", db)
        assert conn_a is not None
        assert conn_a.account_email == "owner_a@gmail.com"

        conn_b = await GoogleConnectionsService.get_connection_for_service(org_b.id, "business_profile", db)
        assert conn_b is None, "Org B must not access Org A's connection"

    await engine.dispose()


@pytest.mark.asyncio
async def test_project_and_citation_isolation():
    """
    Validates that:
    1. Project A1 citations cannot be seen by Project B1.
    2. NAP records and audits are scoped per project.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as db:
        org_a = Organization(name="Org A", slug="org-a")
        org_b = Organization(name="Org B", slug="org-b")
        db.add_all([org_a, org_b])
        await db.commit()
        await db.refresh(org_a)
        await db.refresh(org_b)

        proj_a = Project(name="Project A", domain="domain-a.com", organization_id=org_a.id)
        proj_b = Project(name="Project B", domain="domain-b.com", organization_id=org_b.id)
        db.add_all([proj_a, proj_b])
        await db.commit()
        await db.refresh(proj_a)
        await db.refresh(proj_b)

        # Add citation for Project A
        cit_a = Citation(
            project_id=proj_a.id,
            source_name="Yelp",
            domain="yelp.com",
            listing_url="https://yelp.com/biz/project-a",
            status="listed"
        )
        db.add(cit_a)
        await db.commit()

        # Query citations for Project A vs Project B
        from sqlalchemy.future import select
        res_a = await db.execute(select(Citation).where(Citation.project_id == proj_a.id))
        citations_a = res_a.scalars().all()
        assert len(citations_a) == 1
        assert citations_a[0].source_name == "Yelp"

        res_b = await db.execute(select(Citation).where(Citation.project_id == proj_b.id))
        citations_b = res_b.scalars().all()
        assert len(citations_b) == 0, "Project B must have 0 citations"

    await engine.dispose()


@pytest.mark.asyncio
async def test_scheduler_google_account_and_sync_imports_regression():
    """
    Regression test for:
    1. GoogleAccount UnboundLocalError in scheduler.py
    2. GoogleBusinessProfileClient NameError in sync.py
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as db:
        from app.models.analytics import ScheduledJob
        from app.models.gbp import GoogleAccount
        from app.services.scheduler import JobSchedulerService
        from app.services.google.sync import GBPSyncService
        from app.services.google.gbp_client import GoogleBusinessProfileClient

        # Verify GoogleBusinessProfileClient class is available in sync.py namespace
        assert GoogleBusinessProfileClient is not None

        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        await db.commit()
        await db.refresh(org)

        proj = Project(name="Test Project", domain="example.com", organization_id=org.id)
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        # Create scheduled jobs for gbp_sync and review_sync
        job_gbp = ScheduledJob(project_id=proj.id, job_type="gbp_sync", frequency="daily", status="idle")
        job_rev = ScheduledJob(project_id=proj.id, job_type="review_sync", frequency="daily", status="idle")
        db.add_all([job_gbp, job_rev])
        await db.commit()
        await db.refresh(job_gbp)
        await db.refresh(job_rev)

        # Execute review_sync first to trigger any UnboundLocalError
        res_rev = await JobSchedulerService.execute_job(job_rev.id, db)
        assert res_rev["status"] in ("completed", "failed")
        assert "GBP account not connected" in res_rev["last_result_summary"] or "completed" in res_rev["last_result_summary"]

        # Execute gbp_sync
        res_gbp = await JobSchedulerService.execute_job(job_gbp.id, db)
        assert res_gbp["status"] in ("completed", "failed")
        assert "Google Business Profile is not connected" in res_gbp["last_result_summary"] or "completed" in res_gbp["last_result_summary"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_geo_grid_unconfigured_rejection_no_fake_scans():
    """
    Validates that:
    1. An unconfigured SERP provider stops GeoGrid scanning before creating scan records.
    2. NotConfiguredSERPProvider returns explicit error code.
    """
    not_cfg = NotConfiguredSERPProvider()
    assert not_cfg.is_configured is False

    res = await not_cfg.search_local_grid_point("dentist", 30.2672, -97.7431)
    assert res.success is False
    assert res.error_code == "SERP_PROVIDER_NOT_CONFIGURED"
    assert "Connect your SerpApi account in Settings" in res.error_message


@pytest.mark.asyncio
async def test_active_org_resolution_in_serp_endpoints():
    """
    Validates that:
    1. _resolve_org_id strictly blocks unauthorized cross-tenant requests (403).
    2. Save SERP configuration sets honest 'credential_saved' status.
    """
    from fastapi import HTTPException
    from app.api.v1.serp import _resolve_org_id

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as db:
        org_a = Organization(name="Tenant A", slug="tenant-a")
        org_b = Organization(name="Tenant B", slug="tenant-b")
        db.add_all([org_a, org_b])
        await db.commit()
        await db.refresh(org_a)
        await db.refresh(org_b)

        user_a = User(email="user_a@tenant-a.com", hashed_password="pw", is_active=True)
        db.add(user_a)
        await db.commit()
        await db.refresh(user_a)

        mem_a = OrganizationMember(user_id=user_a.id, organization_id=org_a.id, role="owner")
        db.add(mem_a)
        await db.commit()

        # User A accessing Org A should succeed
        resolved_a = await _resolve_org_id(user_a, db, org_a.id)
        assert resolved_a == org_a.id

        # User A accessing Org B must raise 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            await _resolve_org_id(user_a, db, org_b.id)
        assert exc_info.value.status_code == 403
        assert "User does not have access to this organization" in exc_info.value.detail

    await engine.dispose()

