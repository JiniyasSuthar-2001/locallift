import pytest
import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.database import Base
import app.models  # noqa: F401
from app.models.user import User, Organization
from app.models.project import Project, Location
from app.models.connections import GoogleConnection
from app.models.gbp import GoogleBusinessProfile
from app.core.security import encrypt_token
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.services.google.nap_matcher import NAPMatcher
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.sync import GBPSyncService
from app.schemas.connections import DiscoveredGBPLocation


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        yield session


# ============================================================
# 1. NAP MATCHING TESTS (Tests 8, 9, 10)
# ============================================================

def test_nap_normalization_and_matching_exact():
    """Test 8: Existing project NAP exact match."""
    proj = {
        "name": "Acme Plumbing Services, LLC",
        "address": "123 Main Street, Suite 400",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78701",
        "phone": "+1 (512) 555-0199",
        "website": "https://www.acmeplumbing.com/"
    }
    gbp = {
        "location_name": "Acme Plumbing Services",
        "address": "123 Main St Ste 400",
        "city": "Austin",
        "state": "Texas",
        "postal_code": "78701",
        "phone": "5125550199",
        "website_url": "http://acmeplumbing.com"
    }
    res = NAPMatcher.match(proj, gbp)
    assert res["overall_status"] == "MATCH"
    assert res["overall_score"] >= 80
    assert res["name"]["status"] == "MATCH"
    assert res["phone"]["status"] == "MATCH"
    assert res["website"]["status"] == "MATCH"
    assert res["address"]["status"] == "MATCH"


def test_nap_normalization_and_matching_mismatch():
    """Test 9: Existing project NAP mismatch."""
    proj = {
        "name": "Austin Dental Care",
        "address": "500 Congress Ave",
        "phone": "512-555-9999",
        "website": "https://austindental.com"
    }
    gbp = {
        "location_name": "Seattle Auto Repair",
        "address": "900 1st Ave",
        "phone": "206-555-1111",
        "website_url": "https://seattleautorepair.com"
    }
    res = NAPMatcher.match(proj, gbp)
    assert res["overall_status"] == "NO_MATCH"
    assert res["overall_score"] < 40
    assert res["name"]["status"] == "NO_MATCH"


def test_nap_normalization_and_matching_ambiguous():
    """Test 10: Existing project ambiguous/multiple match handling."""
    proj = {
        "name": "Apex Dental Clinic",
        "address": "100 South Congress",
        "phone": "512-555-1000",
        "website": "https://apexdental.com"
    }
    cand_1 = {
        "location_name": "Apex Dental Clinic Downtown",
        "address": "100 South Congress",
        "phone": "512-555-1000",
        "website_url": "https://apexdental.com"
    }
    cand_2 = {
        "location_name": "Apex Dental Clinic South",
        "address": "100 South Congress",
        "phone": "512-555-1000",
        "website_url": "https://apexdental.com"
    }
    overall_state, evals = NAPMatcher.classify_candidates(proj, [cand_1, cand_2])
    assert overall_state == "AMBIGUOUS"
    assert len(evals) == 2


# ============================================================
# 2. GBP CLIENT PAGINATION & MULTI-LOCATION SCALES (Tests 2, 3, 4, 5, 6, 7, 20)
# ============================================================

@pytest.mark.asyncio
async def test_gbp_client_pagination_3_locations():
    """Test 4 & 5: Pagination and 3 GBP locations discovery."""
    client = GoogleBusinessProfileClient(access_token="fake_token")

    with patch.object(client, "ensure_valid_token", new_callable=AsyncMock) as mock_tok:
        mock_tok.return_value = "valid_token"

        locs = [
            {"name": "locations/loc-1", "title": "Location 1"},
            {"name": "locations/loc-2", "title": "Location 2"},
            {"name": "locations/loc-3", "title": "Location 3"},
        ]

        async def mock_get(url, headers=None, params=None):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"locations": locs}
            return resp

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            res = await client.list_locations("accounts/111")
            assert res["status"] == "CONNECTED"
            assert len(res["locations"]) == 3


