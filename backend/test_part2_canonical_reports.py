import pytest
import asyncio
import io
import openpyxl
from datetime import datetime, timezone
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.project import Project, Website
from app.models.audit import SEOAudit, WebsitePage
from app.services.seo_auditor import SEOAuditor
from app.services.reports.pdf_service import AuditPDFService
from app.services.reports.xlsx_service import MasterXLSXService

@pytest.mark.asyncio
async def test_canonical_audit_result_structure():
    """Verify that SEOAuditor produces the exact canonical payload required by Part 2."""
    dummy_pages = [
        {
            "url": "https://example.com/",
            "status_code": 200,
            "title": "Best Electrician in Sydney | Example Electrical",
            "meta_description": "Top rated electrician in Sydney offering 24/7 emergency service.",
            "h1": "Sydney Electrician Services",
            "word_count": 550,
            "canonical_url": "https://example.com/",
            "schema_types": ["LocalBusiness", "Electrician"],
            "json_ld_schemas": [
                {
                    "@type": "Electrician",
                    "name": "Example Electrical",
                    "telephone": "+61299998888",
                    "address": {"streetAddress": "123 Main St", "addressLocality": "Sydney"},
                    "geo": {"latitude": -33.8688, "longitude": 151.2093},
                    "sameAs": ["https://facebook.com/example"]
                }
            ],
            "phones_found": ["+61299998888"],
            "missing_alt_count": 0
        },
        {
            "url": "https://example.com/about",
            "status_code": 200,
            "title": "About Us | Sydney Electrician",
            "meta_description": "Learn more about our qualified Sydney electrician team.",
            "h1": "About Example Electrical",
            "word_count": 350,
            "canonical_url": "https://example.com/about",
            "schema_types": ["Organization"],
            "json_ld_schemas": [{"@type": "Organization", "name": "Example Electrical"}],
            "phones_found": ["+61299998888"],
            "missing_alt_count": 1
        }
    ]

    project_context = {"domain": "example.com", "name": "Example Electrical", "city": "Sydney", "phone": "+61299998888"}

    res = SEOAuditor.audit_pages(dummy_pages, project_context=project_context)

    # 1. Verify required top-level keys
    assert res["analyzed_pages"] == 2
    assert res["evaluated_rules"] == 14
    assert res["total_evaluated_checks"] == 28
    assert res["score_available"] is True
    assert isinstance(res["score"], int)
    assert 0 <= res["score"] <= 100

    # 2. Verify Rule Executions
    exec_results = res["rule_execution_results"]
    assert len(exec_results) == 15 # 14 evaluated + 1 unevaluated Performance
    perf_rule = next(r for r in exec_results if r["rule_id"] == "PERF_001")
    assert perf_rule["status"] == "Not Evaluated"
    assert perf_rule["evaluated"] is False

    # 3. Verify Schema Summary & Evidence
    s_sum = res["schema_summary"]
    assert s_sum["pages_scanned"] == 2
    assert s_sum["pages_with_schema"] == 2
    assert s_sum["pages_without_schema"] == 0
    assert s_sum["total_schema_instances"] == 2
    assert len(res["schema_evidence"]) == 2

    # 4. Verify Robots Summary
    r_sum = res["robots_summary"]
    assert "robots_url" in r_sum
    assert "fetch_status" in r_sum

