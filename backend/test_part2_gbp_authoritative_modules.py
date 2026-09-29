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
from app.models.project import Project, Location, Website
from app.models.connections import GoogleConnection
from app.models.gbp import GoogleBusinessProfile, GoogleAccount
from app.models.audit import LocalAuditRun, LocalAuditFinding
from app.models.local_seo import BusinessProfile, Review, Citation, SchemaRecord
from app.models.template import Template
from app.core.security import encrypt_token

from app.services.local_seo.audit_framework import LocalSEOAuditFramework, FindingStatus, VerificationStatus
from app.services.local_seo.nap_service import NAPComparisonService
from app.services.local_seo.business_profile_service import BusinessProfileService
from app.services.schema_intelligence import SchemaIntelligenceEngine
from app.services.template_service import TemplateEngine
from app.services.category_taxonomy import CategoryTaxonomy


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        yield session


# ============================================================
# 1. LOCAL SEO AUDIT (GBP Connected vs. Disconnected)
# ============================================================

@pytest.mark.asyncio
async def test_gbp_connected_local_seo_audit(async_db: AsyncSession):
    """Test 1: When GBP is connected, Local SEO Audit traces exact bound GBP with correct provenance."""
    org = Organization(name="Test Org", slug="test-org-1")
    async_db.add(org)
    await async_db.flush()

    user = User(email="owner@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj = Project(
        name="Alpha Health Clinic",
        domain="alphahealth.com",
        organization_id=org.id,
        country="US",
        primary_category="Medical Clinic"
    )
    async_db.add(proj)
    await async_db.flush()

    # Exact bound GBP
    gbp = GoogleBusinessProfile(
        project_id=proj.id,
        business_name="Alpha Health Clinic Official",
        primary_category="Medical clinic",
        additional_categories=["Urgent care center", "Doctor"],
        address="100 Medical Plaza, Suite 200",
        phone="+15125550100",
        website_url="https://alphahealth.com",
        latitude=30.2672,
        longitude=-97.7431,
        photos_count=15,
        posts_count=4,
        search_impressions=1200,
        call_clicks=85,
        website_clicks=340,
        is_verified=True,
        last_synced_at=datetime(2026, 9, 23, 14, 30, tzinfo=timezone.utc)
    )
    async_db.add(gbp)
    await async_db.commit()

    report = await LocalSEOAuditFramework.run_audit(proj.id, async_db)
    assert report is not None

    findings_res = await async_db.execute(select(LocalAuditFinding).where(LocalAuditFinding.audit_run_id == report.id))
    findings = findings_res.scalars().all()

    # Category 1: Google Business Profile
    gbp_finding = next((f for f in findings if f.category == "google_business_profile"), None)
    assert gbp_finding is not None
    assert gbp_finding.status == FindingStatus.PASS.value
    assert gbp_finding.source == "Connected Google Business Profile"
    assert "Alpha Health Clinic Official" in gbp_finding.evidence
    assert "23 Sep 2026" in gbp_finding.evidence

    # Category 2: Categories Taxonomy
    cat_finding = next((f for f in findings if f.category == "categories_taxonomy"), None)
    assert cat_finding is not None
    assert cat_finding.status == FindingStatus.PASS.value
    assert cat_finding.source == "Connected Google Business Profile"
    assert "Medical clinic" in cat_finding.evidence
    assert "Urgent care center" in cat_finding.evidence

    # Category 6: Proximity Coordinates
    prox_finding = next((f for f in findings if f.category == "proximity_location"), None)
    assert prox_finding is not None
    assert prox_finding.status == FindingStatus.PASS.value
    assert prox_finding.source == "Connected Google Business Profile"
    assert "30.2672" in prox_finding.evidence

    # Category 10: GBP Photos
    photos_finding = next((f for f in findings if f.category == "gbp_media"), None)
    assert photos_finding is not None
    assert photos_finding.status == FindingStatus.PASS.value
    assert photos_finding.source == "Connected Google Business Profile"
    assert "15 photos" in photos_finding.evidence

    # Category 12: GBP Posts
    posts_finding = next((f for f in findings if f.category == "gbp_activity"), None)
    assert posts_finding is not None
    assert posts_finding.status == FindingStatus.PASS.value
    assert posts_finding.source == "Connected Google Business Profile"

    # Category 19: User Engagement
    eng_finding = next((f for f in findings if f.category == "user_engagement"), None)
    assert eng_finding is not None
    assert eng_finding.status == FindingStatus.PASS.value
    assert eng_finding.source == "Connected Google Business Profile"
    assert "1200 impressions" in eng_finding.evidence