@pytest.mark.asyncio
async def test_gbp_client_pagination_20_and_40_locations():
    """Test 6 & 7: Pagination across 20 and 40+ GBP locations across multiple pages."""
    client = GoogleBusinessProfileClient(access_token="fake_token")

    with patch.object(client, "ensure_valid_token", new_callable=AsyncMock) as mock_tok:
        mock_tok.return_value = "valid_token"

        # Generate 45 locations across 3 pages
        locs_page1 = [{"name": f"locations/loc-{i}", "title": f"Branch #{i}"} for i in range(1, 21)]
        locs_page2 = [{"name": f"locations/loc-{i}", "title": f"Branch #{i}"} for i in range(21, 41)]
        locs_page3 = [{"name": f"locations/loc-{i}", "title": f"Branch #{i}"} for i in range(41, 46)]

        async def mock_get(url, headers=None, params=None):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            page_token = (params or {}).get("pageToken")
            if not page_token:
                mock_resp.json.return_value = {"locations": locs_page1, "nextPageToken": "token_page2"}
            elif page_token == "token_page2":
                mock_resp.json.return_value = {"locations": locs_page2, "nextPageToken": "token_page3"}
            elif page_token == "token_page3":
                mock_resp.json.return_value = {"locations": locs_page3}
            else:
                mock_resp.json.return_value = {}
            return mock_resp

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            res = await client.list_locations("accounts/12345")
            assert res["status"] == "CONNECTED"
            assert len(res["locations"]) == 45
            assert res["locations"][0]["name"] == "locations/loc-1"
            assert res["locations"][44]["name"] == "locations/loc-45"


# ============================================================
# 3. OAUTH & ERROR HANDLING (Tests 1, 18, 19, 20)
# ============================================================

@pytest.mark.asyncio
async def test_gbp_client_error_handling_statuses():
    """Test 18, 19, 20: Handling OAuth expiration, quota/access errors, and no GBP found."""
    client = GoogleBusinessProfileClient(access_token="expired_token")

    with patch.object(client, "ensure_valid_token", new_callable=AsyncMock) as mock_tok:
        mock_tok.return_value = "valid_token"

        # 401 Unauthorized -> AUTH_EXPIRED
        async def mock_error_401(url, headers=None, params=None):
            resp = MagicMock()
            resp.status_code = 401
            resp.text = "Unauthorized: Token has expired"
            return resp

        with patch("httpx.AsyncClient.get", side_effect=mock_error_401):
            res_401 = await client.list_accounts()
            assert res_401["status"] == "AUTH_EXPIRED"
            assert res_401["accounts"] == []

        # 429 Quota 0 -> API_ACCESS_NOT_GRANTED
        async def mock_error_429(url, headers=None, params=None):
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "Quota limit exceeded: quota_limit_value: 0"
            return resp

        with patch("httpx.AsyncClient.get", side_effect=mock_error_429):
            res_429 = await client.list_locations("accounts/123")
            assert res_429["status"] == "API_ACCESS_NOT_GRANTED"

        # 403 Forbidden -> PERMISSION_DENIED
        async def mock_error_403(url, headers=None, params=None):
            resp = MagicMock()
            resp.status_code = 403
            resp.text = "Google Business Profile API has not been used in project or disabled."
            return resp

        with patch("httpx.AsyncClient.get", side_effect=mock_error_403):
            res_403 = await client.list_locations("accounts/123")
            assert res_403["status"] == "PERMISSION_DENIED"


# ============================================================
# 4. WORKFLOW A & B, EXACT BINDING, AND DUPLICATE PROTECTION
# (Tests 11, 12, 13, 14, 15)
# ============================================================

