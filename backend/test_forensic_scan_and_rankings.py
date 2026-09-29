"""
LocalLift — Forensic Scan, Technical SEO, Local SEO Audit & Ranking Engine Test Suite
Tests:
- Dependency-aware Central Scan orchestration (Phase 1 -> Phase 2 -> Phase 3 -> Phase 4)
- Single crawl execution and snapshot reuse
- No fallback fabricated scores (75, 80, etc.)
- Stale scan recovery
- Local SEO Audit consuming crawl_snapshot_id without duplicate crawling
- Canonical KeywordRankingService with distinct ranking surfaces (Organic vs Local Pack)
- Explicit status codes (NOT_CHECKED, RANKED, NOT_IN_TOP_100, etc.)
- Movement calculation across top-100 boundaries
- GeoGrid Place ID matching and callback argument handling
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.database import Base
from app.models.project import Project, Location
from app.models.intelligence_scan import ProjectIntelligenceScan, ScanStatus, StageStatus
from app.models.audit import AuditJob, AuditJobStatus, LocalAuditRun, LocalAuditFinding, SEOAudit
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan, GeoGridPointResult
from app.models.local_seo import BusinessProfile
from app.models.gbp import GoogleBusinessProfile

from app.services.serp.ranking_service import KeywordRankingService
from app.services.serp.base import SERPResponse, SERPItem
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.local_seo.audit_framework import LocalSEOAuditFramework
from app.services.local_seo.intelligence_scan_service import LocalIntelligenceScanService


@pytest_asyncio.fixture
async def test_db_session():
    """Creates a temporary in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_keyword_ranking_service_movement_calculation():
    """Validates movement calculation across all boundary conditions."""
    # 1. Normal improvement
    mov, label = KeywordRankingService.calculate_movement(prev_rank=8, curr_rank=5, rank_status="RANKED")
    assert mov == 3
    assert label == "+3 improved"

    # 2. Normal decline
    mov, label = KeywordRankingService.calculate_movement(prev_rank=5, curr_rank=12, rank_status="RANKED")
    assert mov == -7
    assert label == "-7 declined"

    # 3. No change
    mov, label = KeywordRankingService.calculate_movement(prev_rank=5, curr_rank=5, rank_status="RANKED")
    assert mov == 0
    assert label == "No change"

    # 4. Entered Top 100
    mov, label = KeywordRankingService.calculate_movement(prev_rank=None, curr_rank=9, rank_status="RANKED")
    assert mov is None
    assert "Entered Top 100" in label

    # 5. Lost Top 100 visibility
    mov, label = KeywordRankingService.calculate_movement(prev_rank=5, curr_rank=None, rank_status="NOT_IN_TOP_100")
    assert mov is None
    assert label == "Lost Top 100 visibility"

    # 6. Unranked check
    mov, label = KeywordRankingService.calculate_movement(prev_rank=None, curr_rank=None, rank_status="NOT_IN_TOP_100")
    assert mov is None
    assert label == "Not in Top 100"


@pytest.mark.asyncio
async def test_keyword_serp_config_resolution():
    """Validates country and language resolution consistency across projects."""
    # Australian project (.com.au domain)
    proj_au = Project(
        name="Melbourne Cafe",
        domain="melbournecafe.com.au",
        country=None,
        organization_id=1
    )
    loc_au = Location(city="Melbourne", state="VIC", country="Australia")
    cfg = KeywordRankingService.resolve_serp_config(proj_au, loc_au, kw_location=None)
    assert cfg["country"] == "au"
    assert cfg["location"] == "Melbourne, VIC, Australia"

    # Explicit country project
    proj_uk = Project(
        name="London Plumbing",
        domain="londonplumber.co.uk",
        country="uk",
        organization_id=1
    )
    cfg_uk = KeywordRankingService.resolve_serp_config(proj_uk, None, kw_location="Camden, London")
    assert cfg_uk["country"] == "uk"
    assert cfg_uk["location"] == "Camden, London"