@pytest.mark.asyncio
async def test_gbp_disconnected_local_seo_audit(async_db: AsyncSession):
    """Test 2: When GBP is disconnected, Local SEO Audit gracefully falls back to Project Data with NOT_VERIFIED."""
    org = Organization(name="Test Org Disconnected", slug="test-org-disc")
    async_db.add(org)
    await async_db.flush()

    user = User(email="owner2@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj = Project(
        name="Beta Legal Group",
        domain="betalegal.com",
        organization_id=org.id,
        country="US",
        primary_category="Lawyer"
    )
    async_db.add(proj)
    await async_db.flush()

    loc = Location(
        project_id=proj.id,
        name="Beta HQ",
        address="500 Law Lane",
        city="Denver",
        state="CO",
        postal_code="80202",
        phone="+13035550199",
        country="US"
    )
    async_db.add(loc)
    await async_db.commit()

    report = await LocalSEOAuditFramework.run_audit(proj.id, async_db)
    assert report is not None

    findings_res = await async_db.execute(select(LocalAuditFinding).where(LocalAuditFinding.audit_run_id == report.id))
    findings = findings_res.scalars().all()

    # Category 1: Should be NOT_VERIFIED with source Project Data
    gbp_finding = next((f for f in findings if f.category == "google_business_profile"), None)
    assert gbp_finding is not None
    assert gbp_finding.status == FindingStatus.NOT_VERIFIED.value
    assert gbp_finding.source == "Project Data"

    # Category 10: Media not verified
    photos_finding = next((f for f in findings if f.category == "gbp_media"), None)
    assert photos_finding is not None
    assert photos_finding.status == FindingStatus.NOT_VERIFIED.value
    assert photos_finding.source == "Project Data"

    # Category 12: Activity not verified
    posts_finding = next((f for f in findings if f.category == "gbp_activity"), None)
    assert posts_finding is not None
    assert posts_finding.status == FindingStatus.NOT_VERIFIED.value
    assert posts_finding.source == "Project Data"


# ============================================================
# 2. NAP & CITATIONS CANONICAL SOURCE TESTS (Tests 7, 8, 9, 10)
# ============================================================

