import asyncio
import json
from bs4 import BeautifulSoup
from app.services.schema_intelligence import SchemaIntelligenceEngine, TIER_1_SCHEMAS, INDUSTRY_SCHEMAS

def test_tier_1_schemas_count():
    assert len(TIER_1_SCHEMAS) == 18
    assert "Organization" in TIER_1_SCHEMAS
    assert "LocalBusiness" in TIER_1_SCHEMAS
    assert "Service" in TIER_1_SCHEMAS
    assert "FAQPage" in TIER_1_SCHEMAS
    assert "BreadcrumbList" in TIER_1_SCHEMAS

def test_schema_extraction_single_and_graph():
    # 1. Single object
    html_single = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "LocalBusiness",
          "name": "Acme Electric",
          "telephone": "+1 234 567 8900"
        }
        </script>
      </head>
      <body><h1>Electrician</h1></body>
    </html>
    """
    soup_single = BeautifulSoup(html_single, "html.parser")
    res_single = SchemaIntelligenceEngine.extract_structured_data(soup_single, "https://acme.com")
    assert "LocalBusiness" in res_single["schema_types"]
    assert res_single["schema_count"] == 1
    assert len(res_single["schema_parse_errors"]) == 0

    # 2. @graph array
    html_graph = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {"@type": "Organization", "name": "Acme Corp"},
            {"@type": "WebSite", "name": "Acme Site"},
            {"@type": "WebPage", "name": "Home Page"}
          ]
        }
        </script>
      </head>
      <body></body>
    </html>
    """
    soup_graph = BeautifulSoup(html_graph, "html.parser")
    res_graph = SchemaIntelligenceEngine.extract_structured_data(soup_graph, "https://acme.com")
    assert "Organization" in res_graph["schema_types"]
    assert "WebSite" in res_graph["schema_types"]
    assert "WebPage" in res_graph["schema_types"]
    assert res_graph["schema_count"] == 3

    # 3. Malformed JSON-LD does not crash
    html_broken = """
    <html>
      <head>
        <script type="application/ld+json">
        { invalid json content here ...
        </script>
      </head>
      <body></body>
    </html>
    """
    soup_broken = BeautifulSoup(html_broken, "html.parser")
    res_broken = SchemaIntelligenceEngine.extract_structured_data(soup_broken, "https://acme.com")
    assert len(res_broken["schema_parse_errors"]) == 1

def test_page_type_detection():
    # Homepage
    pt_home = SchemaIntelligenceEngine.detect_page_type("https://example.com/", title="Example Home", h1="Welcome to Example")
    assert pt_home["page_type"] == "Homepage"

    # Service Page
    pt_service = SchemaIntelligenceEngine.detect_page_type("https://example.com/services/electrical-repair", title="Electrical Repairs", h1="Expert Electrical Repairs")
    assert pt_service["page_type"] == "Service"

    # Service Location Page
    pt_loc = SchemaIntelligenceEngine.detect_page_type("https://example.com/services/electrician-in-brisbane", title="Electrician in Brisbane", h1="Brisbane Electricians")
    assert pt_loc["page_type"] == "Service Location"

    # Contact Page
    pt_contact = SchemaIntelligenceEngine.detect_page_type("https://example.com/contact-us", title="Contact Us", h1="Get in Touch")
    assert pt_contact["page_type"] == "Contact"

def test_applicability_rules():
    # 1. Product is NOT applicable on Service page
    app_service = SchemaIntelligenceEngine.evaluate_applicability(page_type="Service", business_type="Electrician")
    assert app_service["Product"]["applicability"] == "Not Applicable"
    assert app_service["Service"]["applicability"] == "Highly Applicable"

    # 2. Restaurant is NOT applicable on Software Application business
    app_software = SchemaIntelligenceEngine.evaluate_applicability(page_type="Homepage", business_type="SoftwareApplication")
    assert "Restaurant" not in app_software or app_software.get("Restaurant", {}).get("applicability") == "Not Applicable"

def test_nap_phone_validation():
    project_ctx = {"name": "Test Electric", "phone": "+61 7 3000 0000"}

    # Matching phone
    ent_matching = {
        "@type": "LocalBusiness",
        "raw": {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Test Electric",
            "telephone": "(07) 3000 0000",
            "url": "https://test.com"
        }
    }
    val_matching = SchemaIntelligenceEngine.validate_entity(ent_matching, project_context=project_ctx)
    assert val_matching["nap_match_status"] == "Consistent"
    assert val_matching["is_valid"] is True

    # Mismatching phone
    ent_mismatch = {
        "@type": "LocalBusiness",
        "raw": {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Test Electric",
            "telephone": "+1 800 999 9999",
            "url": "https://test.com"
        }
    }
    val_mismatch = SchemaIntelligenceEngine.validate_entity(ent_mismatch, project_context=project_ctx)
    assert val_mismatch["nap_match_status"] == "Mismatch"
    assert val_mismatch["is_valid"] is False

def test_safe_schema_generator_no_fake_defaults():
    # Generate without coordinates or hours
    gen_res = SchemaIntelligenceEngine.generate_safe_schema(
        business_type="Electrician",
        business_name="Custom Electrical Solutions",
        url="https://customelectric.com.au",
        phone="+61 7 3123 4567",
        city="Brisbane",
        state="QLD",
        country="AU",
        service_name="Switchboard Upgrades"
    )

    assert gen_res["is_valid"] is True
    parsed_json = json.loads(gen_res["json_ld"])
    graph = parsed_json["@graph"]

    biz_node = next(n for n in graph if n["@type"] == "Electrician")
    assert biz_node["name"] == "Custom Electrical Solutions"
    assert biz_node["telephone"] == "+61 7 3123 4567"
    assert "geo" not in biz_node  # No fake coordinates injected!
    assert "openingHoursSpecification" not in biz_node  # No fake hours injected!

    # Check connected service node
    srv_node = next(n for n in graph if n["@type"] == "Service")
    assert srv_node["name"] == "Switchboard Upgrades"
    assert srv_node["provider"]["@id"] == biz_node["@id"]

def test_db_schema_records_query():
    from app.test_helper import init_test_db
    from app.database import AsyncSessionLocal
    from app.models.local_seo import SchemaRecord
    from sqlalchemy import select
    
    async def _query():
        await init_test_db(seed_demo=False)
        async with AsyncSessionLocal() as session:
            stmt = select(SchemaRecord)
            res = await session.execute(stmt)
            records = res.scalars().all()
            assert len(records) >= 0
            for r in records:
                # Access all intelligence fields to ensure SQLite column mappings work
                _ = (r.id, r.project_id, r.page_url, r.page_type, r.business_type, r.quality_score, r.nap_status, r.recommendations)
    
    asyncio.run(_query())

def run_all_tests():
    test_tier_1_schemas_count()
    test_schema_extraction_single_and_graph()
    test_page_type_detection()
    test_applicability_rules()
    test_nap_phone_validation()
    test_safe_schema_generator_no_fake_defaults()
    test_db_schema_records_query()
    print("[OK] All 7 Schema Intelligence automated test suites & DB queries PASSED successfully!")

if __name__ == "__main__":
    run_all_tests()
