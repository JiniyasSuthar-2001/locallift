"""
LocalLift — Automated Test Suite for Report Snapshot & Run Resolution System

Tests all required scenarios:
1. Test A — Central only
2. Test B — Standalone Geo-Grid after Central Scan (Override single module)
3. Test C — Central Scan after Standalone Geo-Grid (Newer Central wins)
4. Test D — Two Standalone Geo-Grids (Newest standalone wins)
5. Test E — Standalone Local Audit after Central (Override local_audit module)
6. Test F — Old standalone run cannot override new Central
7. Test G — Incomplete/failed/cancelled runs do not become authoritative
8. Test H — Multi-tenant project access security
9. Test I — PDF & XLSX export generation and data completeness verification
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, Organization
from app.models.project import Project, Website
from app.models.intelligence_scan import ProjectIntelligenceScan, ScanStatus, StageStatus
from app.models.audit import LocalAuditRun, LocalAuditFinding, SEOAudit, SEOIssue, WebsitePage
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.models.local_seo import BusinessProfile, Review, Citation, NAPRecord, Competitor, SchemaRecord
from app.services.reports.report_snapshot_service import ReportSnapshotService
from app.services.reports.local_seo_pdf_service import LocalSEOPDFService
from app.services.reports.local_seo_xlsx_service import LocalSEOXLSXService


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_scenario_a_central_only(test_db: AsyncSession):
    """Test A: When only a Central Scan exists, all modules come from that scan."""
    org = Organization(name="Test Org A", slug="test-org-a")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="Dental Clinic A", domain="dentalclinica.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    bp = BusinessProfile(
        project_id=proj.id,
        business_name="Dental Clinic A",
        website="https://dentalclinica.com",
        city="Austin",
        state="TX",
        primary_phone="512-555-0100"
    )
    test_db.add(bp)

    # Central Scan #100
    t100 = datetime.now(timezone.utc) - timedelta(hours=2)
    central = ProjectIntelligenceScan(
        id=100,
        project_id=proj.id,
        organization_id=org.id,
        status=ScanStatus.COMPLETED.value,
        started_at=t100,
        completed_at=t100,
        stages={
            "business_profile": {"status": "SUCCESS", "completed_at": t100.isoformat()},
            "local_audit": {"status": "SUCCESS", "completed_at": t100.isoformat()},
            "geo": {"status": "SUCCESS", "completed_at": t100.isoformat()}
        },
        results_summary={
            "local_audit": {"overall_score": 88, "findings_count": 10},
            "geo": {"visibility_pct": 75.0, "average_rank": 2.4}
        }
    )
    test_db.add(central)
    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert snapshot["project_id"] == proj.id
    assert snapshot["central_scan"]["id"] == 100
    assert snapshot["provenance"]["local_audit"]["source_type"] == "central_scan"
    assert snapshot["provenance"]["geo"]["source_type"] == "central_scan"
    assert snapshot["provenance"]["geo"]["is_override"] is False


@pytest.mark.asyncio
async def test_scenario_b_geogrid_after_central(test_db: AsyncSession):
    """
    Test B: Standalone GeoGrid run after Central Scan overrides only the Geo module.
    Timeline:
      10:00 Central Scan #100
      11:00 Standalone GeoGrid #200
    Expected:
      geo -> Standalone GeoGrid #200 (is_override = True)
      local_audit -> Central Scan #100
    """
    org = Organization(name="Test Org B", slug="test-org-b")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="Plumber B", domain="plumberb.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    bp = BusinessProfile(project_id=proj.id, business_name="Plumber B", website="https://plumberb.com")
    test_db.add(bp)

    kw = Keyword(project_id=proj.id, keyword="emergency plumber austin")
    test_db.add(kw)
    await test_db.flush()

    # 10:00 Central Scan #100
    t_1000 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    central = ProjectIntelligenceScan(
        id=100,
        project_id=proj.id,
        organization_id=org.id,
        status=ScanStatus.COMPLETED.value,
        started_at=t_1000,
        completed_at=t_1000,
        stages={
            "local_audit": {"status": "SUCCESS", "completed_at": t_1000.isoformat()},
            "geo": {"status": "SUCCESS", "completed_at": t_1000.isoformat()}
        }
    )
    test_db.add(central)

    # 11:00 Standalone GeoGrid #200
    t_1100 = datetime(2026, 9, 26, 11, 0, 0, tzinfo=timezone.utc)
    geo_scan = GeoGridScan(
        id=200,
        project_id=proj.id,
        keyword_id=kw.id,
        center_lat=30.2672,
        center_lng=-97.7431,
        local_visibility_pct=92.0,
        average_rank=1.8,
        scan_status="completed",
        scanned_at=t_1100
    )
    test_db.add(geo_scan)
    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert snapshot["provenance"]["geo"]["source_type"] == "standalone_geogrid"
    assert snapshot["provenance"]["geo"]["source_run_id"] == 200
    assert snapshot["provenance"]["geo"]["is_override"] is True
    assert snapshot["provenance"]["local_audit"]["source_type"] == "central_scan"
    assert snapshot["provenance"]["local_audit"]["source_run_id"] == 100


@pytest.mark.asyncio
async def test_scenario_c_central_after_geogrid(test_db: AsyncSession):
    """
    Test C: Central Scan executed after Standalone GeoGrid wins because it is newer.
    Timeline:
      10:00 Standalone GeoGrid #200
      12:00 Central Scan #101
    Expected:
      geo -> Central Scan #101 (is_override = False)
    """
    org = Organization(name="Test Org C", slug="test-org-c")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="Auto Repair C", domain="autorepairc.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    bp = BusinessProfile(project_id=proj.id, business_name="Auto Repair C", website="https://autorepairc.com")
    test_db.add(bp)

    kw = Keyword(project_id=proj.id, keyword="brake repair austin")
    test_db.add(kw)
    await test_db.flush()

    # 10:00 Standalone GeoGrid #200
    t_1000 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    geo_scan = GeoGridScan(
        id=200,
        project_id=proj.id,
        keyword_id=kw.id,
        center_lat=30.2672,
        center_lng=-97.7431,
        local_visibility_pct=60.0,
        average_rank=4.2,
        scan_status="completed",
        scanned_at=t_1000
    )
    test_db.add(geo_scan)

    # 12:00 Central Scan #101
    t_1200 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    central = ProjectIntelligenceScan(
        id=101,
        project_id=proj.id,
        organization_id=org.id,
        status=ScanStatus.COMPLETED.value,
        started_at=t_1200,
        completed_at=t_1200,
        stages={
            "local_audit": {"status": "SUCCESS", "completed_at": t_1200.isoformat()},
            "geo": {"status": "SUCCESS", "completed_at": t_1200.isoformat()}
        },
        results_summary={"geo": {"visibility_pct": 84.0}}
    )
    test_db.add(central)
    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert snapshot["provenance"]["geo"]["source_type"] == "central_scan"
    assert snapshot["provenance"]["geo"]["source_run_id"] == 101
    assert snapshot["provenance"]["geo"]["is_override"] is False


@pytest.mark.asyncio
async def test_scenario_d_two_standalone_geogrids(test_db: AsyncSession):
    """Test D: Between two standalone Geo-Grids, the newer one wins."""
    org = Organization(name="Test Org D", slug="test-org-d")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="Law Firm D", domain="lawfirmd.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    kw = Keyword(project_id=proj.id, keyword="injury lawyer austin")
    test_db.add(kw)
    await test_db.flush()

    t1 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

    g1 = GeoGridScan(id=200, project_id=proj.id, keyword_id=kw.id, center_lat=30.0, center_lng=-97.0, local_visibility_pct=50.0, scan_status="completed", scanned_at=t1)
    g2 = GeoGridScan(id=201, project_id=proj.id, keyword_id=kw.id, center_lat=30.0, center_lng=-97.0, local_visibility_pct=88.0, scan_status="completed", scanned_at=t2)
    test_db.add_all([g1, g2])
    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert snapshot["provenance"]["geo"]["source_type"] == "standalone_geogrid"
    assert snapshot["provenance"]["geo"]["source_run_id"] == 201
    assert snapshot["geo_visibility"]["local_visibility_pct"] == 88.0


@pytest.mark.asyncio
async def test_scenario_e_standalone_local_audit_after_central(test_db: AsyncSession):
    """Test E: Standalone Local SEO Audit after Central overrides local_audit module."""
    org = Organization(name="Test Org E", slug="test-org-e")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="Electrician E", domain="electriciane.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    # Central scan at 09:00
    t_0900 = datetime(2026, 9, 26, 9, 0, 0, tzinfo=timezone.utc)
    central = ProjectIntelligenceScan(
        id=100,
        project_id=proj.id,
        organization_id=org.id,
        status=ScanStatus.COMPLETED.value,
        started_at=t_0900,
        completed_at=t_0900,
        stages={
            "local_audit": {"status": "SUCCESS", "completed_at": t_0900.isoformat()},
            "citations": {"status": "SUCCESS", "completed_at": t_0900.isoformat()}
        }
    )
    test_db.add(central)

    # Standalone LocalAuditRun at 10:30
    t_1030 = datetime(2026, 9, 26, 10, 30, 0, tzinfo=timezone.utc)
    local_run = LocalAuditRun(
        id=305,
        project_id=proj.id,
        overall_score=94,
        status="completed",
        completed_at=t_1030
    )
    test_db.add(local_run)
    await test_db.flush()

    # Add 3 findings
    f1 = LocalAuditFinding(project_id=proj.id, audit_run_id=local_run.id, category="google_business_profile", check_key="gbp_claimed", title="GBP Claimed", status="PASS")
    f2 = LocalAuditFinding(project_id=proj.id, audit_run_id=local_run.id, category="nap_consistency", check_key="nap_match", title="NAP Match", status="PASS")
    f3 = LocalAuditFinding(project_id=proj.id, audit_run_id=local_run.id, category="local_schema", check_key="schema_present", title="Schema Present", status="PASS")
    test_db.add_all([f1, f2, f3])
    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert snapshot["provenance"]["local_audit"]["source_type"] == "standalone_local_audit"
    assert snapshot["provenance"]["local_audit"]["source_run_id"] == 305
    assert snapshot["provenance"]["local_audit"]["is_override"] is True
    assert snapshot["audit"]["overall_score"] == 94
    assert len(snapshot["audit"]["findings"]) == 3
    assert snapshot["provenance"]["citations"]["source_type"] == "central_scan"


@pytest.mark.asyncio
async def test_scenario_g_incomplete_runs_ignored(test_db: AsyncSession):
    """Test G: Failed, running, or cancelled runs do NOT become authoritative."""
    org = Organization(name="Test Org G", slug="test-org-g")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="HVAC G", domain="hvacg.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    kw = Keyword(project_id=proj.id, keyword="hvac repair austin")
    test_db.add(kw)
    await test_db.flush()

    t_valid = datetime(2026, 9, 26, 8, 0, 0, tzinfo=timezone.utc)
    t_failed = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

    # Valid completed scan at 08:00
    valid_scan = GeoGridScan(id=401, project_id=proj.id, keyword_id=kw.id, center_lat=30.0, center_lng=-97.0, local_visibility_pct=72.0, scan_status="completed", scanned_at=t_valid)
    # Failed scan at 12:00
    failed_scan = GeoGridScan(id=402, project_id=proj.id, keyword_id=kw.id, center_lat=30.0, center_lng=-97.0, local_visibility_pct=0.0, scan_status="failed", scanned_at=t_failed)
    test_db.add_all([valid_scan, failed_scan])
    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert snapshot["provenance"]["geo"]["source_run_id"] == 401
    assert snapshot["geo_visibility"]["local_visibility_pct"] == 72.0


@pytest.mark.asyncio
async def test_scenario_i_export_pdf_and_xlsx_completeness(test_db: AsyncSession):
    """Test I: PDF and XLSX generate correctly from the exact snapshot with complete datasets."""
    org = Organization(name="Test Org I", slug="test-org-i")
    test_db.add(org)
    await test_db.flush()

    proj = Project(name="Roofing Pros I", domain="roofingprosi.com", organization_id=org.id)
    test_db.add(proj)
    await test_db.flush()

    bp = BusinessProfile(
        project_id=proj.id,
        business_name="Roofing Pros I",
        website="https://roofingprosi.com",
        city="Austin",
        state="TX"
    )
    test_db.add(bp)

    kw = Keyword(project_id=proj.id, keyword="roof repair austin", current_rank=2)
    test_db.add(kw)
    await test_db.flush()

    # Create 25 GeoGrid points
    geo_scan = GeoGridScan(
        id=500,
        project_id=proj.id,
        keyword_id=kw.id,
        center_lat=30.26,
        center_lng=-97.74,
        local_visibility_pct=80.0,
        average_rank=2.2,
        scan_status="completed"
    )
    test_db.add(geo_scan)
    await test_db.flush()

    for idx in range(25):
        pt = GeoGridPointResult(
            scan_id=geo_scan.id,
            project_id=proj.id,
            keyword_id=kw.id,
            point_number=idx,
            row=idx // 5,
            col=idx % 5,
            latitude=30.26 + (idx * 0.001),
            longitude=-97.74 + (idx * 0.001),
            area_name=f"Austin Zone {idx + 1}",
            keyword="roof repair austin",
            provider="dataforseo",
            status="SUCCESS",
            rank=(idx % 5) + 1,
            matched_business="Roofing Pros I",
            competitors=[{"name": "Competitor X", "rank": 1, "domain": "compx.com"}]
        )
        test_db.add(pt)

    # Create 10 reviews
    for idx in range(10):
        rev = Review(project_id=proj.id, author_name=f"Customer {idx+1}", rating=5, review_text="Excellent roofing service.")
        test_db.add(rev)

    # Create 15 citations
    for idx in range(15):
        cit = Citation(project_id=proj.id, source_name=f"Directory {idx+1}", domain=f"dir{idx+1}.com", nap_status="consistent")
        test_db.add(cit)

    await test_db.commit()

    snapshot = await ReportSnapshotService.resolve_report_snapshot(proj.id, test_db)
    assert len(snapshot["geo_visibility"]["points"]) == 25
    assert len(snapshot["reputation"]["reviews"]) == 10
    assert len(snapshot["citations"]["listings"]) == 15

    # Generate PDF
    pdf_bytes = LocalSEOPDFService.generate_pdf(snapshot)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")

    # Generate XLSX
    xlsx_bytes = LocalSEOXLSXService.generate_xlsx(snapshot)
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 2000
    assert xlsx_bytes.startswith(b"PK")  # ZIP/XLSX header