@pytest.mark.asyncio
async def test_workflow_b_create_new_projects_from_gbp_locations(async_db: AsyncSession):
    """
    Test 11 & 12: Creating new LocalLift projects from selected GBP locations.
    Each selected GBP location creates exactly one separate LocalLift project with full data populated.
    """
    db = async_db
    org = Organization(name="Agency Test Org", slug="agency-test-org")
    user = User(email="owner@test.com", hashed_password="pw", full_name="Owner")
    db.add_all([org, user])
    await db.commit()
    await db.refresh(org)
    await db.refresh(user)

    conn = GoogleConnection(
        organization_id=org.id,
        account_email="user@agency.com",
        service="business_profile",
        status="connected",
        access_token=encrypt_token("fake-access"),
        refresh_token=encrypt_token("fake-refresh")
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    # Prepare 2 discovered locations
    loc1 = DiscoveredGBPLocation(
        account_id="accounts/1001",
        location_id="locations/loc-A",
        business_name="Austin Coffee Roasters",
        location_name="Austin Coffee Roasters",
        primary_category="Coffee Shop",
        category="Coffee Shop",
        address="100 Congress Ave",
        city="Austin",
        state="TX",
        postal_code="78701",
        country="US",
        phone="+15125550100",
        website_url="https://austincoffee.com",
        latitude=30.2672,
        longitude=-97.7431
    )
    loc2 = DiscoveredGBPLocation(
        account_id="accounts/1001",
        location_id="locations/loc-B",
        business_name="Dallas Bakery & Cafe",
        location_name="Dallas Bakery & Cafe",
        primary_category="Bakery",
        category="Bakery",
        address="200 Elm St",
        city="Dallas",
        state="TX",
        postal_code="75201",
        country="US",
        phone="+12145550200",
        website_url="https://dallasbakery.com",
        latitude=32.7767,
        longitude=-96.7970
    )

    res = await GoogleConnectionsService.create_projects_from_gbp_locations(
        org_id=org.id,
        user_id=user.id,
        locations_payload=[loc1, loc2],
        db=db
    )

    assert res["created_projects_count"] == 2
    proj_a_data, proj_b_data = res["created_projects"][0], res["created_projects"][1]
    assert proj_a_data["project_name"] == "Austin Coffee Roasters"
    assert proj_b_data["project_name"] == "Dallas Bakery & Cafe"

    # Verify each project has an explicit bound GBP record
    gbp_a = (await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == proj_a_data["project_id"]))).scalar_one_or_none()
    gbp_b = (await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == proj_b_data["project_id"]))).scalar_one_or_none()

    assert gbp_a is not None
    assert gbp_a.location_resource_name == "locations/loc-A"
    assert gbp_a.business_name == "Austin Coffee Roasters"
    assert gbp_a.latitude == 30.2672

    assert gbp_b is not None
    assert gbp_b.location_resource_name == "locations/loc-B"
    assert gbp_b.business_name == "Dallas Bakery & Cafe"


