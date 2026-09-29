import pytest
import asyncio
import os
import sys
import json
from unittest.mock import AsyncMock, patch

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.database import Base, get_db
import app.models  # noqa: F401
from app.models.user import User, Organization
from app.models.project import Project, Location, Website
from app.models.audit import WebsitePage, SEOAudit
from app.models.gbp import GoogleBusinessProfile
from app.models.local_seo import Citation, Review
from app.services.seo_auditor import SEOAuditor
from app.services.crawler import WebsiteCrawler


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_seo_auditor_schema_distinction_and_completeness():
    """Verify SEOAuditor distinguishes LocalBusiness from non-local schemas, handles @graph, and checks all NAP/geo fields."""
    # 1. Non-local schema only (e.g., WebSite + BreadcrumbList)
    non_local_pages = [
        {
            "url": "https://example-dentist.com",
            "status_code": 200,
            "title": "Best Dentist in Seattle | Example Clinic",
            "h1": "Welcome to Example Clinic - Seattle Dental Care",
            "meta_description": "Premier family dental care in downtown Seattle.",
            "canonical_url": "https://example-dentist.com",
            "is_indexable": True,
            "schema_types": ["WebSite", "BreadcrumbList"],
            "json_ld_schemas": [
                {"@type": "WebSite", "name": "Example Clinic", "url": "https://example-dentist.com"},
                {"@type": "BreadcrumbList", "itemListElement": []}
            ]
        }
    ]
    
    project_context = {
        "name": "Example Clinic",
        "domain": "example-dentist.com",
        "city": "Seattle",
        "phone": "(206) 555-0199",
        "address": "123 Main St, Seattle, WA 98101"
    }
    
    res_non_local = SEOAuditor.audit_pages(non_local_pages, project_context=project_context)
    schema_res = res_non_local["schema"]
    assert schema_res["status"] == "warning"
    assert schema_res["score"] == 30
    assert schema_res["checklist"]["local_business"] is False
    assert any("Found other structured data" in f for f in schema_res["what_we_found"])

    # 2. Rich LocalBusiness Schema in @graph with sub-type Dentist, address, phone, geo, and hours
    rich_local_pages = [
        {
            "url": "https://example-dentist.com",
            "status_code": 200,
            "title": "Best Dentist in Seattle | Example Clinic",
            "h1": "Welcome to Example Clinic - Seattle Dental Care",
            "meta_description": "Premier family dental care in downtown Seattle.",
            "canonical_url": "https://example-dentist.com",
            "is_indexable": True,
            "schema_types": ["Dentist", "WebSite"],
            "json_ld_schemas": [
                {
                    "@context": "https://schema.org",
                    "@graph": [
                        {
                            "@type": "Dentist",
                            "name": "Example Clinic",
                            "telephone": "(206) 555-0199",
                            "url": "https://example-dentist.com",
                            "address": {
                                "@type": "PostalAddress",
                                "streetAddress": "123 Main St",
                                "addressLocality": "Seattle",
                                "addressRegion": "WA",
                                "postalCode": "98101"
                            },
                            "geo": {
                                "@type": "GeoCoordinates",
                                "latitude": 47.6062,
                                "longitude": -122.3321
                            },
                            "openingHoursSpecification": [
                                {
                                    "@type": "OpeningHoursSpecification",
                                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday"],
                                    "opens": "09:00",
                                    "closes": "17:00"
                                }
                            ]
                        },
                        {
                            "@type": "WebSite",
                            "name": "Example Clinic"
                        }
                    ]
                }
            ]
        }
    ]
    
    res_rich = SEOAuditor.audit_pages(rich_local_pages, project_context=project_context)
    schema_rich = res_rich["schema"]
    assert schema_rich["status"] == "pass"
    assert schema_rich["score"] == 100
    assert schema_rich["checklist"]["local_business"] is True
    assert schema_rich["checklist"]["business_name"] is True
    assert schema_rich["checklist"]["address"] is True
    assert schema_rich["checklist"]["phone"] is True
    assert schema_rich["checklist"]["geo"] is True
    assert schema_rich["checklist"]["opening_hours"] is True
    assert "Dentist" in schema_rich["detected_types"]


@pytest.mark.asyncio
async def test_seo_auditor_crawl_and_onpage_evidence():
    """Verify Crawl Health and On-Page signals generate client-friendly evidence and identify affected URLs."""
    pages = [
        {
            "url": "https://example.com/home",
            "status_code": 200,
            "title": "Plumbing Experts in Austin | Apex Plumbing",
            "h1": "Austin's Trusted Emergency Plumbers",
            "meta_description": "24/7 emergency plumbing services in Austin, TX.",
            "canonical_url": "https://example.com/home",
            "is_indexable": True,
            "word_count": 500,
            "phones_found": ["(512) 555-1234"]
        },
        {
            "url": "https://example.com/broken-service",
            "status_code": 404,
            "title": "Not Found",
            "canonical_url": "https://example.com/broken-service",
            "is_indexable": False,
            "word_count": 20
        },
        {
            "url": "https://example.com/canonical-mismatch",
            "status_code": 200,
            "title": "Drain Cleaning",
            "h1": "Drain Cleaning Services",
            "canonical_url": "https://example.com/other-canonical",
            "is_indexable": True,
            "word_count": 400
        }
    ]
    
    project_context = {
        "name": "Apex Plumbing",
        "domain": "example.com",
        "city": "Austin",
        "phone": "(512) 555-1234",
        "address": "456 Congress Ave, Austin, TX"
    }
    
    audit_res = SEOAuditor.audit_pages(pages, project_context=project_context)
    
    # 1. Crawl Health Checks
    crawl_res = audit_res["crawl"]
    assert crawl_res["pages_checked"] == 3
    assert crawl_res["status"] in ("warning", "error")
    assert crawl_res["score"] < 100
    assert len(crawl_res["affected_pages"]) >= 2
    assert any(ap["url"] == "https://example.com/broken-service" for ap in crawl_res["affected_pages"])
    assert any(ap["url"] == "https://example.com/canonical-mismatch" for ap in crawl_res["affected_pages"])
    assert any("HTTP 404" in ap.get("issue", "") for ap in crawl_res["affected_pages"])
    
    # 2. Local On-Page Checks
    onpage_res = audit_res["local_on_page"]
    assert onpage_res["score"] > 0
    assert any("Business name" in f for f in onpage_res["what_we_found"])
    assert any("Austin" in f or "City" in f or "Location" in f for f in onpage_res["what_we_found"])


