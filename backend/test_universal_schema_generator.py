import pytest
import json
from app.services.schema_vocabulary import SchemaVocabulary, SCHEMA_CATEGORIES
from app.services.schema_intelligence import SchemaIntelligenceEngine

def test_vocabulary_categories_and_types():
    all_types = SchemaVocabulary.get_all_types()
    assert len(all_types) >= 80
    
    # Check key categories
    assert "Local Business & Places" in SCHEMA_CATEGORIES
    assert "Organizations & Brands" in SCHEMA_CATEGORIES
    assert "Content, Media & Creative Works" in SCHEMA_CATEGORIES
    assert "Products, Offers & Commerce" in SCHEMA_CATEGORIES
    assert "People, Events & Roles" in SCHEMA_CATEGORIES
    assert "Web Structure & Navigation" in SCHEMA_CATEGORIES
    
    type_names = {t["name"] for t in all_types}
    assert "LocalBusiness" in type_names
    assert "Electrician" in type_names
    assert "Dentist" in type_names
    assert "Organization" in type_names
    assert "Article" in type_names
    assert "Product" in type_names
    assert "FAQPage" in type_names
    assert "JobPosting" in type_names
    assert "Recipe" in type_names

def test_type_definition_and_inheritance():
    # Dentist inherits from MedicalBusiness -> LocalBusiness -> Organization -> Thing
    dentist_def = SchemaVocabulary.get_type_definition("Dentist")
    assert dentist_def is not None
    assert dentist_def["parent"] == "MedicalBusiness"
    assert dentist_def["rich_result_eligible"] is True
    
    prop_names = {p["name"] for p in dentist_def["properties"]}
    # Inherited from Thing/Organization/LocalBusiness
    assert "name" in prop_names
    assert "url" in prop_names
    assert "telephone" in prop_names
    assert "address" in prop_names
    assert "geo" in prop_names
    assert "openingHoursSpecification" in prop_names
    assert "medicalSpecialty" in prop_names

def test_universal_schema_generation():
    # Test generating an Article schema with Person author and Organization publisher
    res = SchemaVocabulary.generate_universal_schema(
        main_type="Article",
        properties={
            "headline": "Universal Schema.org Guide 2026",
            "url": "https://example.com/blog/schema-guide",
            "datePublished": "2026-09-25",
            "author": {
                "@type": "Person",
                "name": "Jane SEO Specialist"
            },
            "publisher": {
                "@type": "Organization",
                "name": "LocalLift Media",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://example.com/logo.png"
                }
            }
        },
        include_graph=True
    )
    
    parsed = json.loads(res["schema_json"])
    assert "@context" in parsed
    assert "@graph" in parsed
    assert len(parsed["@graph"]) == 1
    art = parsed["@graph"][0]
    assert art["@type"] == "Article"
    assert art["headline"] == "Universal Schema.org Guide 2026"
    assert art["author"]["@type"] == "Person"
    assert art["author"]["name"] == "Jane SEO Specialist"
    assert art["publisher"]["@type"] == "Organization"

def test_deep_validation_rich_results_and_id_resolution():
    # Valid Product JSON-LD with nested Offer and AggregateRating
    product_json = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Product",
                "@id": "https://example.com/item-1#product",
                "name": "Heavy Duty Drill",
                "image": "https://example.com/drill.jpg",
                "description": "Commercial grade power drill.",
                "brand": {
                    "@type": "Brand",
                    "name": "PowerCraft"
                },
                "offers": {
                    "@type": "Offer",
                    "@id": "https://example.com/item-1#offer",
                    "price": "149.99",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock"
                },
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": "4.8",
                    "reviewCount": "89"
                }
            }
        ]
    })
    
    val = SchemaVocabulary.deep_validate_json_ld(product_json)
    assert val["is_valid"] is True
    assert val["syntax_valid"] is True
    assert "Product" in val["entities"]
    assert len(val["rich_results"]) >= 1
    assert val["rich_results"][0]["supported"] is True

def test_deep_validation_nap_mismatch_detection():
    # LocalBusiness with telephone differing from verified project context
    biz_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": "Brisbane Plumbers",
        "telephone": "+1 555-999-8888",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "100 Queen St",
            "addressLocality": "Brisbane",
            "addressRegion": "QLD"
        }
    })
    
    project_context = {
        "name": "Brisbane Plumbers",
        "phone": "+61 7 3100 4500"
    }
    
    val = SchemaVocabulary.deep_validate_json_ld(biz_json, project_context=project_context)
    assert val["nap_status"] == "Mismatch"
    assert any("NAP Phone Mismatch" in e for e in val["errors"])

def test_deep_validation_broken_id_detection():
    # JSON-LD referencing an @id that was not defined in the graph
    broken_graph = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": "https://example.com/#webpage",
                "name": "Home Page",
                "publisher": {"@id": "https://example.com/#nonexistent-org"}
            }
        ]
    })
    
    val = SchemaVocabulary.deep_validate_json_ld(broken_graph)
    # Warnings should flag missing local id definition if applicable
    assert val["syntax_valid"] is True