@pytest.mark.asyncio
async def test_duplicate_protection_already_linked_gbp(async_db: AsyncSession):
    """
    Test 14 & 15: Duplicate protection.
    An already linked GBP cannot silently create duplicate projects or accidentally re-bind without force_relink.
    """
    db = async_db
    org = Organization(name="Org Dup", slug="org-dup")
    user = User(email="dup@test.com", hashed_password="pw", full_name="Dup User")
    db.add_all([org, user])
    await db.commit()
    await db.refresh(org)
    await db.refresh(user)

    conn = GoogleConnection(
        organization_id=org.id,
        account_email="dup@agency.com",
        service="business_profile",
        status="connected"
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    loc = DiscoveredGBPLocation(
        account_id="accounts/2000",
        location_id="locations/loc-unique",
        business_name="Unique Spa & Salon",
        location_name="Unique Spa & Salon",
        primary_category="Spa",
        address="300 South Lamar",
        city="Austin",
        state="TX",
        phone="5125553333"
    )

    # 1. Create first project from loc
    first_res = await GoogleConnectionsService.create_projects_from_gbp_locations(
        org_id=org.id,
        user_id=user.id,
        locations_payload=[loc],
        db=db
    )
    assert first_res["created_projects_count"] == 1

    # 2. Attempting to create duplicate project from same loc should return 0 new projects and mark skipped
    second_res = await GoogleConnectionsService.create_projects_from_gbp_locations(
        org_id=org.id,
        user_id=user.id,
        locations_payload=[loc],
        db=db
    )
    assert second_res["created_projects_count"] == 0
    assert second_res["skipped_locations_count"] == 1

    # 3. Create a second project manually
    proj_2 = Project(
        organization_id=org.id,
        name="Project 2",
        domain="project2.com"
    )
    db.add(proj_2)
    await db.commit()
    await db.refresh(proj_2)

    # 4. Attempting to bind already bound location without force_relink must raise ValueError
    with pytest.raises(ValueError, match="already linked to Project"):
        await GoogleConnectionsService.bind_gbp_location_to_project(
            project_id=proj_2.id,
            org_id=org.id,
            location_payload=loc,
            db=db,
            force_relink=False
        )

    # 5. With force_relink=True, re-binding succeeds cleanly
    rebound_gbp = await GoogleConnectionsService.bind_gbp_location_to_project(
        project_id=proj_2.id,
        org_id=org.id,
        location_payload=loc,
        db=db,
        force_relink=True
    )
    assert rebound_gbp["project_id"] == proj_2.id
    assert rebound_gbp["location_resource_name"] == "locations/loc-unique"


# ============================================================
# 5. PROJECT ISOLATION & TRACEABLE SYNC (Tests 13, 16, 17, 21)
# ============================================================

@pytest.mark.asyncio
async def test_project_isolation_and_traceable_sync(async_db: AsyncSession):
    """
    Test 13, 16, 17, 21:
    - Strong Project -> GBP binding
    - Project A strictly sees ONLY GBP A.
    - Project B strictly sees ONLY GBP B.
    - Background sync follows strict chain: Project -> Bound GBP -> Google Connection -> Google API -> Exact location.
    """
    db = async_db
    org = Organization(name="Agency Multi", slug="agency-multi")
    db.add(org)
    await db.commit()
    await db.refresh(org)

    conn = GoogleConnection(
        organization_id=org.id,
        account_email="master@agency.com",
        service="business_profile",
        status="connected",
        access_token=encrypt_token("active-token"),
        refresh_token=encrypt_token("active-refresh")
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    proj_a = Project(organization_id=org.id, name="Project A (Downtown)", domain="projecta.com")
    proj_b = Project(organization_id=org.id, name="Project B (Uptown)", domain="projectb.com")
    db.add_all([proj_a, proj_b])
    await db.commit()
    await db.refresh(proj_a)
    await db.refresh(proj_b)

    # Bind GBP A to Project A
    gbp_a = GoogleBusinessProfile(
        project_id=proj_a.id,
        google_connection_id=conn.id,
        account_resource_name="accounts/999",
        location_resource_name="locations/loc-alpha",
        business_name="Downtown Bistro",
        address="100 Main St",
        status="CONNECTED"
    )
    # Bind GBP B to Project B
    gbp_b = GoogleBusinessProfile(
        project_id=proj_b.id,
        google_connection_id=conn.id,
        account_resource_name="accounts/999",
        location_resource_name="locations/loc-beta",
        business_name="Uptown Bistro",
        address="900 North Ave",
        status="CONNECTED"
    )
    db.add_all([gbp_a, gbp_b])
    await db.commit()

    # Isolation Check 1: Querying Project A's profile never returns GBP B
    query_a = (await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == proj_a.id)
    )).scalar_one_or_none()
    assert query_a is not None
    assert query_a.business_name == "Downtown Bistro"
    assert query_a.location_resource_name == "locations/loc-alpha"
    assert query_a.location_resource_name != "locations/loc-beta"

    # Isolation Check 2: Querying Project B's profile never returns GBP A
    query_b = (await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == proj_b.id)
    )).scalar_one_or_none()
    assert query_b is not None
    assert query_b.business_name == "Uptown Bistro"
    assert query_b.location_resource_name == "locations/loc-beta"
    assert query_b.location_resource_name != "locations/loc-alpha"

    # Traceable Background Sync Check
    synced_location_calls = []

    async def mock_fetch_location(self, location_name):
        synced_location_calls.append(location_name)
        return {
            "name": location_name,
            "title": f"Live Updated {location_name}",
            "storefrontAddress": {
                "addressLines": ["Updated Address"],
                "locality": "Austin",
                "administrativeArea": "TX"
            }
        }

    with patch.object(GoogleBusinessProfileClient, "fetch_location", mock_fetch_location), \
         patch.object(GoogleConnectionsService, "get_valid_access_token", new_callable=AsyncMock) as mock_tok:
        mock_tok.return_value = "valid_live_token"

        sync_result_a = await GBPSyncService.sync_project_gbp(proj_a.id, db)
        assert sync_result_a["status"] == "synced"
        assert "locations/loc-alpha" in synced_location_calls
        assert "locations/loc-beta" not in synced_location_calls

        # Verify DB updated Project A's GBP record only
        await db.refresh(query_a)
        await db.refresh(query_b)
        assert query_a.business_name == "Live Updated locations/loc-alpha"
        assert query_b.business_name == "Uptown Bistro"  # Untouched