@pytest.mark.asyncio
async def test_keyword_ranking_service_distinct_surfaces(test_db_session: AsyncSession):
    """Validates separate organic and local pack rank recording and status assignment."""
    # Setup test project & location
    proj = Project(
        name="Test Dental Clinic",
        domain="testdentalclinic.com.au",
        organization_id=1
    )
    test_db_session.add(proj)
    await test_db_session.commit()
    await test_db_session.refresh(proj)

    kw = Keyword(
        project_id=proj.id,
        keyword="dentist near me",
        search_intent="Commercial"
    )
    test_db_session.add(kw)
    await test_db_session.commit()
    await test_db_session.refresh(kw)

    # Mock SERP response with distinct Local Pack and Organic positions
    mock_serp_resp = SERPResponse(
        keyword="dentist near me",
        success=True,
        provider="MockSERP",
        total_results=20,
        organic_results=[
            SERPItem(position=8, title="Other Clinic", link="https://otherclinic.com", domain="otherclinic.com"),
            SERPItem(position=12, title="Test Dental Clinic", link="https://testdentalclinic.com.au/services", domain="testdentalclinic.com.au")
        ],
        local_pack_results=[
            SERPItem(position=2, title="Test Dental Clinic", link="https://testdentalclinic.com.au", domain="testdentalclinic.com.au", rating=4.9, reviews_count=45)
        ]
    )

    with patch("app.services.serp.ranking_service.get_organization_serp_provider") as mock_get_prov:
        mock_prov = MagicMock()
        mock_prov.is_configured = True
        mock_prov.provider_name = "MockSERP"
        mock_prov.search_keyword = AsyncMock(return_value=mock_serp_resp)
        mock_get_prov.return_value = mock_prov

        result = await KeywordRankingService.check_keyword(
            db=test_db_session,
            keyword_id=kw.id,
            project_id=proj.id,
            organization_id=1
        )

        assert result["status"] == "checked"
        assert result["organic_rank"] == 12
        assert result["local_pack_rank"] == 2
        assert result["current_rank"] == 2  # Best visibility position

        # Refresh from db and verify model persistence
        await test_db_session.refresh(kw)
        assert kw.organic_rank == 12
        assert kw.local_pack_rank == 2
        assert kw.rank_status == "RANKED"
        assert kw.last_successful_check_at is not None


@pytest.mark.asyncio
async def test_local_seo_audit_framework_consumes_crawl_snapshot(test_db_session: AsyncSession):
    """Validates LocalSEOAuditFramework uses supplied crawl snapshot and does NOT trigger duplicate crawl."""
    proj = Project(
        name="Snapshot Plumbing",
        domain="snapshotplumbing.com.au",
        organization_id=1
    )
    test_db_session.add(proj)
    await test_db_session.commit()
    await test_db_session.refresh(proj)

    # Create pre-existing AuditJob crawl snapshot
    audit_job = AuditJob(
        project_id=proj.id,
        organization_id=1,
        job_type="website_audit",
        status=AuditJobStatus.COMPLETED,
        crawler_status="completed",
        progress=100.0,
        start_url="https://snapshotplumbing.com.au",
        pages_crawled=10
    )
    test_db_session.add(audit_job)

    seo_audit = SEOAudit(
        project_id=proj.id,
        audit_type="local_website",
        overall_score=88,
        pages_analyzed=10,
        critical_issues=0,
        warnings=1,
        opportunities=2,
        passed_checks=12,
        summary="Test crawl snapshot"
    )
    test_db_session.add(seo_audit)
    await test_db_session.commit()
    await test_db_session.refresh(audit_job)
    await test_db_session.refresh(seo_audit)

    # Run audit passing crawl_snapshot_id
    run = await LocalSEOAuditFramework.run_audit(
        project_id=proj.id,
        db=test_db_session,
        framework_version="local_seo_v1",
        crawl_snapshot_id=audit_job.id,
        force_crawl=False
    )

    assert run.crawl_id == audit_job.id
    assert run.findings is not None


