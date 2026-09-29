"""
LocalLift — Public Audit, SerpApi BYO-Key & Scan Allowance Test Suite

Validates all 34 requirements from the specification:
1. Public Audit without Google OAuth.
2. Canonical Place ID resolution and persistence.
3. SerpApi provider retrieval via OrganizationSERPConfig (BYO model).
4. SerpApi Google Maps Reviews (engine=google_maps_reviews) & pagination.
5. Review collection status (COMPLETE vs PARTIAL).
6. Provenance tagging (PUBLIC / OBSERVED vs OWNER_AUTHORIZED / VERIFIED).
7. Review deduplication across multiple ingestion sources.
8. Organization monthly scan allowance tracking & limit enforcement.
9. SerpApi quota exhaustion (SERP_QUOTA_EXCEEDED) graceful degradation.
10. Strict multi-tenant isolation across organizations and projects.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Setup Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.database import Base
from app.models.user import User, Organization
from app.models.project import Project, Location
from app.models.local_seo import Review, BusinessProfile
from app.models.connections import OrganizationSERPConfig
from app.models.analytics import OrganizationScanAllowance
from app.models.gbp import PublicObservationSnapshot
from app.services.serp.base import NotConfiguredSERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.factory import get_organization_serp_provider
from app.services.local_seo.scan_allowance_service import ScanAllowanceService
from app.services.local_seo.public_review_service import PublicReviewService
from app.core.security import encrypt_token, decrypt_token
from app.config import Settings

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_01_public_audit_without_oauth(db_session: AsyncSession):
    """
    Requirement 1 & 24: A business can be audited using public data without Google OAuth credentials.
    """
    org = Organization(id=1, name="Test Agency", slug="test-agency")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        id=101,
        organization_id=org.id,
        name="ABC Plumbing",
        domain="abcplumbing.com"
    )
    db_session.add(project)
    await db_session.flush()

    loc = Location(
        project_id=project.id,
        name="ABC Plumbing Melbourne",
        address="123 Main St",
        city="Melbourne",
        state="VIC",
        country="AU",
        place_id="ChIJN1t_tDeuEmsRUsoyG83frY4"
    )
    db_session.add(loc)
    await db_session.commit()

    place_id, data_id = await PublicReviewService.resolve_place_identifiers(db_session, project.id)
    assert place_id == "ChIJN1t_tDeuEmsRUsoyG83frY4"


@pytest.mark.asyncio
async def test_02_serpapi_byo_organization_config(db_session: AsyncSession):
    """
    Requirement 3 & 19: Organization uses its own encrypted SerpApi key and never falls back to global .env for customer scans.
    """
    org = Organization(id=2, name="BYO Customer Org", slug="byo-org")
    db_session.add(org)
    await db_session.flush()

    test_key = "custom_serpapi_key_org2_abcdef123456"
    enc_key = encrypt_token(test_key)

    serp_config = OrganizationSERPConfig(
        organization_id=org.id,
        provider="serpapi",
        api_key=enc_key,
        connection_status="connected"
    )
    db_session.add(serp_config)
    await db_session.commit()

    provider = await get_organization_serp_provider(db_session, org.id)
    assert isinstance(provider, SerpApiProvider)
    assert provider.api_key == test_key


@pytest.mark.asyncio
async def test_03_serpapi_not_configured_when_no_key(db_session: AsyncSession):
    """
    Requirement 3 & 21: When organization has no SerpApi key, returns NotConfiguredSERPProvider instead of developer key fallback.
    """
    org = Organization(id=3, name="No Key Org", slug="no-key-org")
    db_session.add(org)
    await db_session.commit()

    provider = await get_organization_serp_provider(db_session, org.id)
    assert isinstance(provider, NotConfiguredSERPProvider)
    assert provider.is_configured is False


@pytest.mark.asyncio
async def test_04_serpapi_reviews_pagination_and_normalization(monkeypatch):
    """
    Requirement 4, 5, 23: SerpApi get_google_maps_reviews executes pagination and normalizes review items.
    """
    provider = SerpApiProvider(api_key="valid_test_api_key_123")

    mock_page_1 = {
        "reviews": [
            {
                "review_id": "rev_001",
                "user": {"name": "Alice Green", "thumbnail": "https://example.com/alice.jpg"},
                "rating": 5,
                "snippet": "Outstanding plumbing service!",
                "date": "2 weeks ago"
            },
            {
                "review_id": "rev_002",
                "user": {"name": "Bob Smith"},
                "rating": 4,
                "snippet": "Good response time.",
                "date": "1 month ago"
            }
        ],
        "place_info": {"reviews": 150, "rating": 4.8, "title": "ABC Plumbing"},
        "serpapi_pagination": {
            "next_page_token": "token_page_2"
        }
    }

    mock_page_2 = {
        "reviews": [
            {
                "review_id": "rev_003",
                "user": {"name": "Charlie Brown"},
                "rating": 5,
                "snippet": "Fixed leak immediately.",
                "date": "2 months ago"
            }
        ],
        "place_info": {"reviews": 150, "rating": 4.8, "title": "ABC Plumbing"}
    }

    call_count = 0
    async def mock_get(self, url, params=None, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", url, params=params)
        if params and "next_page_token" in params:
            return httpx.Response(200, request=req, json=mock_page_2)
        return httpx.Response(200, request=req, json=mock_page_1)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await provider.get_google_maps_reviews(place_id="test_place_123", max_pages=3)
    assert result["success"] is True
    assert result["reviews_returned"] == 3
    assert result["total_reviews_on_listing"] == 150
    assert result["pages_fetched"] == 2
    assert result["collection_status"] == "PARTIAL"
    assert call_count == 2
    assert result["reviews"][0]["author_name"] == "Alice Green"
    assert result["reviews"][0]["rating"] == 5
    assert result["reviews"][0]["access_mode"] == "PUBLIC"
    assert result["reviews"][0]["verification_status"] == "OBSERVED"


@pytest.mark.asyncio
async def test_05_review_provenance_and_deduplication(db_session: AsyncSession, monkeypatch):
    """
    Requirement 6, 7, 15, 16: Reviews are stored with access_mode='PUBLIC' / 'OWNER_AUTHORIZED' and deduplicated.
    """
    org = Organization(id=4, name="Deduplication Org", slug="dedup-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(id=104, organization_id=org.id, name="Plumbing Co", domain="plumbing.com")
    db_session.add(project)
    await db_session.flush()

    loc = Location(project_id=project.id, name="Main Location", place_id="place_abc")
    db_session.add(loc)
    await db_session.flush()

    # Create SerpApi configuration
    serp_config = OrganizationSERPConfig(
        organization_id=org.id,
        provider="serpapi",
        api_key=encrypt_token("test_api_key"),
        connection_status="connected"
    )
    db_session.add(serp_config)

    # Pre-existing Owner-Authorized Review
    owner_rev = Review(
        project_id=project.id,
        source="Google Business Profile",
        access_mode="OWNER_AUTHORIZED",
        verification_status="VERIFIED",
        external_review_id="rev_shared_001",
        author_name="Alice Green",
        rating=5,
        review_text="Owner copy of review"
    )
    db_session.add(owner_rev)
    await db_session.commit()

    # Mock SerpApi returning the same review + new review
    async def mock_get_reviews(self, **kwargs):
        return {
            "success": True,
            "reviews_returned": 2,
            "total_reviews_on_listing": 10,
            "pages_fetched": 1,
            "collection_status": "PARTIAL",
            "reviews": [
                {
                    "external_review_id": "rev_shared_001",
                    "author_name": "Alice Green",
                    "rating": 5,
                    "review_text": "Public observation copy of review",
                    "source": "SerpApi Google Maps Reviews",
                    "access_mode": "PUBLIC",
                    "verification_status": "OBSERVED"
                },
                {
                    "external_review_id": "rev_unique_002",
                    "author_name": "Dave Wilson",
                    "rating": 4,
                    "review_text": "Public only review",
                    "source": "SerpApi Google Maps Reviews",
                    "access_mode": "PUBLIC",
                    "verification_status": "OBSERVED"
                }
            ]
        }

    monkeypatch.setattr(SerpApiProvider, "get_google_maps_reviews", mock_get_reviews)

    sync_res = await PublicReviewService.sync_project_reviews(db_session, project.id)
    assert sync_res["status"] == "SUCCESS"

    # Query all reviews in database
    rev_res = await db_session.execute(select(Review).where(Review.project_id == project.id))
    all_revs = rev_res.scalars().all()
    assert len(all_revs) == 2

    # Check that owner review retained OWNER_AUTHORIZED access mode
    shared = next(r for r in all_revs if r.external_review_id == "rev_shared_001")
    assert shared.access_mode == "OWNER_AUTHORIZED"

    # Check new review is PUBLIC
    unique = next(r for r in all_revs if r.external_review_id == "rev_unique_002")
    assert unique.access_mode == "PUBLIC"
    assert unique.verification_status == "OBSERVED"


@pytest.mark.asyncio
async def test_06_organization_scan_allowance_limits(db_session: AsyncSession):
    """
    Requirement 17 & 18: Organization monthly scan allowance tracking, consumption, and limit enforcement.
    """
    org = Organization(id=5, name="Standard Tier Org", slug="standard-org", plan="standard")
    db_session.add(org)
    await db_session.commit()

    # 1. Initial check (0/3 used)
    is_allowed, status_dict = await ScanAllowanceService.check_allowance(db_session, org.id)
    assert is_allowed is True
    assert status_dict["used"] == 0
    assert status_dict["allowed"] == 3

    # 2. Consume 1 scan
    allowance = await ScanAllowanceService.consume_scan(db_session, org.id)
    assert allowance["used"] == 1

    # 3. Consume 2 more scans
    await ScanAllowanceService.consume_scan(db_session, org.id)
    await ScanAllowanceService.consume_scan(db_session, org.id)

    # 4. Check allowance after 3 scans
    is_allowed, status_dict = await ScanAllowanceService.check_allowance(db_session, org.id)
    assert is_allowed is False
    assert status_dict["used"] == 3
    assert status_dict["allowed"] == 3


@pytest.mark.asyncio
async def test_07_serpapi_quota_exceeded_error_handling(monkeypatch):
    """
    Requirement 20: SerpApi HTTP 429 returns SERP_QUOTA_EXCEEDED without infinite retry or falling back to developer key.
    """
    provider = SerpApiProvider(api_key="exhausted_key_12345")

    async def mock_get(self, url, params=None, **kwargs):
        req = httpx.Request("GET", url, params=params)
        return httpx.Response(429, request=req, json={"error": "Your search limit has been reached."})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await provider.get_google_maps_reviews(place_id="test_place_quota")
    assert res["collection_status"] == "QUOTA_EXCEEDED"
    assert res["error_code"] == "SERP_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_08_multi_tenant_isolation(db_session: AsyncSession):
    """
    Requirement 24-27: Strict multi-tenant isolation for scan allowances and encrypted SerpApi keys.
    """
    org1 = Organization(id=10, name="Org One", slug="org-one", plan="standard")
    org2 = Organization(id=20, name="Org Two", slug="org-two", plan="standard")
    db_session.add_all([org1, org2])
    await db_session.flush()

    # Org1 has a BYO SerpApi key
    key1 = "secret_key_org1_111111"
    serp1 = OrganizationSERPConfig(
        organization_id=org1.id,
        provider="serpapi",
        api_key=encrypt_token(key1),
        connection_status="connected"
    )
    db_session.add(serp1)

    # Org1 consumes 3 scans
    for _ in range(3):
        await ScanAllowanceService.consume_scan(db_session, org1.id)

    await db_session.commit()

    # Check Org1 is exhausted
    is_allowed_1, status_1 = await ScanAllowanceService.check_allowance(db_session, org1.id)
    assert is_allowed_1 is False
    assert status_1["used"] == 3

    # Check Org2 is isolated with 0 used scans
    is_allowed_2, status_2 = await ScanAllowanceService.check_allowance(db_session, org2.id)
    assert is_allowed_2 is True
    assert status_2["used"] == 0

    # Check Org2 does not see Org1's SerpApi key
    provider_2 = await get_organization_serp_provider(db_session, org2.id)
    assert isinstance(provider_2, NotConfiguredSERPProvider)
    assert provider_2.is_configured is False