@pytest.mark.asyncio
async def test_seo_auditor_gbp_citations_reviews_states():
    """Verify GBP match vs disconnected, citations not verified, and review fallback states."""
    pages = [
        {
            "url": "https://testroofing.com",
            "status_code": 200,
            "title": "Test Roofing Melbourne",
            "canonical_url": "https://testroofing.com",
            "is_indexable": True
        }
    ]
    project_context = {
        "name": "Test Roofing Pty Ltd",
        "domain": "testroofing.com",
        "city": "Melbourne",
        "phone": "+61 3 9000 0000",
        "address": "100 Collins St, Melbourne VIC 3000"
    }
    
    # State A: GBP Disconnected, Citations None, Reviews None
    res_disconnected = SEOAuditor.audit_pages(
        pages,
        project_context=project_context,
        gbp_context=None,
        citation_context=None,
        review_context=None
    )
    assert res_disconnected["gbp_match"]["status"] == "not_connected"
    assert res_disconnected["gbp_match"]["score"] is None
    assert res_disconnected["citations"]["status"] == "not_verified"
    assert res_disconnected["citations"]["score"] is None
    assert res_disconnected["reviews"]["status"] == "no_data"
    assert res_disconnected["reviews"]["score"] is None

    # State B: GBP Connected with perfect match
    gbp_context_perfect = {
        "connected": True,
        "business_name": "Test Roofing Pty Ltd",
        "phone": "+61 3 9000 0000",
        "address": "100 Collins St, Melbourne VIC 3000",
        "website_url": "https://testroofing.com"
    }
    res_matched = SEOAuditor.audit_pages(
        pages,
        project_context=project_context,
        gbp_context=gbp_context_perfect,
        citation_context=[{"source_name": "YellowPages", "status": "active", "nap_status": "aligned"}],
        review_context={"total_reviews": 45, "average_rating": 5.0, "unanswered_count": 0}
    )
    assert res_matched["gbp_match"]["status"] == "matched"
    assert res_matched["gbp_match"]["score"] == 100
    assert res_matched["gbp_match"]["fields"]["business_name"]["match"] is True
    assert res_matched["gbp_match"]["fields"]["phone"]["match"] is True
    assert res_matched["citations"]["status"] == "pass"
    assert res_matched["citations"]["score"] == 100
    assert res_matched["reviews"]["status"] == "pass"
    assert res_matched["reviews"]["score"] == 100


@pytest.mark.asyncio
async def test_seo_auditor_scoring_methodology_no_developer_formulas():
    """Verify that scoring methodology is client-friendly and does not leak backend formula syntax."""
    methodology = SEOAuditor.get_scoring_methodology()
    assert "crawl_health" in methodology
    assert "schema_structured_data" in methodology
    
    for pillar_key, m in methodology.items():
        assert "name" in m
        assert "weight" in m
        assert "description" in m
        assert "formula" not in m  # No developer formulas exposed
        assert "deductions" not in m


@pytest.mark.asyncio
async def test_project_isolation_in_database(async_db: AsyncSession):
    """Verify Project A audit and crawled pages are strictly isolated from Project B."""
    org = Organization(name="Test Isolation Org", slug="isolation-org")
    async_db.add(org)
    await async_db.flush()

    user = User(email="iso@test.com", hashed_password="pw")
    async_db.add(user)
    await async_db.flush()

    # Project A
    proj_a = Project(name="Project A Alpha", domain="alpha.com", organization_id=org.id)
    async_db.add(proj_a)
    await async_db.flush()

    web_a = Website(project_id=proj_a.id, url="https://alpha.com")
    async_db.add(web_a)
    await async_db.flush()

    page_a = WebsitePage(website_id=web_a.id, url="https://alpha.com", status_code=200, title="Alpha Page")
    async_db.add(page_a)

    # Project B
    proj_b = Project(name="Project B Beta", domain="beta.com", organization_id=org.id)
    async_db.add(proj_b)
    await async_db.flush()

    web_b = Website(project_id=proj_b.id, url="https://beta.com")
    async_db.add(web_b)
    await async_db.flush()

    page_b = WebsitePage(website_id=web_b.id, url="https://beta.com", status_code=404, title="Beta Not Found")
    async_db.add(page_b)
    await async_db.commit()

    # Query Project A pages
    pages_a_res = await async_db.execute(select(WebsitePage).where(WebsitePage.website_id == web_a.id))
    pages_a = pages_a_res.scalars().all()
    assert len(pages_a) == 1
    assert pages_a[0].url == "https://alpha.com"
    assert pages_a[0].status_code == 200

    # Query Project B pages
    pages_b_res = await async_db.execute(select(WebsitePage).where(WebsitePage.website_id == web_b.id))
    pages_b = pages_b_res.scalars().all()
    assert len(pages_b) == 1
    assert pages_b[0].url == "https://beta.com"
    assert pages_b[0].status_code == 404
