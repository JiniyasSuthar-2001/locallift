import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from app.core.security import create_access_token
from app.models.user import User, Organization, OrganizationMember
from app.models.project import Project, Location
from app.models.connections import PublicBusinessListing, GoogleConnection
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.config import settings

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def client(test_db):
    app.dependency_overrides[get_db] = lambda: test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_headers(test_db):
    user = User(email="testowner@example.com", hashed_password="pw", is_active=True, is_superuser=False)
    test_db.add(user)
    await test_db.flush()
    
    org = Organization(name="Test Agency", slug="test-agency")
    test_db.add(org)
    await test_db.flush()
    
    member = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    test_db.add(member)
    
    proj_a = Project(name="Project Alpha", domain="alpha.com", organization_id=org.id, country="Australia")
    proj_b = Project(name="Project Beta", domain="beta.com", organization_id=org.id, country="Australia")
    test_db.add_all([proj_a, proj_b])
    await test_db.commit()
    await test_db.refresh(user)
    await test_db.refresh(proj_a)
    await test_db.refresh(proj_b)
    
    token = create_access_token(subject=user.id)
    orig_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "testing"
    yield {
        "headers": {"Authorization": f"Bearer {token}"},
        "user": user,
        "org": org,
        "proj_a": proj_a,
        "proj_b": proj_b
    }
    settings.ENVIRONMENT = orig_env

@pytest.mark.asyncio
async def test_1_no_oauth_public_lookup_succeeds(client, auth_headers):
    headers = auth_headers["headers"]
    proj_id = auth_headers["proj_a"].id

    res = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
        "business_name": "Alpha Plumbing",
        "location": "Sydney"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["lookup_status"] == "found"
    assert data["business_name"] == "Alpha Plumbing"
    assert data["source"] == "google_places_api"

@pytest.mark.asyncio
async def test_2_no_oauth_public_lookup_not_found(client, auth_headers):
    headers = auth_headers["headers"]
    proj_id = auth_headers["proj_a"].id

    res = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
        "business_name": "not_found_query_test",
        "location": "Nowhere"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["lookup_status"] == "not_found"

@pytest.mark.asyncio
async def test_3_no_oauth_places_not_configured(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "")
    headers = auth_headers["headers"]
    proj_id = auth_headers["proj_a"].id

    res = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
        "business_name": "Any Business"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["lookup_status"] == "not_configured"

@pytest.mark.asyncio
async def test_4_no_oauth_places_quota_exceeded(client, auth_headers):
    headers = auth_headers["headers"]
    proj_id = auth_headers["proj_a"].id

    res = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
        "business_name": "quota_test_query"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["lookup_status"] == "quota_exceeded"

@pytest.mark.asyncio
async def test_7_8_9_oauth_connect_disconnect_preserves_public_profile(client, auth_headers, test_db):
    headers = auth_headers["headers"]
    proj_id = auth_headers["proj_a"].id

    # 1. Perform public lookup without OAuth
    pub_res = await client.post(f"/api/v1/gbp/{proj_id}/public-lookup", json={
        "business_name": "Alpha Plumbing",
        "location": "Sydney"
    }, headers=headers)
    assert pub_res.json()["lookup_status"] == "found"

    # 2. Add connected GoogleAccount for owner data
    acc = GoogleAccount(
        project_id=proj_id,
        account_email="owner@alpha.com",
        access_token="valid_enc_token",
        is_connected=True
    )
    test_db.add(acc)
    await test_db.flush()

    gbp = GoogleBusinessProfile(
        google_account_id=acc.id,
        business_name="Alpha Plumbing Owner View",
        primary_category="Local Business",
        search_impressions=1250,
        maps_impressions=850,
        call_clicks=32,
        website_clicks=110,
        last_synced_at=datetime.now(timezone.utc)
    )
    test_db.add(gbp)
    await test_db.commit()

    # 3. Fetch owner profile
    owner_res = await client.get(f"/api/v1/gbp/{proj_id}/owner-profile", headers=headers)
    assert owner_res.status_code == 200
    owner_data = owner_res.json()
    assert owner_data["is_connected"] is True
    assert owner_data["account_email"] == "owner@alpha.com"
    assert owner_data["profile"]["search_impressions"] == 1250

    # 4. Disconnect OAuth
    disc_res = await client.post(f"/api/v1/gbp/{proj_id}/disconnect", headers=headers)
    assert disc_res.status_code == 200

    # 5. Verify public profile REMAINS AVAILABLE after OAuth disconnect!
    pub_check = await client.get(f"/api/v1/gbp/{proj_id}/public-profile", headers=headers)
    assert pub_check.status_code == 200
    assert pub_check.json()["lookup_status"] == "found"
    assert pub_check.json()["business_name"] == "Alpha Plumbing"

@pytest.mark.asyncio
async def test_10_project_isolation_for_gbp(client, auth_headers, test_db):
    headers = auth_headers["headers"]
    proj_a_id = auth_headers["proj_a"].id
    proj_b_id = auth_headers["proj_b"].id

    acc_a = GoogleAccount(project_id=proj_a_id, account_email="owner@a.com", is_connected=True)
    acc_b = GoogleAccount(project_id=proj_b_id, account_email="owner@b.com", is_connected=True)
    test_db.add_all([acc_a, acc_b])
    await test_db.commit()

    # Disconnect Project A
    await client.post(f"/api/v1/gbp/{proj_a_id}/disconnect", headers=headers)

    # Check Project A is disconnected
    a_res = await client.get(f"/api/v1/gbp/{proj_a_id}/owner-profile", headers=headers)
    assert a_res.json()["is_connected"] is False

    # Check Project B REMAINS CONNECTED
    b_res = await client.get(f"/api/v1/gbp/{proj_b_id}/owner-profile", headers=headers)
    assert b_res.json()["is_connected"] is True
    assert b_res.json()["account_email"] == "owner@b.com"

@pytest.mark.asyncio
async def test_11_12_13_14_15_16_no_fake_defaults_in_public_profile(client, auth_headers):
    headers = auth_headers["headers"]
    proj_id = auth_headers["proj_a"].id

    # Fetch idle public profile without prior lookup
    res = await client.get(f"/api/v1/gbp/{proj_id}/public-profile", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["completeness_score"] is None
    assert data["completeness_label"] == "Not measured"
    assert data["rating"] is None
    assert data["review_count"] is None
    assert data["phone"] is None
    assert data["formatted_address"] is None
    assert data["place_id"] is None
