import pytest
import json
from bs4 import BeautifulSoup
from app.services.schema_intelligence import SchemaIntelligenceEngine, TIER_1_SCHEMAS

def test_single_and_multiple_json_ld_scripts_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "@id": "https://queenshineelectricals.com.au/#organization",
            "name": "Queenshine Electricals Pty Ltd",
            "url": "https://queenshineelectricals.com.au",
            "telephone": "+61 7 3100 4500",
            "sameAs": ["https://facebook.com/queenshine", "https://linkedin.com/company/queenshine"]
        }
        </script>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "@id": "https://queenshineelectricals.com.au/#website",
            "name": "Queenshine Electricals",
            "url": "https://queenshineelectricals.com.au"
        }
        </script>
    </head>
    <body>
        <h1>Queenshine Electricals</h1>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = SchemaIntelligenceEngine.extract_structured_data(soup, "https://queenshineelectricals.com.au")

    assert "Organization" in result["schema_types"]
    assert "WebSite" in result["schema_types"]
    assert len(result["json_ld_schemas"]) == 2
    assert len(result["schema_entities"]) >= 2
    assert len(result["schema_parse_errors"]) == 0

    # Verify actual extracted properties on Organization
    org_ent = next(e for e in result["schema_entities"] if e["@type"] == "Organization")
    assert org_ent["properties"]["name"] == "Queenshine Electricals Pty Ltd"
    assert org_ent["properties"]["telephone"] == "+61 7 3100 4500"
    assert len(org_ent["properties"]["sameAs"]) == 2

def test_graph_and_nested_entities_unpacking():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "LocalBusiness",
                    "@id": "https://queenshineelectricals.com.au/#localbusiness",
                    "name": "Queenshine Electricals",
                    "telephone": "+61 7 3100 4500",
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": "142 Queen Street",
                        "addressLocality": "Brisbane",
                        "addressRegion": "QLD",
                        "postalCode": "4000",
                        "addressCountry": "AU"
                    },
                    "geo": {
                        "@type": "GeoCoordinates",
                        "latitude": -27.4698,
                        "longitude": 153.0251
                    },
                    "parentOrganization": {
                        "@type": "Organization",
                        "@id": "https://queenshineelectricals.com.au/#organization",
                        "name": "Queenshine Holdings"
                    }
                },
                {
                    "@type": "Service",
                    "@id": "https://queenshineelectricals.com.au/#service",
                    "name": "Switchboard Upgrades",
                    "provider": {
                        "@id": "https://queenshineelectricals.com.au/#localbusiness"
                    }
                },
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://queenshineelectricals.com.au"},
                        {"@type": "ListItem", "position": 2, "name": "Services", "item": "https://queenshineelectricals.com.au/services"}
                    ]
                }
            ]
        }
        </script>
    </head>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = SchemaIntelligenceEngine.extract_structured_data(soup, "https://queenshineelectricals.com.au/services")

    assert "LocalBusiness" in result["schema_types"]
    assert "Organization" in result["schema_types"]
    assert "Service" in result["schema_types"]
    assert "BreadcrumbList" in result["schema_types"]

    # Verify nested parentOrganization was unpacked
    org_ent = next(e for e in result["schema_entities"] if e["@type"] == "Organization")
    assert org_ent["properties"]["name"] == "Queenshine Holdings"

    # Verify PostalAddress inside LocalBusiness
    biz_ent = next(e for e in result["schema_entities"] if e["@type"] == "LocalBusiness")
    assert biz_ent["properties"]["telephone"] == "+61 7 3100 4500"
    assert biz_ent["properties"]["address"]["addressLocality"] == "Brisbane"
    assert biz_ent["properties"]["geo"]["latitude"] == -27.4698

def test_malformed_json_ld_sanitization():
    # Notice trailing comma after priceRange
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Queenshine Electricals",
            "priceRange": "$$",
        }
        </script>
    </head>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = SchemaIntelligenceEngine.extract_structured_data(soup, "https://example.com")

    # Should recover gracefully and extract LocalBusiness
    assert "LocalBusiness" in result["schema_types"]
    ent = result["schema_entities"][0]
    assert ent["properties"]["name"] == "Queenshine Electricals"

def test_tier_1_applicability_and_scoring():
    # 1. Homepage applicability for Electrician business
    homepage_app = SchemaIntelligenceEngine.evaluate_applicability(
        page_type="Homepage",
        business_type="Electrician"
    )
    assert homepage_app["WebSite"]["applicability"] == "Highly Applicable"
    assert homepage_app["WebPage"]["applicability"] == "Highly Applicable"
    assert homepage_app["Organization"]["applicability"] == "Highly Applicable"
    assert homepage_app["LocalBusiness"]["applicability"] == "Highly Applicable"

    # 2. Service subpage applicability
    service_app = SchemaIntelligenceEngine.evaluate_applicability(
        page_type="Service",
        business_type="Electrician"
    )
    assert service_app["Service"]["applicability"] == "Highly Applicable"
    assert service_app["BreadcrumbList"]["applicability"] == "Highly Applicable"
    assert service_app["Product"]["applicability"] == "Not Applicable"

def test_nap_validation_and_mismatch_detection():
    project_ctx = {
        "name": "Queenshine Electricals",
        "domain": "queenshineelectricals.com.au",
        "phone": "+61 7 3100 4500",
        "address": "142 Queen Street, Brisbane QLD 4000",
        "latitude": -27.4698,
        "longitude": 153.0251
    }

    matching_entity = {
        "@type": "LocalBusiness",
        "raw": {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Queenshine Electricals",
            "telephone": "(07) 3100 4500",
            "url": "https://queenshineelectricals.com.au",
            "address": {
                "streetAddress": "142 Queen Street",
                "addressLocality": "Brisbane",
                "postalCode": "4000"
            },
            "geo": {
                "latitude": -27.4698,
                "longitude": 153.0251
            }
        }
    }

    res_match = SchemaIntelligenceEngine.validate_entity(matching_entity, project_context=project_ctx)
    assert res_match["is_valid"] is True
    assert res_match["nap_match_status"] == "Consistent"
    assert len(res_match["errors"]) == 0

    # Test Phone Mismatch
    mismatch_entity = {
        "@type": "LocalBusiness",
        "raw": {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Queenshine Electricals",
            "telephone": "+1 800 555 0199",
            "address": {"streetAddress": "142 Queen Street"}
        }
    }
    res_mismatch = SchemaIntelligenceEngine.validate_entity(mismatch_entity, project_context=project_ctx)
    assert res_mismatch["nap_match_status"] == "Mismatch"
    assert any("Phone Mismatch" in err for err in res_mismatch["errors"])

def test_safe_schema_generator_with_graph():
    gen_result = SchemaIntelligenceEngine.generate_safe_schema(
        business_type="Electrician",
        business_name="Queenshine Electricals",
        url="https://queenshineelectricals.com.au",
        phone="+61 7 3100 4500",
        street_address="142 Queen Street",
        city="Brisbane",
        state="QLD",
        postal_code="4000",
        country="AU",
        latitude=-27.4698,
        longitude=153.0251,
        service_name="Emergency Electrician",
        include_graph=True
    )

    assert gen_result["is_valid"] is True
    assert len(gen_result["validation_errors"]) == 0
    parsed = json.loads(gen_result["json_ld"])
    assert "@graph" in parsed
    types_in_graph = [item["@type"] for item in parsed["@graph"]]
    assert "Organization" in types_in_graph
    assert "Electrician" in types_in_graph
    assert "WebSite" in types_in_graph
    assert "WebPage" in types_in_graph
    assert "Service" in types_in_graph
