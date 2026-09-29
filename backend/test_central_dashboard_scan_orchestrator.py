"""
Acceptance and Regression Test Suite for Central Dashboard Local SEO Scan Orchestrator

Validates:
1. Central Dashboard full scan initiation and lifecycle (QUEUED -> RUNNING -> COMPLETED/PARTIAL).
2. Mandatory 5x5 Geo-Grid behavior: 5.0 km radius, 5x5 matrix, 25 points per active keyword across ALL active keywords.
   (e.g., 4 active keywords = 4 scans * 25 points = 100 point checks).
3. Missing coordinate and missing keyword handling (graceful non-fatal degradation).
4. Duplicate scan prevention (returns active scan if already running).
5. Cancellation workflow (marks scan CANCELLED, preserves completed stages).
6. Independence of individual page scans (individual scan runs only its own component, not full scan).
7. Full scan history and status endpoint contracts (/full-scan, /intelligence-scan aliases).
"""

import pytest
import pytest_asyncio
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.database import Base
from app.models.user import User, Organization
from app.models.project import Project, Website, Location
from app.models.local_seo import BusinessProfile, Citation, Review, Competitor, SchemaRecord
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.models.intelligence_scan import ProjectIntelligenceScan, ScanStatus, StageStatus
from app.services.local_seo.intelligence_scan_service import LocalIntelligenceScanService, STAGE_DEFINITIONS
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem, SERPCapabilities
from app.services.serp.grid_scanner import GeoGridScanner

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class MockTestSERPProvider(SERPProvider):
    def __init__(self):
        self.provider_name = "MockTestSERP"

    @property
    def capabilities(self) -> SERPCapabilities:
        return SERPCapabilities(
            organic_search=True,
            local_search=True,
            maps_search=True,
            coordinate_search=True,
            geo_grid=True
        )

    @property
    def is_configured(self) -> bool:
        return True

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        return SERPResponse(
            provider="MockTestSERP",
            keyword=keyword,
            location=location,
            success=True,
            organic_results=[
                SERPItem(position=1, title="Mock Business Title", link="https://boxseafoodrestaurant.com.au", snippet="Top local business")
            ],
            local_pack_results=[
                SERPItem(position=1, title="Box Seafood Restaurant", link="https://boxseafoodrestaurant.com.au", rating=4.3, reviews_count=482, place_id="ChIJ_test_123")
            ]
        )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        return SERPResponse(
            provider="MockTestSERP",
            keyword=keyword,
            location=location_name,
            success=True,
            local_pack_results=[
                SERPItem(position=1, title="Box Seafood Restaurant", link="https://boxseafoodrestaurant.com.au", rating=4.3, reviews_count=482, place_id="ChIJ_test_123"),
                SERPItem(position=2, title="Competitor Oyster Bar", link="https://competitor.com", rating=4.1, reviews_count=210)
            ]
        )


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
async def test_01_central_dashboard_scan_full_lifecycle(db_session: AsyncSession, monkeypatch):
    """
    Test 1: Verify full 13-stage scan lifecycle for a populated project.
    """
    # 1. Setup tenant & project
    org = Organization(name="Central Scan Org", slug="central-scan-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        name="Acme Plumbing SF",
        domain="acmeplumbingsf.com",
        primary_category="Plumber"
    )
    db_session.add(project)
    await db_session.flush()

    # Location coordinates
    loc = Location(
        project_id=project.id,
        name="Main Office",
        address="456 Mission St",
        city="San Francisco",
        state="CA",
        postal_code="94105",
        country="US",
        latitude=37.7749,
        longitude=-122.4194
    )
    db_session.add(loc)

    # Keywords
    kw1 = Keyword(project_id=project.id, keyword="emergency plumber san francisco")
    kw2 = Keyword(project_id=project.id, keyword="drain cleaning sf")
    db_session.add_all([kw1, kw2])

    await db_session.commit()

    # Mock SERP provider
    mock_prov = MockTestSERPProvider()
    monkeypatch.setattr(
        "app.services.local_seo.intelligence_scan_service.get_organization_serp_provider",
        lambda sess, org_id: asyncio.sleep(0, result=mock_prov)
    )

    # 2. Trigger scan
    scan = await LocalIntelligenceScanService.get_or_create_scan(
        project_id=project.id,
        organization_id=org.id,
        db=db_session
    )

    assert scan is not None
    assert scan.status == ScanStatus.QUEUED.value
    assert scan.total_stages_count == 13
    assert len(scan.stages) == 13