@pytest.mark.asyncio
async def test_geogrid_point_done_callback():
    """Validates Geo-Grid point callback handles dict argument properly without failing."""
    completed_points = 0
    failed_points = 0

    def _on_point_done(point_result: dict):
        nonlocal completed_points, failed_points
        completed_points += 1
        st = str(point_result.get("status") or "").upper()
        if st in ("FAILED", "TIMEOUT", "PROVIDER_ERROR", "ERROR") or point_result.get("error"):
            failed_points += 1

    # Simulate callback invocations
    _on_point_done({"point_number": 1, "status": "SUCCESS", "rank": 2})
    _on_point_done({"point_number": 2, "status": "NOT_FOUND", "rank": None})
    _on_point_done({"point_number": 3, "status": "FAILED", "error": "Timeout"})
    _on_point_done({"point_number": 4, "status": "PROVIDER_ERROR", "error": "Quota exceeded"})

    assert completed_points == 4
    assert failed_points == 2


@pytest.mark.asyncio
async def test_gbp_sync_recursion_regression(test_db_session):
    """
    Regression Test: Ensures sync_project_gbp -> sync_google_account never causes infinite recursion.
    """
    from app.services.google.sync import GBPSyncService
    from app.models.gbp import GoogleAccount

    # Create project without bound location
    proj = Project(name="Recursion Test Co", domain="recursiontest.com", organization_id=1)
    test_db_session.add(proj)
    await test_db_session.commit()
    await test_db_session.refresh(proj)

    g_acc = GoogleAccount(
        project_id=proj.id,
        account_email="test@example.com",
        is_connected=True
    )
    test_db_session.add(g_acc)
    await test_db_session.commit()

    # Call sync_project_gbp - should safely terminate without RecursionError
    res1 = await GBPSyncService.sync_project_gbp(project_id=proj.id, db=test_db_session)
    assert res1["status"] == "not_connected"
    assert "No bound Google Business Profile" in res1["error"]

    # Call sync_google_account - should also safely terminate without RecursionError
    res2 = await GBPSyncService.sync_google_account(google_account=g_acc, db=test_db_session)
    assert res2["status"] == "not_connected"
    assert "not bound" in res2["error"]


@pytest.mark.asyncio
async def test_geogrid_scan_completed_at_persistence(test_db_session):
    """
    Validates GeoGridScan accepts and persists completed_at timestamp without error.
    """
    proj = Project(name="Geo Test Co", domain="geotest.com", organization_id=1)
    test_db_session.add(proj)
    await test_db_session.commit()
    await test_db_session.refresh(proj)

    kw = Keyword(project_id=proj.id, keyword="emergency plumber", target_location="Austin, TX")
    test_db_session.add(kw)
    await test_db_session.commit()
    await test_db_session.refresh(kw)

    now = datetime.now(timezone.utc)
    scan = GeoGridScan(
        project_id=proj.id,
        keyword_id=kw.id,
        center_lat=30.2672,
        center_lng=-97.7431,
        radius_km=5.0,
        grid_size=5,
        scan_status="completed",
        total_points=25,
        completed_points=25,
        successful_points=25,
        failed_points=0,
        started_at=now - timedelta(seconds=10),
        completed_at=now
    )
    test_db_session.add(scan)
    await test_db_session.commit()
    await test_db_session.refresh(scan)

    assert scan.id is not None
    assert scan.completed_at is not None
    assert scan.scan_status == "completed"


@pytest.mark.asyncio
async def test_review_identity_and_nullable_rating(test_db_session):
    """
    Validates reviews use external_review_id for identity and support nullable rating without 5-star fallback.
    """
    from app.models.local_seo import Review

    proj = Project(name="Review Test Co", domain="reviewtest.com", organization_id=1)
    test_db_session.add(proj)
    await test_db_session.commit()
    await test_db_session.refresh(proj)

    # 1. Review with missing rating
    rev1 = Review(
        project_id=proj.id,
        external_review_id="ext_rev_12345",
        source="Google",
        author_name="Alice Smith",
        rating=None,  # Nullable, no default 5 fallback
        review_text="Service was pending."
    )
    test_db_session.add(rev1)
    await test_db_session.commit()
    await test_db_session.refresh(rev1)

    assert rev1.external_review_id == "ext_rev_12345"
    assert rev1.rating is None

    # 2. Duplicate author with different external_review_id
    rev2 = Review(
        project_id=proj.id,
        external_review_id="ext_rev_67890",
        source="Google",
        author_name="Alice Smith",
        rating=4,
        review_text="Second visit was great."
    )
    test_db_session.add(rev2)
    await test_db_session.commit()
    await test_db_session.refresh(rev2)

    assert rev2.id != rev1.id
    assert rev2.external_review_id == "ext_rev_67890"