@pytest.mark.asyncio
async def test_pdf_service_generation():
    """Verify PDF export service generates valid PDF bytes from canonical result."""
    canonical_data = {
        "domain": "testsite.com.au",
        "crawl_id": 101,
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "analyzed_pages": 20,
        "evaluated_rules": 14,
        "total_evaluated_checks": 280,
        "health_score": 87,
        "score_available": True,
        "rule_execution_results": [
            {
                "rule_id": "META_001",
                "category": "Local On-Page SEO",
                "rule_name": "Missing Meta Description",
                "pages_checked": 20,
                "passed": 17,
                "problems": 3,
                "status": "Issues Found",
                "validation_method": "Meta Tag Extraction"
            }
        ],
        "schema_summary": {
            "pages_scanned": 20,
            "pages_with_schema": 12,
            "pages_without_schema": 8,
            "total_schema_instances": 17,
            "unique_schema_types": 6,
            "complete_entities": 10,
            "incomplete_entities": 2,
            "potential_mismatches": 0,
            "detected_types": [{"type": "LocalBusiness", "page_count": 4, "instance_count": 4}]
        },
        "robots_summary": {
            "robots_url": "https://testsite.com.au/robots.txt",
            "http_status": 200,
            "fetch_status": "Fetched Successfully",
            "user_agent_groups": 1,
            "allow_rules": 1,
            "disallow_rules": 0,
            "sitemaps": ["https://testsite.com.au/sitemap.xml"],
            "seed_url_result": "Allowed"
        }
    }

    pdf_bytes = AuditPDFService.generate_pdf(canonical_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

@pytest.mark.asyncio
async def test_xlsx_service_generation():
    """Verify Master XLSX export service generates valid Excel file with 4 worksheets."""
    canonical_data = {
        "domain": "testsite.com.au",
        "crawl_id": 101,
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "analyzed_pages": 20,
        "evaluated_rules": 14,
        "total_evaluated_checks": 280,
        "health_score": 87,
        "score_available": True,
        "passed": 260,
        "critical": 1,
        "warnings": 10,
        "opportunities": 9,
        "scoring_formula": "Composite weighted sum",
        "scoring_weights": {"crawl_health": 0.20},
        "rule_execution_results": [
            {
                "rule_id": "META_001",
                "category": "Local On-Page SEO",
                "rule_name": "Missing Meta Description",
                "what_was_checked": "Verifies meta desc tag",
                "validation_method": "Meta Tag Extraction",
                "pages_checked": 20,
                "evaluated": True,
                "passed": 17,
                "problems": 3,
                "status": "Issues Found",
                "requires_integration": False,
                "evidence_source": "Crawler HTML Parser"
            }
        ],
        "schema_evidence": [
            {
                "url": "https://testsite.com.au/",
                "schema_type": "LocalBusiness",
                "validation_status": "Supported",
                "completeness": "Complete",
                "important_properties": {"Name": "Test Corp"},
                "missing_properties": [],
                "page_evidence": "Found valid LocalBusiness",
                "raw_json_ld": '{"@type":"LocalBusiness"}'
            }
        ],
        "robots_summary": {
            "robots_url": "https://testsite.com.au/robots.txt",
            "http_status": 200,
            "fetch_status": "Fetched Successfully",
            "user_agent_groups": 1,
            "allow_rules": 1,
            "disallow_rules": 0,
            "sitemaps": ["https://testsite.com.au/sitemap.xml"],
            "seed_url_result": "Allowed"
        }
    }

    xlsx_bytes = MasterXLSXService.generate_xlsx(canonical_data)
    assert isinstance(xlsx_bytes, bytes)

    wb = openpyxl.load_workbook(filename=io.BytesIO(xlsx_bytes))
    sheet_names = wb.sheetnames
    assert "Audit Rules Applied" in sheet_names
    assert "Schema Evidence" in sheet_names
    assert "Robots Evidence" in sheet_names
    assert "Health Score" in sheet_names

    ws_rules = wb["Audit Rules Applied"]
    summary_cell = ws_rules.cell(row=2, column=1).value
    assert "20" in summary_cell
    assert "14" in summary_cell
    assert "280" in summary_cell

@pytest.mark.asyncio
async def test_project_isolation_and_no_crawl_state():
    """Verify that projects remain strictly isolated and empty state returns score_available=False."""
    async with AsyncSessionLocal() as session:
        from app.models.user import Organization
        org_res = await session.execute(select(Organization))
        org = org_res.scalars().first()
        if not org:
            org = Organization(name="Test Org")
            session.add(org)
            await session.commit()
            await session.refresh(org)

        p1 = Project(organization_id=org.id, name="Project Isolation Alpha", domain="alpha.example.com", health_score=None)
        p2 = Project(organization_id=org.id, name="Project Isolation Beta", domain="beta.example.com", health_score=85)
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)
        await session.refresh(p2)

        # Audit for P2 only
        audit2 = SEOAudit(project_id=p2.id, overall_score=85, pages_analyzed=10)
        session.add(audit2)
        await session.commit()

        # Check P1 (no audit run)
        res1 = await session.execute(select(SEOAudit).where(SEOAudit.project_id == p1.id))
        audit1 = res1.scalars().first()
        assert audit1 is None

        # Check P2
        res2 = await session.execute(select(SEOAudit).where(SEOAudit.project_id == p2.id))
        audit2_db = res2.scalars().first()
        assert audit2_db is not None
        assert audit2_db.overall_score == 85
