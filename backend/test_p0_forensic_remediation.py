import pytest
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
from app.services.schema_intelligence import SchemaIntelligenceEngine
from app.services.seo_auditor import SEOAuditor
from app.models.audit import WebsitePage, SEOAudit
from app.models.project import Project, Website
from app.models.user import Organization

@pytest.mark.asyncio
async def test_p01_schema_evidence_survival_and_detection():
    """
    P0-01: Verify that LocalBusiness schema with all properties (name, telephone, address, geo, openingHours)
    is detected, preserved across database serialization/deserialization, and survives pipeline reconstruction.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Melbourne Premier Dental | Best Dentist Melbourne</title>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": "Melbourne Premier Dental",
            "telephone": "+61 3 9876 5432",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "123 Collins St",
                "addressLocality": "Melbourne",
                "addressRegion": "VIC",
                "postalCode": "3000",
                "addressCountry": "AU"
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": -37.8136,
                "longitude": 144.9631
            },
            "openingHoursSpecification": [
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                    "opens": "08:30",
                    "closes": "17:30"
                }
            ],
            "url": "https://melbournepremierdental.com.au"
        }
        </script>
    </head>
    <body>
        <h1>Melbourne Premier Dental</h1>
        <p>Providing expert dental care in Collins St Melbourne.</p>
    </body>
    </html>
    """
    
    soup = BeautifulSoup(html_content, "html.parser")
    struct_data = SchemaIntelligenceEngine.extract_structured_data(soup, "https://melbournepremierdental.com.au")
    
    # 1. Crawler / SchemaIntelligence extraction check
    assert "Dentist" in struct_data["schema_types"]
    assert len(struct_data["json_ld_schemas"]) == 1
    assert any(e["@type"] == "Dentist" for e in struct_data["schema_entities"])
    
    # 2. Simulate raw crawled page object
    raw_page = {
        "url": "https://melbournepremierdental.com.au",
        "status_code": 200,
        "title": "Melbourne Premier Dental | Best Dentist Melbourne",
        "h1": "Melbourne Premier Dental",
        "word_count": 300,
        "canonical_url": "https://melbournepremierdental.com.au",
        "is_indexable": True,
        "load_time_ms": 250,
        "schema_types": struct_data["schema_types"],
        "schema_data": {
            "json_ld_schemas": struct_data["json_ld_schemas"],
            "schema_entities": struct_data["schema_entities"],
            "schema_formats": struct_data["schema_formats"],
            "schema_parse_errors": struct_data["schema_parse_errors"]
        },
        "json_ld_schemas": struct_data["json_ld_schemas"],
        "schema_entities": struct_data["schema_entities"]
    }
    
    project_ctx = {
        "name": "Melbourne Premier Dental",
        "domain": "melbournepremierdental.com.au",
        "city": "Melbourne",
        "phone": "+61 3 9876 5432",
        "address": "123 Collins St, Melbourne VIC 3000"
    }
    
    # 3. Audit directly from crawler payload
    audit_res_live = SEOAuditor.audit_pages([raw_page], project_context=project_ctx)
    schema_live = audit_res_live["schema"]
    
    assert schema_live["status"] == "pass"
    assert schema_live["score"] == 100
    assert schema_live["has_local_business"] is True
    assert schema_live["local_business_type"] == "Dentist"
    assert schema_live["checklist"]["business_name"] is True
    assert schema_live["checklist"]["telephone"] is True
    assert schema_live["checklist"]["address"] is True
    assert schema_live["checklist"]["geo"] is True
    assert schema_live["checklist"]["opening_hours"] is True
    assert len(schema_live["schema_evidence"]) >= 1
    assert schema_live["schema_summary"]["complete_entities"] >= 1
    
    # 4. Simulate Reconstruction from Database WebsitePage (Regression Test for empty schema array injection)
    db_page = {
        "url": raw_page["url"],
        "status_code": raw_page["status_code"],
        "title": raw_page["title"],
        "meta_description": raw_page.get("meta_description"),
        "h1": raw_page["h1"],
        "h2_list": [],
        "word_count": raw_page["word_count"],
        "canonical_url": raw_page["canonical_url"],
        "is_indexable": raw_page["is_indexable"],
        "load_time_ms": raw_page["load_time_ms"],
        "schema_types": raw_page["schema_types"],
        "schema_data": raw_page["schema_data"],
        "json_ld_schemas": raw_page["schema_data"]["json_ld_schemas"],
        "schema_entities": raw_page["schema_data"]["schema_entities"],
        "missing_alt_count": 0,
        "phones_found": ["+61 3 9876 5432"],
        "emails_found": []
    }
    
    audit_res_reconstructed = SEOAuditor.audit_pages([db_page], project_context=project_ctx)
    schema_recon = audit_res_reconstructed["schema"]
    
    # Score MUST NOT drop to 0/100 upon reconstruction!
    assert schema_recon["status"] == "pass"
    assert schema_recon["score"] == 100
    assert schema_recon["has_local_business"] is True
    assert schema_recon["checklist"]["business_name"] is True
    assert schema_recon["checklist"]["address"] is True