@pytest.mark.asyncio
async def test_nap_uses_bound_gbp_as_canonical(async_db: AsyncSession):
    """Test 7 & 9: When GBP is connected, bound GBP is canonical for NAP and Citation comparison."""
    org = Organization(name="NAP Org", slug="nap-org")
    async_db.add(org)
    await async_db.flush()

    user = User(email="nap@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj = Project(
        name="Precision Dental",
        domain="precisiondental.com",
        organization_id=org.id,
        country="US"
    )
    async_db.add(proj)
    await async_db.flush()

    # Project fallback profile (differing phone to test comparison)
    b_prof = await BusinessProfileService.get_or_create_canonical_profile(proj.id, async_db)
    b_prof.business_name = "Precision Dental Practice"
    b_prof.primary_phone = "+15125559999"
    b_prof.primary_address = "700 Dental Way"
    b_prof.website = "https://precisiondental.com"

    # Exact bound GBP (Canonical Truth)
    gbp = GoogleBusinessProfile(
        project_id=proj.id,
        business_name="Precision Dental Official",
        phone="+15125551111",
        address="700 Dental Way, Suite 100",
        website_url="https://precisiondental.com",
        is_verified=True
    )
    async_db.add(gbp)

    # Citation 1 matching GBP phone
    cit1 = Citation(
        project_id=proj.id,
        source_name="Yelp",
        domain="yelp.com",
        found_name="Precision Dental Official",
        found_phone="+15125551111",
        found_address="700 Dental Way, Suite 100",
        found_website="https://precisiondental.com",
        status="listed"
    )
    # Citation 2 with mismatched phone
    cit2 = Citation(
        project_id=proj.id,
        source_name="YellowPages",
        domain="yellowpages.com",
        found_name="Precision Dental Official",
        found_phone="+15125550000",
        found_address="700 Dental Way, Suite 100",
        found_website="https://precisiondental.com",
        status="listed"
    )
    async_db.add_all([cit1, cit2])
    await async_db.commit()

    nap_res = await NAPComparisonService.compare_project_nap(proj.id, async_db)
    assert nap_res["canonical_source"] == "GOOGLE_BUSINESS_PROFILE"
    assert nap_res["canonical_profile"]["primary_phone"] == "+15125551111"
    assert nap_res["canonical_profile"]["business_name"] == "Precision Dental Official"

    # Yelp citation should match expected GBP phone
    yelp_comp = next((c for c in nap_res["comparisons"] if c["source_name"] == "Yelp"), None)
    assert yelp_comp is not None
    assert yelp_comp["fields"]["phone"]["status"] == "match"
    assert yelp_comp["fields"]["phone"]["expected"] == "+15125551111"

    # YellowPages citation should mismatch expected GBP phone
    yp_comp = next((c for c in nap_res["comparisons"] if c["source_name"] == "YellowPages"), None)
    assert yp_comp is not None
    assert yp_comp["fields"]["phone"]["status"] == "mismatch"


@pytest.mark.asyncio
async def test_nap_fallback_without_gbp(async_db: AsyncSession):
    """Test 8 & 10: When GBP is not connected, NAP comparison uses project profile as canonical truth."""
    org = Organization(name="NAP Fallback Org", slug="nap-fb-org")
    async_db.add(org)
    await async_db.flush()

    user = User(email="nap_fallback@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj = Project(
        name="Apex Plumbing",
        domain="apexplumbing.com",
        organization_id=org.id,
        country="US"
    )
    async_db.add(proj)
    await async_db.flush()

    b_prof = await BusinessProfileService.get_or_create_canonical_profile(proj.id, async_db)
    b_prof.business_name = "Apex Plumbing Services"
    b_prof.primary_phone = "+15125554321"
    b_prof.primary_address = "200 Pipe Rd"
    b_prof.website = "https://apexplumbing.com"
    await async_db.commit()

    nap_res = await NAPComparisonService.compare_project_nap(proj.id, async_db)
    assert nap_res["canonical_source"] == "PROJECT_USER_INPUT"
    assert nap_res["canonical_profile"]["primary_phone"] == "+15125554321"
    assert nap_res["canonical_profile"]["business_name"] == "Apex Plumbing Services"


# ============================================================
# 3. SCHEMA INTELLIGENCE COMPARISON (Tests 11, 12)
# ============================================================

def test_schema_entity_validation_against_gbp():
    """Test 11 & 12: Schema validator compares website JSON-LD against canonical external GBP information."""
    project_context_gbp = {
        "canonical_source": "GOOGLE_BUSINESS_PROFILE",
        "name": "Summit Dental Group",
        "domain": "summitdental.com",
        "phone": "+1 (512) 555-8888",
        "address": "888 Summit Ave, Austin, TX 78701",
        "latitude": 30.2700,
        "longitude": -97.7400,
        "primary_category": "Dentist"
    }

    schema_matching = {
        "@type": "Dentist",
        "raw": {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": "Summit Dental Group",
            "url": "https://summitdental.com",
            "telephone": "+15125558888",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "888 Summit Ave",
                "addressLocality": "Austin",
                "postalCode": "78701",
                "addressCountry": "US"
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": 30.2700,
                "longitude": -97.7400
            }
        }
    }

    val_res = SchemaIntelligenceEngine.validate_entity(schema_matching, project_context=project_context_gbp)
    assert val_res["is_valid"] is True
    assert val_res["nap_match_status"] == "Consistent"
    assert val_res["comparison_details"]["phone"]["status"] == "MATCH"

    schema_mismatch_phone = {
        "@type": "Dentist",
        "raw": {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": "Summit Dental Group",
            "url": "https://summitdental.com",
            "telephone": "+19998887777"
        }
    }
    val_mismatch = SchemaIntelligenceEngine.validate_entity(schema_mismatch_phone, project_context=project_context_gbp)
    assert val_mismatch["nap_match_status"] == "Mismatch"
    assert val_mismatch["comparison_details"]["phone"]["status"] == "MISMATCH"


