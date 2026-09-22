import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.schemas.ranking import GeoGridScanRequest
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.base import SERPResponse, SERPItem
from app.api.v1.keywords import trigger_grid_scan

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_geogrid_5x5_points_generation_and_execution():
    """
    Verifies that a 5x5 Geo-Grid generates exactly 25 unique points,
    calls the provider independently for each point, and computes honest metrics.
    """
    call_records = []

    mock_provider = AsyncMock()
    mock_provider.provider_name = "test_serp_provider"
    mock_provider.is_configured = True
    mock_caps = MagicMock()
    mock_caps.geo_grid = True
    mock_provider.capabilities = mock_caps

    async def mock_search_point(keyword, lat, lng, **kwargs):
        call_records.append((lat, lng, keyword))
        idx = len(call_records)
        # Business ranks #2 at first 5 points, absent at remaining 20
        if idx <= 5:
            items = [
                SERPItem(position=1, title="Competitor A", domain="comp-a.com"),
                SERPItem(position=2, title="My Real Electrician", domain="myelectrician.com", place_id="ChIJ_REAL123"),
                SERPItem(position=3, title="Competitor B", domain="comp-b.com")
            ]
        else:
            items = [
                SERPItem(position=1, title="Competitor A", domain="comp-a.com"),
                SERPItem(position=2, title="Competitor C", domain="comp-c.com")
            ]
        return SERPResponse(provider="test_serp_provider", keyword=keyword, organic_results=[], local_pack_results=items)

    mock_provider.search_local_grid_point.side_effect = mock_search_point

    res = await GeoGridScanner.scan_grid(
        provider=mock_provider,
        keyword="electrician melbourne",
        center_lat=-37.8136,
        center_lng=144.9631,
        grid_size=5,
        radius_km=5.0,
        business_name="My Real Electrician",
        target_place_id="ChIJ_REAL123",
        target_domain="myelectrician.com"
    )

    # 1. Total points must be 25
    assert res["grid_size"] == 5
    assert res["radius_km"] == 5.0
    assert len(res["grid_points"]) == 25
    assert len(call_records) == 25

    # 2. Every point has unique coordinates and point_number 0..24
    point_nums = [p["point_number"] for p in res["grid_points"]]
    assert sorted(point_nums) == list(range(25))
    coords = set((p["lat"], p["lng"]) for p in res["grid_points"])
    assert len(coords) == 25

    # 3. Exactly 5 points rank #2, exactly 20 points are NOT_FOUND
    ranking_found = [p for p in res["grid_points"] if p["rank"] is not None]
    assert len(ranking_found) == 5
    for p in ranking_found:
        assert p["rank"] == 2
        assert p["status"] == "SUCCESS"
        assert p["matched_place_id"] == "ChIJ_REAL123"

    not_found = [p for p in res["grid_points"] if p["rank"] is None]
    assert len(not_found) == 20
    for p in not_found:
        assert p["status"] == "NOT_FOUND"

    # 4. Metrics integrity
    assert res["total_points"] == 25
    assert res["completed_points"] == 25
    assert res["ranking_found_points"] == 5
    assert res["not_found_points"] == 20
    assert res["provider_error_points"] == 0
    assert res["timeout_points"] == 0
    # Average rank strictly uses found points: 5 * 2 / 5 = 2.0
    assert res["average_rank"] == 2.0
    # Visibility: 5 top 3 ranks / 25 completed = 20.0%
    assert res["local_visibility_pct"] == 20.0

@pytest.mark.asyncio
async def test_geogrid_5x5_database_persistence(db_session):
    """
    Verifies full end-to-end Geo-Grid scan database persistence:
    1 GeoGridScan created, 25 GeoGridPointResult rows persisted with unique constraints,
    correct project, keyword, and coordinates.
    """
    # Create Org, User, Project, Location, Keyword
    org = Organization(id=1, name="Test Org", slug="test-org")
    db_session.add(org)
    await db_session.flush()

    user = User(
        id=1,
        email="owner@test.com",
        full_name="Owner User",
        hashed_password="pw",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    member = OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.ADMIN)
    db_session.add(member)

    project = Project(
        id=10,
        organization_id=org.id,
        name="Melbourne Electricians",
        domain="myelectrician.com",
        status="active"
    )
    db_session.add(project)
    await db_session.flush()

    loc = Location(
        id=100,
        project_id=project.id,
        name="Main Office",
        latitude=-37.8136,
        longitude=144.9631
    )
    db_session.add(loc)

    kw = Keyword(
        id=50,
        project_id=project.id,
        keyword="commercial electrician",
        target_location="Melbourne"
    )
    db_session.add(kw)
    await db_session.commit()

    # Mock provider returning 25 responses
    mock_provider = AsyncMock()
    mock_provider.provider_name = "serpapi"
    mock_provider.is_configured = True
    mock_caps = MagicMock()
    mock_caps.geo_grid = True
    mock_provider.capabilities = mock_caps

    async def mock_search_point(keyword, lat, lng, **kwargs):
        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            organic_results=[],
            local_pack_results=[
                SERPItem(position=1, title="Melbourne Electricians", domain="myelectrician.com")
            ]
        )
    mock_provider.search_local_grid_point.side_effect = mock_search_point

    scan_req = GeoGridScanRequest(
        project_id=project.id,
        keyword_id=kw.id,
        grid_size=5,
        radius_km=5.0,
        center_lat=-37.8136,
        center_lng=144.9631
    )

    mock_request = AsyncMock()

    with patch("app.api.v1.keywords.get_organization_serp_provider", return_value=mock_provider):
        scan_out = await trigger_grid_scan(mock_request, scan_req, user, db_session)

    assert scan_out.id is not None
    assert scan_out.project_id == project.id
    assert scan_out.keyword_id == kw.id
    assert scan_out.grid_size == 5
    assert scan_out.radius_km == 5.0
    assert len(scan_out.points) == 25

    # Check database persistence of scan
    scans_stmt = select(GeoGridScan).where(GeoGridScan.project_id == project.id)
    scans = (await db_session.execute(scans_stmt)).scalars().all()
    assert len(scans) == 1
    scan = scans[0]
    assert scan.ranking_found_points == 25
    assert scan.completed_points == 25
    assert scan.not_found_points == 0

    # Check database persistence of all 25 point results
    points_stmt = select(GeoGridPointResult).where(GeoGridPointResult.scan_id == scan.id).order_by(GeoGridPointResult.point_number)
    db_points = (await db_session.execute(points_stmt)).scalars().all()
    assert len(db_points) == 25

    # Verify point values
    for idx, pt in enumerate(db_points):
        assert pt.scan_id == scan.id
        assert pt.project_id == project.id
        assert pt.keyword_id == kw.id
        assert pt.point_number == idx
        assert pt.rank == 1
        assert pt.status == "SUCCESS"
        assert pt.matched_domain == "myelectrician.com"

    # Verify duplicate prevention: attempting to insert duplicate (scan_id, point_number) raises error
    from sqlalchemy.exc import IntegrityError
    dup_point = GeoGridPointResult(
        scan_id=scan.id,
        project_id=project.id,
        keyword_id=kw.id,
        point_number=0,  # duplicate of point 0
        latitude=-37.8136,
        longitude=144.9631,
        status="SUCCESS"
    )
    db_session.add(dup_point)
    with pytest.raises(IntegrityError):
        await db_session.commit()