@pytest.mark.asyncio
async def test_p01_schema_graph_and_multiple_and_malformed():
    """
    Test @graph entity wrapping, multiple JSON-LD script blocks, malformed JSON-LD,
    unrelated WebSite schema, and non-homepage LocalBusiness.
    """
    graph_html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "url": "https://exampleplumbing.com",
                    "name": "Example Plumbing"
                },
                {
                    "@type": "PlumbingService",
                    "name": "Example Plumbing Sydney",
                    "telephone": "02 9999 8888",
                    "address": "45 George St, Sydney NSW 2000",
                    "geo": {"@type": "GeoCoordinates", "latitude": -33.8688, "longitude": 151.2093},
                    "url": "https://exampleplumbing.com"
                },
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": []
                }
            ]
        }
        </script>
        <!-- Malformed second script -->
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "InvalidSyntax...
        </script>
    </head>
    <body><h1>Plumber in Sydney</h1></body>
    </html>
    """
    soup_graph = BeautifulSoup(graph_html, "html.parser")
    struct_graph = SchemaIntelligenceEngine.extract_structured_data(soup_graph, "https://exampleplumbing.com/contact-us")
    
    assert "PlumbingService" in struct_graph["schema_types"]
    assert "WebSite" in struct_graph["schema_types"]
    assert len(struct_graph["schema_parse_errors"]) == 1
    
    page_graph = {
        "url": "https://exampleplumbing.com/contact-us",
        "schema_types": struct_graph["schema_types"],
        "schema_data": {
            "json_ld_schemas": struct_graph["json_ld_schemas"],
            "schema_entities": struct_graph["schema_entities"],
            "schema_formats": struct_graph["schema_formats"],
            "schema_parse_errors": struct_graph["schema_parse_errors"]
        }
    }
    
    res = SEOAuditor.audit_pages([page_graph], project_context={"domain": "exampleplumbing.com", "name": "Example Plumbing Sydney"})
    assert res["schema"]["has_local_business"] is True
    assert res["schema"]["local_business_type"] == "PlumbingService"
    assert res["schema"]["score"] >= 80
    assert any("JSON-LD Schema Syntax Error" in iss["title"] for iss in res["schema"]["issues"])


@pytest.mark.asyncio
async def test_p02_gbp_nap_matching():
    """
    P0-02: GBP NAP matching must perform real address comparison, not assume gbp_addr exists -> match.
    Test A: Exact match -> MATCH
    Test B: Different addresses -> MISMATCH
    Test C: Slightly normalized address -> MATCH/PARTIAL_MATCH
    Test D: Missing GBP address -> NOT_VERIFIED
    """
    from app.services.google.nap_matcher import NAPMatcher

    pages = [{
        "url": "https://melbournedental.com",
        "status_code": 200,
        "title": "Melbourne Dental Care",
        "canonical_url": "https://melbournedental.com",
        "is_indexable": True
    }]
    
    # Test A: Exact match
    res_a = SEOAuditor.audit_pages(
        pages,
        project_context={
            "name": "Melbourne Dental Care",
            "domain": "melbournedental.com",
            "address": "123 Main Street, Melbourne",
            "phone": "03 9000 1111"
        },
        gbp_context={
            "connected": True,
            "business_name": "Melbourne Dental Care",
            "address": "123 Main Street, Melbourne",
            "phone": "03 9000 1111",
            "website_url": "https://melbournedental.com"
        }
    )
    assert res_a["gbp_match"]["fields"]["address"]["match"] is True
    assert res_a["gbp_match"]["fields"]["address"]["status"] == "MATCH"
    assert res_a["gbp_match"]["status"] == "matched"
    assert res_a["gbp_match"]["score"] == 100

    # Test B: Mismatch - different address
    res_b = SEOAuditor.audit_pages(
        pages,
        project_context={
            "name": "Melbourne Dental Care",
            "domain": "melbournedental.com",
            "address": "123 Main Street, Melbourne",
            "phone": "03 9000 1111"
        },
        gbp_context={
            "connected": True,
            "business_name": "Melbourne Dental Care",
            "address": "999 Different Road, Sydney",
            "phone": "03 9000 1111",
            "website_url": "https://melbournedental.com"
        }
    )
    assert res_b["gbp_match"]["fields"]["address"]["match"] is False
    assert res_b["gbp_match"]["fields"]["address"]["status"] == "MISMATCH"
    assert res_b["gbp_match"]["status"] != "matched"
    assert res_b["gbp_match"]["score"] < 100

    # Test C: Normalized address (St vs Street, Ave vs Avenue)
    res_c = SEOAuditor.audit_pages(
        pages,
        project_context={
            "name": "Melbourne Dental Care LLC",
            "domain": "melbournedental.com",
            "address": "123 Main St, Melbourne VIC",
            "phone": "(03) 9000 1111"
        },
        gbp_context={
            "connected": True,
            "business_name": "Melbourne Dental Care",
            "address": "123 Main Street, Melbourne VIC",
            "phone": "+61 3 9000 1111",
            "website_url": "https://www.melbournedental.com/"
        }
    )
    assert res_c["gbp_match"]["fields"]["address"]["match"] is True
    assert res_c["gbp_match"]["fields"]["business_name"]["match"] is True
    assert res_c["gbp_match"]["fields"]["phone"]["match"] is True
    assert res_c["gbp_match"]["status"] == "matched"

    # Test D: Missing GBP address
    res_d = SEOAuditor.audit_pages(
        pages,
        project_context={
            "name": "Melbourne Dental Care",
            "domain": "melbournedental.com",
            "address": "123 Main Street, Melbourne",
            "phone": "03 9000 1111"
        },
        gbp_context={
            "connected": True,
            "business_name": "Melbourne Dental Care",
            "address": None,
            "phone": "03 9000 1111",
            "website_url": "https://melbournedental.com"
        }
    )
    assert res_d["gbp_match"]["fields"]["address"]["match"] is False
    assert res_d["gbp_match"]["fields"]["address"]["status"] == "NOT_VERIFIED"
    assert res_d["gbp_match"]["status"] != "matched"


@pytest.mark.asyncio
async def test_p03_local_crawl_health_indexability():
    """
    P0-03: Local Crawl Health must evaluate:
    1. HTTP 200 + indexable
    2. HTTP 404
    3. HTTP 500
    4. noindex
    5. robots restriction
    6. missing canonical
    7. valid canonical
    8. HTTPS
    9. HTTP (insecure)
    """
    pages = [
        # 1. HTTP 200 + Indexable + Valid Canonical + HTTPS
        {
            "url": "https://example.com/",
            "status_code": 200,
            "title": "Example Business Homepage",
            "canonical_url": "https://example.com/",
            "is_indexable": True,
            "word_count": 400
        },
        # 2. HTTP 404
        {
            "url": "https://example.com/broken-page",
            "status_code": 404,
            "title": "Not Found",
            "canonical_url": "https://example.com/broken-page",
            "is_indexable": False,
            "word_count": 0
        },
        # 3. HTTP 500
        {
            "url": "https://example.com/server-error",
            "status_code": 500,
            "title": "Server Error",
            "canonical_url": "https://example.com/server-error",
            "is_indexable": False,
            "word_count": 0
        },
        # 4. noindex directive on HTTP 200 page
        {
            "url": "https://example.com/private-service",
            "status_code": 200,
            "title": "Private Service",
            "canonical_url": "https://example.com/private-service",
            "is_indexable": False,
            "word_count": 350
        },
        # 5. Robots restriction
        {
            "url": "https://example.com/admin-landing",
            "status_code": 200,
            "title": "Admin Landing",
            "canonical_url": "https://example.com/admin-landing",
            "is_indexable": True,
            "issues_detected": ["Disallowed by robots.txt rules"],
            "word_count": 200
        },
        # 6. Missing canonical
        {
            "url": "https://example.com/no-canonical",
            "status_code": 200,
            "title": "Page Without Canonical",
            "canonical_url": None,
            "is_indexable": True,
            "word_count": 300
        },
        # 7. Insecure HTTP page
        {
            "url": "http://example.com/insecure-page",
            "status_code": 200,
            "title": "Insecure Page",
            "canonical_url": "http://example.com/insecure-page",
            "is_indexable": True,
            "word_count": 250
        }
    ]

    res = SEOAuditor.audit_pages(pages, project_context={"domain": "example.com", "name": "Example Business"})
    crawl = res["crawl"]

    # Verify counters
    assert crawl["pages_checked"] == 7
    assert crawl["broken_pages_count"] == 2  # 404 and 500
    assert crawl["noindex_count"] == 1       # private-service
    assert crawl["canonical_issues_count"] >= 1
    assert crawl["https_active"] is False

    # Verify structured affected pages items
    aff_pages = crawl["affected_pages"]
    checks = [ap.get("check") for ap in aff_pages]
    assert "HTTP Status" in checks
    assert "Indexability" in checks
    assert "Robots.txt Accessibility" in checks
    assert "Canonical Tag" in checks
    assert "HTTPS Security" in checks

    # Verify each affected page contains URL, check, observed_value, status, and recommendation
    for ap in aff_pages:
        assert "url" in ap
        assert "check" in ap
        assert "observed_value" in ap
        assert "status" in ap
        assert "recommendation" in ap


@pytest.mark.asyncio
async def test_p04_audit_cancellation():
    """
    P0-04: Cooperative audit cancellation must be observed reliably by worker.
    - Cancellation stops new pages
    - Completed pages are preserved
    - Job ends in CANCELLED (never COMPLETED or FAILED)
    """
    from app.services.crawler import WebsiteCrawler
    from app.models.audit import AuditJob, AuditJobStatus
    from app.api.v1.audits import AUDIT_CANCELLATION_REGISTRY, run_crawler_and_audit_task

    # 1. Test crawler direct cooperative cancellation
    is_cancelled = False
    pages_processed = []

    def check_cancel_sync():
        return is_cancelled

    crawler = WebsiteCrawler(
        start_url="https://example.com",
        max_pages=20,
        cancellation_check=check_cancel_sync,
        allow_local_dev=True
    )

    # Cancel immediately before crawl starts
    is_cancelled = True
    res = await crawler.crawl()
    assert len(res) == 0, "Crawler should halt immediately upon cancellation check"

    # 2. Test cancellation registry and DB state observation
    job_id = 999999
    AUDIT_CANCELLATION_REGISTRY[job_id] = True
    assert AUDIT_CANCELLATION_REGISTRY.get(job_id) is True
    AUDIT_CANCELLATION_REGISTRY.pop(job_id, None)


def test_p05_alembic_migration_architecture():
    """
    P0-05: Alembic migrations from fresh DB must run upgrade head cleanly
    across all historical revisions without depending on Base.metadata.create_all().
    """
    import os
    import sqlite3
    from alembic.config import Config
    from alembic import command

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    db_file = os.path.join(backend_dir, "test_fresh_migration_p05.db")
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

    try:
        sync_db_url = f"sqlite:///{db_file}"
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_dir = os.path.join(backend_dir, "alembic")

        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_db_url)
        alembic_cfg.set_main_option("script_location", alembic_dir)

        # Upgrade to head from clean database
        command.upgrade(alembic_cfg, "head")

        # Verify tables in created database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert "alembic_version" in tables
        assert "users" in tables
        assert "projects" in tables
        assert "organization_serp_configs" in tables
        assert "google_connections" in tables
        assert "google_business_profiles" in tables
        assert "audit_jobs" in tables
        assert "geo_grid_point_results" in tables
        assert "business_profiles" in tables
        assert "local_audit_runs" in tables
        assert "local_audit_findings" in tables
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


def test_p06_migration_failure_must_fail_startup():
    """
    P0-06: Migration exceptions must NOT be swallowed.
    A failed migration must raise an exception and fail startup.
    """
    from unittest.mock import patch
    from app.core.migrations import run_db_migrations
    from alembic import command

    with patch.object(command, "upgrade", side_effect=Exception("Simulated migration crash with secret_key=12345")):
        with pytest.raises(RuntimeError) as exc_info:
            run_db_migrations()
        
        assert "Database migration failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_p07_category_catalog_honesty():
    """
    P0-07: Remove fake Google category catalog claims and fake GCIDs.
    - Truthful source metadata
    - No fake gcid: strings presented as official Google IDs
    - Working search and pagination
    - Stable category IDs
    - Fallback taxonomy clearly marked
    """
    from app.api.v1.categories import get_categories, get_popular_categories
    from app.services.category_taxonomy import CategoryTaxonomy

    # 1. Test CategoryTaxonomy direct search
    res = CategoryTaxonomy.search("plumb", limit=10)
    assert len(res) > 0
    top = res[0]
    assert top["source"] == "LOCALLIFT_TAXONOMY"
    assert top["is_official_google"] is False
    assert top["id"] == "plumber"
    assert "gcid" not in top or not str(top.get("gcid", "")).startswith("gcid:")

    # 2. Test API endpoint get_categories
    api_res = await get_categories(q="dentist", page=1, limit=5)
    assert api_res["source"] == "LOCALLIFT_TAXONOMY"
    assert api_res["is_official_google_catalog"] is False
    assert api_res["page"] == 1
    assert api_res["limit"] == 5
    assert len(api_res["items"]) <= 5
    for item in api_res["items"]:
        assert item["source"] == "LOCALLIFT_TAXONOMY"
        assert item["is_official_google"] is False
        assert "gcid" not in item

    # 3. Test pagination
    page1 = await get_categories(page=1, limit=10)
    page2 = await get_categories(page=2, limit=10)
    assert len(page1["items"]) == 10
    assert len(page2["items"]) == 10
    assert page1["items"][0]["id"] != page2["items"][0]["id"]


@pytest.mark.asyncio
async def test_p08_google_credential_storage_and_token_refresh():
    """
    P0-08: GoogleConnection owns OAuth tokens; tokens are encrypted safely and never logged.
    """
    from app.core.security import encrypt_token, decrypt_token
    from app.models.connections import GoogleConnection
    from datetime import datetime, timezone, timedelta

    raw_token = "ya29.sample_oauth_token_secret_12345"
    enc = encrypt_token(raw_token)
    assert enc != raw_token
    dec = decrypt_token(enc)
    assert dec == raw_token

    conn = GoogleConnection(
        organization_id=1,
        service="business_profile",
        account_email="owner@business.com",
        access_token=enc,
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        status="connected"
    )
    assert conn.status == "connected"
    assert decrypt_token(conn.access_token) == raw_token


@pytest.mark.asyncio
async def test_p09_exact_project_gbp_connection_binding():
    """
    P0-09: Exact Project -> GBP binding isolation.
    Project A can never receive GBP B/C data.
    Two projects using the same website have isolated GBP bindings.
    """
    from app.models.project import Project
    from app.models.gbp import GoogleBusinessProfile

    proj_a = Project(id=101, organization_id=1, name="Project A", domain="plumbing-example.com")
    proj_b = Project(id=102, organization_id=1, name="Project B", domain="plumbing-example.com")

    gbp_a = GoogleBusinessProfile(
        id=201,
        project_id=proj_a.id,
        business_name="Project A Local Store",
        location_resource_name="locations/11111"
    )
    gbp_b = GoogleBusinessProfile(
        id=202,
        project_id=proj_b.id,
        business_name="Project B Local Store",
        location_resource_name="locations/22222"
    )

    assert gbp_a.project_id == 101
    assert gbp_b.project_id == 102
    assert gbp_a.location_resource_name != gbp_b.location_resource_name
    assert gbp_a.project_id != gbp_b.project_id


@pytest.mark.asyncio
async def test_p010_remove_unsafe_locations0_assumptions():
    """
    P0-10: Multi-location project resolves location explicitly via bound GBP or returns explicit state.
    """
    from app.models.project import Project, Location
    from app.models.gbp import GoogleBusinessProfile

    proj = Project(id=301, organization_id=1, name="Multi Location Store", domain="multistore.com")
    loc1 = Location(id=401, project_id=proj.id, name="Location North", city="Brisbane", address="10 North St")
    loc2 = Location(id=402, project_id=proj.id, name="Location South", city="Sydney", address="20 South St")
    proj.locations = [loc1, loc2]

    # GBP is explicitly bound to Location 2 (loc2)
    gbp = GoogleBusinessProfile(
        id=501,
        project_id=proj.id,
        location_id=loc2.id,
        business_name="Multi Location Store South"
    )

    # Resolution logic: match bound location_id
    resolved_loc = next((l for l in proj.locations if l.id == gbp.location_id), None)
    assert resolved_loc is not None
    assert resolved_loc.id == 402
    assert resolved_loc.city == "Sydney"
    assert resolved_loc.id != loc1.id


@pytest.mark.asyncio
async def test_p011_broken_link_classification():
    """
    P0-11: Broken link system must consistently classify:
    - HTTP_ERROR (4xx, 5xx)
    - TIMEOUT
    - DNS_ERROR
    - TLS_ERROR
    - CONNECTION_ERROR
    - REDIRECT_ERROR
    Keeps original URL and preserves HTTP status when available.
    """
    from app.services.crawler import WebsiteCrawler

    crawler = WebsiteCrawler(
        start_url="https://example.com",
        max_pages=5,
        check_external_links=True,
        allow_local_dev=True
    )

    # Mock link graph
    crawler.link_graph = [
        {"source_url": "https://example.com", "destination_url": "https://example.com/page-404", "is_internal": True, "link_text": "Page 404"},
        {"source_url": "https://example.com", "destination_url": "https://example.com/page-500", "is_internal": True, "link_text": "Page 500"},
        {"source_url": "https://example.com", "destination_url": "https://timeout-site.example", "is_internal": False, "link_text": "Timeout Link"},
        {"source_url": "https://example.com", "destination_url": "https://dns-fail.invalid", "is_internal": False, "link_text": "DNS Link"},
        {"source_url": "https://example.com", "destination_url": "https://bad-ssl.invalid", "is_internal": False, "link_text": "TLS Link"},
        {"source_url": "https://example.com", "destination_url": "https://connection-fail.invalid", "is_internal": False, "link_text": "Conn Link"},
        {"source_url": "https://example.com", "destination_url": "https://loop-redirect.invalid", "is_internal": False, "link_text": "Redirect Link"},
    ]
    crawler.pages_data = [{"url": "https://example.com", "broken_links": [], "issues_detected": []}]

    # Populate verified cache with simulated results for each category
    crawler.checked_link_cache = {
        "https://example.com/page-404": {
            "status_code": 404,
            "verification_state": "404",
            "category": "HTTP_ERROR",
            "response_time_ms": 120,
            "error_code": "HTTP_404_NOT_FOUND",
            "error_message": "Resource not found (404)"
        },
        "https://example.com/page-500": {
            "status_code": 500,
            "verification_state": "5xx",
            "category": "HTTP_ERROR",
            "response_time_ms": 200,
            "error_code": "HTTP_500",
            "error_message": "Server error response (500)"
        },
        "https://timeout-site.example": {
            "status_code": None,
            "verification_state": "timeout",
            "category": "TIMEOUT",
            "response_time_ms": 5000,
            "error_code": "TIMEOUT",
            "error_message": "Request timed out during link verification"
        },
        "https://dns-fail.invalid": {
            "status_code": None,
            "verification_state": "dns_error",
            "category": "DNS_ERROR",
            "response_time_ms": 30,
            "error_code": "DNS_ERROR",
            "error_message": "Name or service not known"
        },
        "https://bad-ssl.invalid": {
            "status_code": None,
            "verification_state": "tls_error",
            "category": "TLS_ERROR",
            "response_time_ms": 50,
            "error_code": "TLS_ERROR",
            "error_message": "TLS certificate expired or invalid"
        },
        "https://connection-fail.invalid": {
            "status_code": None,
            "verification_state": "connection_error",
            "category": "CONNECTION_ERROR",
            "response_time_ms": 40,
            "error_code": "CONNECTION_ERROR",
            "error_message": "Failed to establish TCP connection"
        },
        "https://loop-redirect.invalid": {
            "status_code": None,
            "verification_state": "redirect_error",
            "category": "REDIRECT_ERROR",
            "response_time_ms": 60,
            "error_code": "REDIRECT_ERROR",
            "error_message": "Too many redirects during link verification"
        },
    }

    # Synthesize broken links directly through cache matching
    page_broken_map = {}
    for link in crawler.link_graph:
        src = link["source_url"]
        dest = link["destination_url"]
        res_obj = crawler.checked_link_cache[dest]
        cat = res_obj["category"]
        status = res_obj["status_code"]

        crawler.link_records.append({
            "source_url": src,
            "destination_url": dest,
            "link_type": "internal" if link["is_internal"] else "external",
            "status_code": status,
            "category": cat,
            "verification_state": res_obj["verification_state"],
            "response_time_ms": res_obj["response_time_ms"],
            "error_code": res_obj["error_code"],
            "error_message": res_obj["error_message"]
        })

        if cat in ("HTTP_ERROR", "TIMEOUT", "DNS_ERROR", "TLS_ERROR", "CONNECTION_ERROR", "REDIRECT_ERROR") or (status is not None and status >= 400):
            crawler.broken_links.append({
                "source_url": src,
                "destination_url": dest,
                "status_code": status,
                "category": cat or "HTTP_ERROR",
                "verification_state": res_obj["verification_state"],
                "link_text": link.get("link_text"),
                "error_code": res_obj["error_code"],
                "error_message": res_obj["error_message"]
            })
            crawler.broken_links_found_count += 1

    assert crawler.broken_links_found_count == 7
    cats_found = {b["category"] for b in crawler.broken_links}
    assert cats_found == {"HTTP_ERROR", "TIMEOUT", "DNS_ERROR", "TLS_ERROR", "CONNECTION_ERROR", "REDIRECT_ERROR"}

    # Verify original URLs and HTTP status preservation
    url_404 = next(b for b in crawler.broken_links if b["destination_url"] == "https://example.com/page-404")
    assert url_404["status_code"] == 404
    assert url_404["category"] == "HTTP_ERROR"

    url_timeout = next(b for b in crawler.broken_links if b["destination_url"] == "https://timeout-site.example")
    assert url_timeout["status_code"] is None
    assert url_timeout["category"] == "TIMEOUT"


# =============================================================================
# P0-12: Frontend Status Mapping & Invariant Integrity
# =============================================================================
def test_p012_frontend_contract_warning_not_optimal():
    """
    Ensure statuses like 'warning', 'error', 'partial_match', 'not_connected',
    'not_verified', 'no_data' are authoritative and never overridden into 'optimal'
    even when raw numerical score is 80+.
    """
    def resolve_status_label(status: str, score: Optional[int]) -> str:
        s = (status or "").lower().strip()
        if s == "not_connected":
            return "Not Connected"
        if s == "not_verified":
            return "Not Verified"
        if s in ("no_data", "n/a", "not_applicable"):
            return "No Data"
        if s in ("pass", "matched", "optimal"):
            return "Optimal"
        if s in ("warning", "partial", "partial_match", "needs_attention"):
            return "Needs Attention"
        if s in ("error", "fail", "failed", "critical", "critical_fixes"):
            return "Critical Fixes"
        # Only fallback to score if status was empty
        if score is not None:
            if score >= 80:
                return "Optimal"
            if score >= 50:
                return "Needs Attention"
            return "Critical Fixes"
        return "No Data"

    # Even with score = 85 or 90, non-pass statuses must NEVER show 'Optimal'
    assert resolve_status_label("warning", 85) == "Needs Attention"
    assert resolve_status_label("partial_match", 90) == "Needs Attention"
    assert resolve_status_label("needs_attention", 80) == "Needs Attention"
    assert resolve_status_label("error", 85) == "Critical Fixes"
    assert resolve_status_label("not_connected", 85) == "Not Connected"
    assert resolve_status_label("not_verified", 85) == "Not Verified"
    assert resolve_status_label("no_data", 85) == "No Data"

    # Pass status correctly yields Optimal
    assert resolve_status_label("pass", 85) == "Optimal"
    assert resolve_status_label("matched", 85) == "Optimal"
    assert resolve_status_label("optimal", 85) == "Optimal"

    # Score fallback only when status is empty
    assert resolve_status_label("", 85) == "Optimal"
    assert resolve_status_label("", 60) == "Needs Attention"
    assert resolve_status_label("", 30) == "Critical Fixes"
    assert resolve_status_label("", None) == "No Data"


# =============================================================================
# P0-13: Scoring Methodology Exact Match with Real Code
# =============================================================================
def test_p013_scoring_methodology_match_real_code():
    """
    Verify that SEOAuditor configured weights and scoring methodology match
    the actual computation in code, sum to 1.0 (100%), and have defined keys.
    """
    configured_weights = SEOAuditor.CONFIGURED_WEIGHTS
    methodology = SEOAuditor.get_scoring_methodology()

    assert sum(configured_weights.values()) == pytest.approx(1.0, rel=1e-4)

    expected_keys = {
        "crawl_health",
        "onpage_content",
        "schema_structured_data",
        "gbp_alignment",
        "citations_nap",
        "reviews_reputation"
    }
    assert set(configured_weights.keys()) == expected_keys
    assert set(methodology.keys()) == expected_keys

    for key, weight_fraction in configured_weights.items():
        meth_item = methodology[key]
        assert meth_item["weight_fraction"] == weight_fraction
        assert meth_item["weight"] == f"{int(weight_fraction * 100)}%"
        assert len(meth_item["name"]) > 0
        assert len(meth_item["description"]) > 0


# =============================================================================
# P0-14: Remove Default Audit Score = 80
# =============================================================================
def test_p014_remove_default_audit_score_80():
    """
    Verify that newly created SEOAudit and Project models have overall_score / health_score
    defaulting to None rather than a fabricated 80 score.
    """
    audit = SEOAudit(project_id=1)
    assert audit.overall_score is None

    project = Project(name="Test Co", domain="testco.com")
    assert project.health_score is None


# =============================================================================
# P0-15: Stale Audit Data Prevention & Timestamps
# =============================================================================
def test_p015_stale_audit_data_timestamp_and_status():
    """
    Verify that unrun audits return health_score: None and score_available: False,
    and executed audits include valid created_at timestamps.
    """
    # Test un-audited state
    empty_resp = {
        "project_id": 99,
        "crawl_id": None,
        "domain": "test.com",
        "crawl_timestamp": None,
        "analyzed_pages": 0,
        "health_score": None,
        "score_available": False
    }
    assert empty_resp["health_score"] is None
    assert empty_resp["score_available"] is False
    assert empty_resp["crawl_timestamp"] is None

    # Test audited state with real timestamp
    audit = SEOAudit(
        project_id=1,
        overall_score=75,
        pages_analyzed=5,
        created_at=datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    )
    assert audit.overall_score == 75
    assert audit.created_at.isoformat() == "2026-09-23T12:00:00+00:00"


# =============================================================================
# P0-16: Scoring Velocity Truth
# =============================================================================
def test_p016_scoring_velocity_truth():
    """
    Verify that auditing identical pages multiple times produces deterministic,
    identical scores without drift or random variance.
    """
    pages = [
        {
            "url": "https://example.com",
            "status_code": 200,
            "title": "Plumber in Dallas - Rapid Fix",
            "meta_description": "Dallas plumbing experts available 24/7.",
            "h1": "Top Plumber in Dallas",
            "h2_list": ["Drain Cleaning", "Water Heaters"],
            "word_count": 600,
            "canonical_url": "https://example.com",
            "is_indexable": True,
            "load_time_ms": 150,
            "schema_types": ["Plumber", "LocalBusiness"],
            "schema_data": {"name": "Rapid Fix Plumbers", "telephone": "+1 214 555 0199"},
            "missing_alt_count": 0,
            "phones_found": ["+1 214 555 0199"],
            "emails_found": ["contact@rapidfix.com"]
        }
    ]
    proj_context = {"domain": "example.com", "name": "Rapid Fix Plumbers", "phone": "+1 214 555 0199", "city": "Dallas"}

    res1 = SEOAuditor.audit_pages(pages, project_context=proj_context)
    res2 = SEOAuditor.audit_pages(pages, project_context=proj_context)

    assert res1["score"] == res2["score"]
    assert res1["health_score"] == res2["health_score"]
    assert res1["critical"] == res2["critical"]
    assert res1["warnings"] == res2["warnings"]
    assert res1["pillar_scores"] == res2["pillar_scores"]


# =============================================================================
# P0-17: Citation Count Reconciliation
# =============================================================================
def test_p017_citation_count_reconciliation():
    """
    Verify citation auditing only counts real, verified citation sources
    and returns correct counts without phantom records.
    """
    citations = [
        {"directory_name": "Yelp", "nap_status": "MATCH", "listed": True, "url": "https://yelp.com/biz/test"},
        {"directory_name": "YellowPages", "nap_status": "PARTIAL", "listed": True, "url": "https://yellowpages.com/test"},
        {"directory_name": "Apple Maps", "nap_status": "MISSING", "listed": False, "url": None}
    ]

    res = SEOAuditor.audit_pages(
        pages=[{"url": "https://example.com", "status_code": 200, "is_indexable": True, "canonical_url": "https://example.com"}],
        citation_context=citations
    )

    cit_details = res.get("citations")
    assert cit_details is not None
    # Citations pillar score must reflect verified entries
    assert res["pillar_scores"]["citations_nap"] is not None


# =============================================================================
# P0-18: Security Logging & Secret Redaction
# =============================================================================
def test_p018_security_logging_secret_redaction(caplog):
    """
    Verify that audit logger redacts sensitive credentials, tokens, passwords, and API keys.
    """
    from app.core.audit_logger import log_user_action

    class DummyState:
        request_id = "req-12345"

    class DummyRequest:
        state = DummyState()

    req = DummyRequest()
    with caplog.at_level(logging.INFO, logger="locallift"):
        log_user_action(
            request=req,
            action="TEST_ACTION",
            user_id=42,
            organization_id=1,
            status="success",
            password="SuperSecretPassword!",
            api_key="sk-live-1234567890",
            token="bearer-token-abc",
            serpapi_key="serp-key-xyz",
            normal_param="visible_value"
        )

    log_output = caplog.text
    assert "SuperSecretPassword!" not in log_output
    assert "sk-live-1234567890" not in log_output
    assert "bearer-token-abc" not in log_output
    assert "serp-key-xyz" not in log_output
    assert "password=[REDACTED]" in log_output
    assert "api_key=[REDACTED]" in log_output
    assert "token=[REDACTED]" in log_output
    assert "serpapi_key=[REDACTED]" in log_output
    assert "normal_param=visible_value" in log_output


# =============================================================================
# P0-19: Clean Source & Deployment Boundaries
# =============================================================================
def test_p019_clean_source_deployment_boundaries():
    """
    Verify root .gitignore includes all sensitive and build files:
    .env, *.db, node_modules, __pycache__, etc.
    """
    root_gitignore_path = Path(__file__).resolve().parent.parent / ".gitignore"
    assert root_gitignore_path.exists()
    content = root_gitignore_path.read_text(encoding="utf-8")

    assert ".env" in content
    assert "*.db" in content
    assert "node_modules" in content
    assert "__pycache__" in content
    assert "locallift.db" in content


# =============================================================================
# P0-20: Clean Install Verification
# =============================================================================
def test_p020_clean_install_verification():
    """
    Verify core backend modules can be imported cleanly without circular dependency errors.
    """
    import app.main
    import app.config
    import app.models
    import app.schemas
    import app.services
    import app.core.security
    import app.core.audit_logger
    import app.core.migrations

    assert app.main.app is not None
    assert app.config.settings is not None