# ============================================================
# 4. TEMPLATE ENGINE VARIABLE PRIORITY (Tests 13, 14)
# ============================================================

@pytest.mark.asyncio
async def test_template_variable_priority_gbp_over_project(async_db: AsyncSession):
    """Test 13: Template variable resolution prioritizes bound GBP over Location and Project Data."""
    org = Organization(name="Template Org", slug="tpl-org")
    async_db.add(org)
    await async_db.flush()

    user = User(email="template@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj = Project(
        name="Project Name Fallback",
        domain="projectdomain.com",
        organization_id=org.id,
        country="US",
        primary_category="Generic Category"
    )
    async_db.add(proj)
    await async_db.flush()

    loc = Location(
        project_id=proj.id,
        name="Location Name Fallback",
        address="100 Location St",
        city="Location City",
        phone="+1111111111",
        country="US"
    )
    async_db.add(loc)
    await async_db.flush()

    # Exact bound GBP (Priority 1)
    gbp = GoogleBusinessProfile(
        project_id=proj.id,
        business_name="GBP Authoritative Name",
        primary_category="Dentist",
        address="999 Google Blvd",
        city="Austin",
        state="TX",
        postal_code="78701",
        country="US",
        phone="+15125559999",
        website_url="https://gbpdomain.com",
        latitude=30.25,
        longitude=-97.75
    )
    async_db.add(gbp)

    template = Template(
        name="Test Template",
        slug="test-template-priority",
        category="gbp",
        template_type="content_markdown",
        content="Welcome to {{business_name}} located at {{address}}, {{city}}. Call {{phone}} for {{primary_category}} services."
    )
    async_db.add(template)
    await async_db.commit()

    rendered, used_vars, missing_vars = await TemplateEngine.render_template(async_db, template, proj.id)
    assert "GBP Authoritative Name" in rendered
    assert "999 Google Blvd" in rendered
    assert "Austin" in rendered
    assert "+15125559999" in rendered
    assert "Dentist" in rendered
    assert len(missing_vars) == 0


@pytest.mark.asyncio
async def test_template_variable_fallback_without_gbp(async_db: AsyncSession):
    """Test 14: When GBP is disconnected, Template Engine cleanly falls back to Location & Project without fake data."""
    org = Organization(name="Template Fallback Org", slug="tpl-fb-org")
    async_db.add(org)
    await async_db.flush()

    user = User(email="template_fb@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj = Project(
        name="Clean Roofing Pros",
        domain="cleanroofing.com",
        organization_id=org.id,
        country="US",
        primary_category="Roofing contractor"
    )
    async_db.add(proj)
    await async_db.flush()

    loc = Location(
        project_id=proj.id,
        name="Main Office",
        address="456 Shingle Way",
        city="Dallas",
        state="TX",
        postal_code="75001",
        phone="+12145550188",
        country="US"
    )
    async_db.add(loc)

    template = Template(
        name="Test Fallback Template",
        slug="test-fallback-template",
        category="gbp",
        template_type="content_markdown",
        content="Contact {{business_name}} at {{phone}} in {{city}}, {{state}}."
    )
    async_db.add(template)
    await async_db.commit()

    rendered, used_vars, missing_vars = await TemplateEngine.render_template(async_db, template, proj.id)
    assert "Clean Roofing Pros" in rendered
    assert "+12145550188" in rendered
    assert "Dallas" in rendered
    assert "TX" in rendered
    assert len(missing_vars) == 0