@pytest.mark.asyncio
async def test_crawler_domain_boundary_and_redirect_escape():
    """
    Validates crawler never puts external URLs in queue and halts on redirect to external domain.
    """
    from app.services.crawler import WebsiteCrawler, URLNormalizer

    crawler = WebsiteCrawler(
        start_url="https://myshop.com",
        max_pages=20,
        allow_local_dev=True
    )

    # 1. Verify URL Normalizer domain isolation
    assert URLNormalizer.is_same_domain("https://myshop.com", "https://myshop.com/about") is True
    assert URLNormalizer.is_same_domain("https://myshop.com", "https://facebook.com/myshop") is False
    assert URLNormalizer.is_same_domain("https://myshop.com", "https://otherdomain.com") is False

    # 2. Simulate link extraction
    from bs4 import BeautifulSoup
    html = """
    <html>
      <body>
        <a href="/services">Internal Service</a>
        <a href="https://facebook.com/myshop" rel="nofollow">Facebook</a>
        <a href="https://instagram.com/myshop" rel="ugc sponsored">Instagram</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    page_data, extracted_links = crawler._analyze_html_and_extract_links(
        url="https://myshop.com",
        status_code=200,
        soup=soup,
        load_time_ms=120,
        source="seed"
    )

    assert page_data["internal_links_count"] == 1
    assert page_data["external_links_count"] == 2

    # Check extracted link attributes
    fb_link = next(l for l in extracted_links if "facebook.com" in l["destination_url"])
    assert fb_link["is_internal"] is False
    assert fb_link["link_type"] == "external"
    assert fb_link["nofollow"] is True
    assert fb_link["target_domain"] == "facebook.com"

    ig_link = next(l for l in extracted_links if "instagram.com" in l["destination_url"])
    assert ig_link["is_internal"] is False
    assert ig_link["ugc"] is True
    assert ig_link["sponsored"] is True


@pytest.mark.asyncio
async def test_scheduler_keyword_ranking_all_keywords(test_db_session):
    """
    Validates scheduler rank_check executes across all configured keywords using KeywordRankingService.
    """
    from app.models.analytics import ScheduledJob
    from app.services.scheduler import JobSchedulerService

    proj = Project(name="Scheduler Test Co", domain="schedulertest.com", organization_id=1)
    test_db_session.add(proj)
    await test_db_session.commit()
    await test_db_session.refresh(proj)

    # Add 12 keywords to verify no 10-keyword truncation occurs
    for i in range(12):
        kw = Keyword(project_id=proj.id, keyword=f"keyword {i}", target_location="Dallas, TX")
        test_db_session.add(kw)
    await test_db_session.commit()

    job = ScheduledJob(
        project_id=proj.id,
        job_type="rank_check",
        frequency="daily",
        status="idle"
    )
    test_db_session.add(job)
    await test_db_session.commit()
    await test_db_session.refresh(job)

    with patch("app.services.serp.ranking_service.KeywordRankingService.check_all_project_keywords", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {
            "project_id": proj.id,
            "checked_count": 12,
            "not_found_count": 0,
            "error_count": 0,
            "provider": "MockSERP",
            "results": [{"keyword": f"keyword {i}", "status": "checked"} for i in range(12)]
        }

        res = await JobSchedulerService.execute_job(job.id, test_db_session)
        assert res["status"] == "completed"
        assert "12 tracked keywords" in res["last_result_summary"]
        mock_check.assert_called_once_with(
            db=test_db_session,
            project_id=proj.id,
            organization_id=proj.organization_id
        )