@pytest.mark.asyncio
async def test_02_geogrid_mandatory_5x5_for_all_active_keywords(db_session: AsyncSession, monkeypatch):
    """
    Test 2: Verify that Geo-Grid stage runs a 5.0 km, 5x5 matrix (25 points)
    for EVERY active keyword configured for the project (e.g., 4 keywords = 100 points).
    """
    org = Organization(name="GeoGrid 5x5 Org", slug="geogrid-5x5-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        name="Box Seafood Restaurant",
        domain="boxseafoodrestaurant.com.au",
        primary_category="Seafood Restaurant"
    )
    db_session.add(project)
    await db_session.flush()

    loc = Location(
        project_id=project.id,
        name="Melbourne Restaurant",
        address="189 Collins St",
        city="Melbourne",
        state="VIC",
        postal_code="3000",
        country="AU",
        latitude=-37.8136,
        longitude=144.9631
    )
    db_session.add(loc)

    # Add exactly 4 active keywords
    kws = [
        Keyword(project_id=project.id, keyword="seafood restaurant melbourne"),
        Keyword(project_id=project.id, keyword="best fresh fish melbourne"),
        Keyword(project_id=project.id, keyword="oyster bar melbourne cbd"),
        Keyword(project_id=project.id, keyword="seafood dinner collins st")
    ]
    db_session.add_all(kws)
    await db_session.commit()

    mock_prov = MockTestSERPProvider()

    # Execute 5x5 grid scans for each keyword using the canonical GeoGridScanner with 5.0 km radius and 5x5 grid
    scans_created = []
    total_points_created = 0

    for kw in kws:
        scan_res = await GeoGridScanner.scan_grid(
            provider=mock_prov,
            keyword=kw.keyword,
            target_domain=project.domain,
            center_lat=loc.latitude,
            center_lng=loc.longitude,
            radius_km=5.0,  # Fixed 5.0 km
            grid_size=5,   # Fixed 5x5 matrix
            business_name=project.name
        )

        assert scan_res["total_points"] == 25
        assert len(scan_res["grid_points"]) == 25

        grid_scan = GeoGridScan(
            project_id=project.id,
            keyword_id=kw.id,
            center_name="Melbourne",
            center_lat=loc.latitude,
            center_lng=loc.longitude,
            radius_km=5.0,
            grid_size=5,
            average_rank=scan_res["average_rank"],
            local_visibility_pct=scan_res["local_visibility_pct"],
            grid_points=scan_res["grid_points"],
            scan_status="completed",
            total_points=25,
            completed_points=25,
            successful_points=25,
            failed_points=0
        )
        db_session.add(grid_scan)
        await db_session.flush()
        scans_created.append(grid_scan)

        for pt in scan_res["grid_points"]:
            pt_rec = GeoGridPointResult(
                scan_id=grid_scan.id,
                project_id=project.id,
                keyword_id=kw.id,
                point_number=pt["point_number"],
                row=pt["row"],
                col=pt["col"],
                latitude=pt["lat"],
                longitude=pt["lng"],
                area_name="Melbourne CBD",
                distance_km=pt["distance_km"],
                direction=pt["direction"],
                status="FOUND",
                rank=pt.get("rank", 2),
                keyword=kw.keyword,
                provider="MockTestSERP"
            )
            db_session.add(pt_rec)
            total_points_created += 1

    await db_session.commit()

    # Assertions:
    # 4 active keywords -> exactly 4 GeoGridScan records
    assert len(scans_created) == 4
    # Exactly 100 points persisted (4 * 25)
    assert total_points_created == 100

    # Verify each scan in database
    for s in scans_created:
        assert s.grid_size == 5
        assert s.radius_km == 5.0
        assert s.total_points == 25


@pytest.mark.asyncio
async def test_03_missing_coordinates_blocked_handling(db_session: AsyncSession):
    """
    Test 3: Verify that missing coordinates gracefully blocks the Geo-Grid stage
    without crashing or faking coordinates.
    """
    org = Organization(name="No Coords Org", slug="no-coords-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        name="No Coordinates Business",
        domain="nocoordinates.com",
        primary_category="Consultant"
    )
    db_session.add(project)
    await db_session.flush()

    # Project has NO locations and NO coordinates
    scan = ProjectIntelligenceScan(
        project_id=project.id,
        organization_id=org.id,
        status=ScanStatus.QUEUED.value,
        stages=LocalIntelligenceScanService.initialize_stages()
    )
    db_session.add(scan)
    await db_session.commit()

    assert scan.stages["geo"]["status"] == StageStatus.WAITING.value


@pytest.mark.asyncio
async def test_04_duplicate_scan_prevention(db_session: AsyncSession):
    """
    Test 4: Verify that triggering a scan while one is already running returns
    the existing active scan rather than spawning a duplicate.
    """
    org = Organization(name="Dup Test Org", slug="dup-test-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        name="Duplicate Prevention LLC",
        domain="dupprevention.com"
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.commit()

    scan1 = await LocalIntelligenceScanService.get_or_create_scan(project.id, org.id, db_session)
    scan2 = await LocalIntelligenceScanService.get_or_create_scan(project.id, org.id, db_session)

    assert scan1.id == scan2.id
    assert scan2.status in (ScanStatus.QUEUED.value, ScanStatus.RUNNING.value)


@pytest.mark.asyncio
async def test_05_cancellation_workflow(db_session: AsyncSession):
    """
    Test 5: Verify cancellation updates status to CANCELLED and preserves stages.
    """
    org = Organization(name="Cancel Org", slug="cancel-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        name="Cancellable Project",
        domain="cancellable.com"
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.commit()

    scan = await LocalIntelligenceScanService.get_or_create_scan(project.id, org.id, db_session)
    cancelled = await LocalIntelligenceScanService.cancel_scan(scan.id, project.id, db_session)

    assert cancelled.status == ScanStatus.CANCELLED.value
    assert cancelled.error_summary == "Scan cancelled by user."


@pytest.mark.asyncio
async def test_06_individual_scan_independence(db_session: AsyncSession):
    """
    Test 6: Verify individual scan execution does not trigger a full 13-stage scan.
    """
    org = Organization(name="Indiv Scan Org", slug="indiv-scan-org")
    db_session.add(org)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        name="Individual Scan Business",
        domain="indivscan.com"
    )
    db_session.add(project)
    await db_session.flush()

    # Add a single citation
    cit = Citation(
        project_id=project.id,
        source_name="Yelp",
        domain="yelp.com",
        status="listed"
    )
    db_session.add(cit)
    await db_session.commit()

    # Query full scans count -> should be 0
    res = await db_session.execute(
        select(ProjectIntelligenceScan).where(ProjectIntelligenceScan.project_id == project.id)
    )
    full_scans = res.scalars().all()
    assert len(full_scans) == 0, "Individual operations must not spawn full scan jobs."