# ============================================================
# 5. MULTI-PROJECT ISOLATION (Test 15: GBP A vs. GBP B)
# ============================================================

@pytest.mark.asyncio
async def test_multi_project_gbp_isolation(async_db: AsyncSession):
    """Test 15 & 20: Project A bound to GBP A and Project B bound to GBP B have 100% strict isolation."""
    org = Organization(name="Multi Tenant Org", slug="mt-org")
    async_db.add(org)
    await async_db.flush()

    user = User(email="multitenant@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    proj_a = Project(name="Project A", domain="project-a.com", organization_id=org.id, country="US")
    proj_b = Project(name="Project B", domain="project-b.com", organization_id=org.id, country="US")
    async_db.add_all([proj_a, proj_b])
    await async_db.flush()

    gbp_a = GoogleBusinessProfile(
        project_id=proj_a.id,
        business_name="GBP Location A Only",
        phone="+15125550001",
        address="111 Alpha Street",
        city="Austin",
        is_verified=True
    )
    gbp_b = GoogleBusinessProfile(
        project_id=proj_b.id,
        business_name="GBP Location B Only",
        phone="+15125550002",
        address="222 Beta Avenue",
        city="Seattle",
        is_verified=True
    )
    async_db.add_all([gbp_a, gbp_b])
    await async_db.commit()

    # Verify NAP isolation
    nap_a = await NAPComparisonService.compare_project_nap(proj_a.id, async_db)
    nap_b = await NAPComparisonService.compare_project_nap(proj_b.id, async_db)

    assert nap_a["canonical_profile"]["business_name"] == "GBP Location A Only"
    assert "GBP Location B Only" not in str(nap_a)

    assert nap_b["canonical_profile"]["business_name"] == "GBP Location B Only"
    assert "GBP Location A Only" not in str(nap_b)

    # Verify Audit isolation
    audit_a = await LocalSEOAuditFramework.run_audit(proj_a.id, async_db)
    audit_b = await LocalSEOAuditFramework.run_audit(proj_b.id, async_db)

    findings_a = (await async_db.execute(select(LocalAuditFinding).where(LocalAuditFinding.audit_run_id == audit_a.id))).scalars().all()
    findings_b = (await async_db.execute(select(LocalAuditFinding).where(LocalAuditFinding.audit_run_id == audit_b.id))).scalars().all()

    gbp_finding_a = next(f for f in findings_a if f.category == "google_business_profile")
    gbp_finding_b = next(f for f in findings_b if f.category == "google_business_profile")

    assert "GBP Location A Only" in gbp_finding_a.evidence
    assert "GBP Location B Only" not in str(gbp_finding_a.evidence)

    assert "GBP Location B Only" in gbp_finding_b.evidence
    assert "GBP Location A Only" not in str(gbp_finding_b.evidence)


# ============================================================
# 6. CATEGORY TAXONOMY & SEARCH (Tests 16, 17, 18, 19, 20)
# ============================================================

def test_category_taxonomy_search_and_gcids():
    """Test 16 & 17: CategoryTaxonomy supports typeahead search, stable category_id persistence, and exact matches."""
    dentist_results = CategoryTaxonomy.search("dentist", limit=5)
    assert len(dentist_results) > 0
    top = dentist_results[0]
    assert "dentist" in top["name"].lower()
    assert top["source"] == "LOCALLIFT_TAXONOMY"
    assert top["category_id"] == "dentist"

    # Check lookup by ID
    cat_by_id = CategoryTaxonomy.get_by_id_or_name("dentist")
    assert cat_by_id is not None
    assert cat_by_id["name"] == "Dentist"

    cat_by_plumber = CategoryTaxonomy.get_by_id_or_name("plumber")
    assert cat_by_plumber is not None
    assert cat_by_plumber["name"] == "Plumber"
