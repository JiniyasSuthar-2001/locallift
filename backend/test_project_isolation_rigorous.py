import pytest
import pytest_asyncio
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.models.ranking import GeoGridScan, GeoGridPointResult, KeywordRanking, Keyword
from app.models.audit import SEOAudit, SEOIssue, AuditJob, IssueSeverity, IssueStatus
from app.core.deps import verify_project_access
from app.api.v1.audits import get_canonical_audit, get_latest_audit, list_project_issues, get_diagnostic_summary
from app.api.v1.keywords import get_project_grid

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
async def test_multi_tenant_project_data_isolation(db_session):
    """
    Sets up Project A (Org A, User A) and Project B (Org B, User B) with distinct:
    - Domains
    - Keywords
    - Locations
    - Crawl / SEO audits & issues
    - Geo-Grid scans & point results
    - Daily rankings

    Verifies:
    1. User A querying Project A gets ONLY Project A data.
    2. User B querying Project B gets ONLY Project B data.
    3. User A querying Project B endpoints raises HTTP 403 Forbidden.
    4. User B querying Project A endpoints raises HTTP 403 Forbidden.
    5. Database queries never leak cross-tenant rows.
    """
    # 1. Setup Tenant A
    org_a = Organization(id=1, name="Tenant A Corp", slug="tenant-a")
    db_session.add(org_a)
    user_a = User(id=1, email="alice@tenant-a.com", full_name="Alice", hashed_password="pw", is_active=True)
    db_session.add(user_a)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role=OrgRole.ADMIN))

    proj_a = Project(id=101, organization_id=org_a.id, name="Project Alpha", domain="alpha.example.com", status="active")
    db_session.add(proj_a)
    await db_session.flush()

    loc_a = Location(id=1001, project_id=proj_a.id, name="Alpha HQ", latitude=-37.8136, longitude=144.9631)
    kw_a = Keyword(id=5001, project_id=proj_a.id, keyword="alpha plumbing", target_location="Melbourne")
    db_session.add_all([loc_a, kw_a])

    audit_a = SEOAudit(
        id=7001,
        project_id=proj_a.id,
        overall_score=88,
        pages_analyzed=12,
        critical_issues=1,
        warnings=2,
        passed_checks=9,
        details={"audit_origin": "alpha_project_only"}
    )
    issue_a = SEOIssue(
        id=9001,
        project_id=proj_a.id,
        category="Technical SEO",
        severity=IssueSeverity.CRITICAL,
        status=IssueStatus.OPEN,
        title="Alpha 404 Page Found",
        evidence="https://alpha.example.com/broken",
        why_it_matters="Hurts crawlability"
    )
    scan_a = GeoGridScan(
        id=3001,
        project_id=proj_a.id,
        keyword_id=kw_a.id,
        center_lat=-37.8136,
        center_lng=144.9631,
        grid_size=3,
        radius_km=5.0,
        scan_status="SUCCESS",
        total_points=9,
        completed_points=9,
        ranking_found_points=9
    )
    point_a = GeoGridPointResult(
        scan_id=scan_a.id,
        project_id=proj_a.id,
        keyword_id=kw_a.id,
        point_number=0,
        latitude=-37.8136,
        longitude=144.9631,
        keyword="alpha plumbing",
        provider="serpapi",
        status="SUCCESS",
        rank=1,
        matched_domain="alpha.example.com"
    )
    db_session.add_all([audit_a, issue_a, scan_a, point_a])

    # 2. Setup Tenant B
    org_b = Organization(id=2, name="Tenant B Corp", slug="tenant-b")
    db_session.add(org_b)
    user_b = User(id=2, email="bob@tenant-b.com", full_name="Bob", hashed_password="pw", is_active=True)
    db_session.add(user_b)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role=OrgRole.ADMIN))

    proj_b = Project(id=202, organization_id=org_b.id, name="Project Beta", domain="beta.example.com", status="active")
    db_session.add(proj_b)
    await db_session.flush()

    loc_b = Location(id=2002, project_id=proj_b.id, name="Beta HQ", latitude=40.7128, longitude=-74.0060)
    kw_b = Keyword(id=6002, project_id=proj_b.id, keyword="beta roofing", target_location="New York")
    db_session.add_all([loc_b, kw_b])

    audit_b = SEOAudit(
        id=8002,
        project_id=proj_b.id,
        overall_score=45,
        pages_analyzed=5,
        critical_issues=8,
        warnings=4,
        passed_checks=1,
        details={"audit_origin": "beta_project_only"}
    )
    issue_b = SEOIssue(
        id=9002,
        project_id=proj_b.id,
        category="Security",
        severity=IssueSeverity.WARNING,
        status=IssueStatus.OPEN,
        title="Beta Missing SSL",
        evidence="http://beta.example.com/",
        why_it_matters="Insecure transport"
    )
    scan_b = GeoGridScan(
        id=4002,
        project_id=proj_b.id,
        keyword_id=kw_b.id,
        center_lat=40.7128,
        center_lng=-74.0060,
        grid_size=3,
        radius_km=10.0,
        scan_status="SUCCESS",
        total_points=9,
        completed_points=9,
        ranking_found_points=2
    )
    point_b = GeoGridPointResult(
        scan_id=scan_b.id,
        project_id=proj_b.id,
        keyword_id=kw_b.id,
        point_number=0,
        latitude=40.7128,
        longitude=-74.0060,
        keyword="beta roofing",
        provider="serpapi",
        status="SUCCESS",
        rank=7,
        matched_domain="beta.example.com"
    )
    db_session.add_all([audit_b, issue_b, scan_b, point_b])
    await db_session.commit()

    # 3. VERIFY AUTHORIZATION ENFORCEMENT
    # Alice accessing Project B must raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await verify_project_access(proj_b.id, user_a, db_session)
    assert exc_info.value.status_code == 403

    # Bob accessing Project A must raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await verify_project_access(proj_a.id, user_b, db_session)
    assert exc_info.value.status_code == 403

    # 4. VERIFY AUDIT & CRAWL DATA ISOLATION
    # Alice requesting Project A canonical audit gets ONLY Alpha
    audit_data_a = await get_canonical_audit(project_id=proj_a.id, current_user=user_a, db=db_session)
    assert audit_data_a["domain"] == "alpha.example.com"
    assert audit_data_a["health_score"] == 88
    assert audit_data_a["audit_origin"] == "alpha_project_only"

    # Bob requesting Project B canonical audit gets ONLY Beta
    audit_data_b = await get_canonical_audit(project_id=proj_b.id, current_user=user_b, db=db_session)
    assert audit_data_b["domain"] == "beta.example.com"
    assert audit_data_b["health_score"] == 45
    assert audit_data_b["audit_origin"] == "beta_project_only"

    # Alice blocked from accessing Project B audit
    with pytest.raises(HTTPException) as exc:
        await get_canonical_audit(project_id=proj_b.id, current_user=user_a, db=db_session)
    assert exc.value.status_code == 403

    # 5. VERIFY ISSUES ISOLATION
    issues_a = await list_project_issues(project_id=proj_a.id, current_user=user_a, db=db_session)
    assert len(issues_a) == 1
    assert issues_a[0].title == "Alpha 404 Page Found"

    issues_b = await list_project_issues(project_id=proj_b.id, current_user=user_b, db=db_session)
    assert len(issues_b) == 1
    assert issues_b[0].title == "Beta Missing SSL"

    # 6. VERIFY GEOGRID ISOLATION
    from unittest.mock import AsyncMock
    mock_request = AsyncMock()
    grid_a = await get_project_grid(request=mock_request, project_id=proj_a.id, current_user=user_a, db=db_session)
    assert grid_a is not None
    assert grid_a.project_id == proj_a.id
    assert grid_a.points[0]["matched_domain"] == "alpha.example.com"
    assert grid_a.points[0]["rank"] == 1

    grid_b = await get_project_grid(request=mock_request, project_id=proj_b.id, current_user=user_b, db=db_session)
    assert grid_b is not None
    assert grid_b.project_id == proj_b.id
    assert grid_b.points[0]["matched_domain"] == "beta.example.com"
    assert grid_b.points[0]["rank"] == 7

    # Alice cannot read Bob's grid
    with pytest.raises(HTTPException) as exc:
        await get_project_grid(request=mock_request, project_id=proj_b.id, current_user=user_a, db=db_session)
    assert exc.value.status_code == 403
