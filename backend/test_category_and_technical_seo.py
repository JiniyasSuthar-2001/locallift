"""
Integration & Unit Tests for Category Taxonomy and Technical SEO Scan Orchestration.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.database import Base
from app.models.user import User, Organization
from app.models.project import Project, Website
from app.models.local_seo import BusinessProfile
from app.models.audit import (
    SEOAudit, SEOIssue, WebsitePage, AuditJob, AuditJobStatus,
    LocalAuditRun, LocalAuditFinding, IssueSeverity, IssueStatus
)
from app.services.category_taxonomy import CategoryTaxonomy, BUSINESS_CATEGORIES_DATA
from app.services.local_seo.audit_framework import LocalSEOAuditFramework


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


# =========================================================================
# PART 1: CATEGORY TAXONOMY TESTS
# =========================================================================

def test_category_taxonomy_unique_ids_and_slugs():
    """Verify that all category IDs and slugs in taxonomy are unique and non-empty."""
    ids = set()
    slugs = set()
    for cat in BUSINESS_CATEGORIES_DATA:
        assert cat.get("id"), "Category missing id"
        assert cat.get("name"), "Category missing name"
        assert cat.get("slug"), "Category missing slug"
        assert cat.get("group"), "Category missing group"
        
        c_id = cat["id"].lower()
        c_slug = cat["slug"].lower()
        
        assert c_id not in ids, f"Duplicate category id: {c_id}"
        assert c_slug not in slugs, f"Duplicate category slug: {c_slug}"
        ids.add(c_id)
        slugs.add(c_slug)


def test_category_taxonomy_preserves_legacy_ids():
    """Verify all 107 legacy category IDs are preserved."""
    legacy_sample = [
        "dentist", "dental-clinic", "orthodontist", "plumber", "electrician",
        "hvac-contractor", "roofing-contractor", "general-contractor", "law-firm",
        "personal-injury-attorney", "restaurant", "cafe", "auto-repair-shop",
        "car-dealer", "real-estate-agency", "accountant", "marketing-agency",
        "hair-salon", "barber-shop", "gym", "hotel", "veterinarian", "clothing-store",
        "event-venue", "photographer", "moving-company", "preschool", "local-business",
        "computer-repair-service", "it-services-consultant"
    ]
    for leg_id in legacy_sample:
        cat = CategoryTaxonomy.get_by_id(leg_id)
        assert cat is not None, f"Legacy category ID missing: {leg_id}"
        assert cat["id"] == leg_id


def test_it_category_family_coverage_and_search():
    """Verify IT categories and aliases can be discovered via ranked search."""
    # 1. Exact IT search
    it_res = CategoryTaxonomy.search("IT")
    assert len(it_res) > 0
    it_names = [c["name"] for c in it_res]
    assert any("IT Services" in n for n in it_names)

    # 2. Cyber security search
    cyber_res = CategoryTaxonomy.search("cyber security")
    assert len(cyber_res) > 0
    cyber_names = [c["name"] for c in cyber_res]
    assert "Cybersecurity Company" in cyber_names

    # 3. Software search
    soft_res = CategoryTaxonomy.search("software")
    assert len(soft_res) > 0
    soft_names = [c["name"] for c in soft_res]
    assert any("Software" in n for n in soft_names)

    # 4. Doctor search
    doc_res = CategoryTaxonomy.search("doctor")
    assert len(doc_res) > 0
    assert doc_res[0]["name"] == "Doctor"

    # 5. Construction search
    const_res = CategoryTaxonomy.search("construction")
    assert len(const_res) > 0
    const_names = [c["name"] for c in const_res]
    assert any("Contractor" in n or "Construction" in n for n in const_names)


def test_category_popular_and_hierarchy():
    """Verify popular categories and hierarchical catalog structuring."""
    popular = CategoryTaxonomy.search(popular_only=True, limit=50)
    assert len(popular) >= 20, "Should have rich popular categories"
    
    # Check diverse representation in popular
    groups_in_popular = {c["group"] for c in popular}
    assert "Information Technology (IT)" in groups_in_popular
    assert "Healthcare & Medical" in groups_in_popular or "Dental & Oral Health" in groups_in_popular
    assert "Home Services & Trades" in groups_in_popular
    assert "Legal & Law" in groups_in_popular

    # Hierarchy catalog check
    hier = CategoryTaxonomy.get_hierarchical_catalog()
    assert hier["total_groups"] >= 20
    assert hier["total_categories"] == len(BUSINESS_CATEGORIES_DATA)
    assert any(g["name"] == "Information Technology (IT)" for g in hier["groups"])


# =========================================================================
# PART 2: TECHNICAL SEO SCAN TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_technical_seo_with_valid_fresh_crawl(test_db_session: AsyncSession):
    """
    Test Case 1 & 2: Valid fresh crawl exists -> Local SEO Audit reuses it,
    evaluates Category 15 with full multi-check evidence & provenance.
    """
    db = test_db_session

    # 1. Setup Organization & Project
    org = Organization(name="Test Org", slug="test-org")
    db.add(org)
    await db.flush()

    user = User(email="tech_seo@test.com", hashed_password="pwd")
    db.add(user)
    await db.flush()

    project = Project(
        name="Apex Tech Solutions",
        domain="apextech.example.com",
        organization_id=org.id
    )
    db.add(project)
    await db.flush()

    website = Website(project_id=project.id, url="https://apextech.example.com", status="completed")
    db.add(website)
    await db.flush()

    # 2. Add Crawled Pages (Clean pages without errors)
    p1 = WebsitePage(
        website_id=website.id,
        url="https://apextech.example.com",
        status_code=200,
        title="Apex Tech - Managed IT Services",
        canonical_url="https://apextech.example.com",
        is_indexable=True,
        load_time_ms=350,
        internal_links_count=12,
        broken_links=[]
    )
    p2 = WebsitePage(
        website_id=website.id,
        url="https://apextech.example.com/cybersecurity",
        status_code=200,
        title="Cybersecurity Solutions",
        canonical_url="https://apextech.example.com/cybersecurity",
        is_indexable=True,
        load_time_ms=420,
        internal_links_count=8,
        broken_links=[]
    )
    db.add_all([p1, p2])

    # 3. Add Valid SEOAudit
    audit = SEOAudit(
        project_id=project.id,
        audit_type="website_audit",
        overall_score=92,
        pages_analyzed=2,
        critical_issues=0,
        warnings=1,
        passed_checks=18,
        summary="Crawl completed successfully"
    )
    db.add(audit)

    # 4. Add Completed AuditJob
    job = AuditJob(
        project_id=project.id,
        organization_id=org.id,
        job_type="website_audit",
        status=AuditJobStatus.COMPLETED,
        progress=100.0,
        current_stage="Completed",
        start_url="https://apextech.example.com",
        completed_at=datetime.now(timezone.utc)
    )
    db.add(job)
    await db.commit()

    # 5. Run Local SEO Audit
    local_run = await LocalSEOAuditFramework.run_audit(
        project_id=project.id,
        db=db,
        freshness_hours=24,
        force_crawl=False
    )

    assert local_run is not None
    # Category 15 findings verification
    tech_findings = [f for f in local_run.findings if f.category == "technical_seo"]
    assert len(tech_findings) >= 4, "Should evaluate multiple technical checks"
    
    health_f = next((f for f in tech_findings if f.check_key == "crawl_health_score"), None)
    assert health_f is not None
    assert health_f.status == "PASS"
    assert "92/100" in health_f.evidence
    assert "Job #" in health_f.evidence or "Audit #" in health_f.evidence

    http_f = next((f for f in tech_findings if f.check_key == "http_status_errors"), None)
    assert http_f is not None
    assert http_f.status == "PASS"


@pytest.mark.asyncio
async def test_technical_seo_with_broken_pages(test_db_session: AsyncSession):
    """
    Test Case: Crawl with 404 errors & broken links produces truthful FAIL findings.
    """
    db = test_db_session

    org = Organization(name="Broken Test Org", slug="broken-test-org")
    db.add(org)
    await db.flush()

    project = Project(name="Broken Website Co", domain="broken.example.com", organization_id=org.id)
    db.add(project)
    await db.flush()

    website = Website(project_id=project.id, url="https://broken.example.com", status="completed")
    db.add(website)
    await db.flush()

    # 404 Page and broken links
    p1 = WebsitePage(
        website_id=website.id,
        url="https://broken.example.com/missing-service",
        status_code=404,
        title="Page Not Found",
        is_indexable=False,
        load_time_ms=800,
        broken_links=["https://broken.example.com/dead-link"]
    )
    p2 = WebsitePage(
        website_id=website.id,
        url="https://broken.example.com",
        status_code=200,
        title="Home",
        is_indexable=True,
        load_time_ms=500,
        broken_links=["https://broken.example.com/another-dead-link"]
    )
    db.add_all([p1, p2])

    audit = SEOAudit(
        project_id=project.id,
        audit_type="website_audit",
        overall_score=55,
        pages_analyzed=2,
        critical_issues=2,
        warnings=3,
        passed_checks=8
    )
    db.add(audit)

    job = AuditJob(
        project_id=project.id,
        organization_id=org.id,
        job_type="website_audit",
        status=AuditJobStatus.COMPLETED_WITH_ERRORS,
        broken_links_found=2,
        start_url="https://broken.example.com",
        completed_at=datetime.now(timezone.utc)
    )
    db.add(job)
    await db.commit()

    local_run = await LocalSEOAuditFramework.run_audit(
        project_id=project.id,
        db=db,
        freshness_hours=24,
        force_crawl=False
    )

    tech_findings = [f for f in local_run.findings if f.category == "technical_seo"]
    http_f = next((f for f in tech_findings if f.check_key == "http_status_errors"), None)
    assert http_f is not None
    assert http_f.status == "FAIL"
    assert "missing-service" in http_f.evidence

    broken_f = next((f for f in tech_findings if f.check_key == "broken_links"), None)
    assert broken_f is not None
    assert broken_f.status == "FAIL"


@pytest.mark.asyncio
async def test_technical_seo_failed_crawl_reporting(test_db_session: AsyncSession):
    """
    Test Case 4 & 5: When crawl fails or is blocked, Technical SEO reports ERROR / NOT_VERIFIED
    with the exact failure reason, NEVER a false PASS or fake 80 score.
    """
    db = test_db_session

    org = Organization(name="Fail Org", slug="fail-org")
    db.add(org)
    await db.flush()

    project = Project(name="Blocked Site", domain="blocked.example.com", organization_id=org.id)
    db.add(project)
    await db.flush()

    # Failed Job
    job = AuditJob(
        project_id=project.id,
        organization_id=org.id,
        job_type="website_audit",
        status=AuditJobStatus.FAILED,
        error_message="Robots protection blocked the crawl: target robots.txt Disallow: /",
        start_url="https://blocked.example.com",
        failed_at=datetime.now(timezone.utc)
    )
    db.add(job)
    await db.commit()

    local_run = await LocalSEOAuditFramework.run_audit(
        project_id=project.id,
        db=db,
        freshness_hours=24,
        force_crawl=False
    )

    tech_findings = [f for f in local_run.findings if f.category == "technical_seo"]
    assert len(tech_findings) > 0
    err_f = tech_findings[0]
    assert err_f.status in ("ERROR", "NOT_VERIFIED")
    assert "Robots protection" in err_f.evidence or "failed" in err_f.evidence.lower()
    assert err_f.verification_status == "NOT_VERIFIED"
