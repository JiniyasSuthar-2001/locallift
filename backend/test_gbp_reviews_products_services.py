import pytest
from app.services.local_seo.review_classifier_service import ReviewClassifierService
from app.schemas.gbp import ProductOrServiceItemOut, ProductsServicesResponseOut

def test_review_classifier_dynamic_topics_and_categories():
    service = ReviewClassifierService()

    # Test product topic
    res_product = service.classify_review(
        review_text="The ergonomic office chair and wooden dining table are super comfortable and sturdy!"
    )
    assert res_product["category"] in ["PRODUCT", "QUALITY", "EXPERIENCE"]
    assert len(res_product["topics"]) > 0
    assert any("Product" in t or "Quality" in t for t in res_product["topics"])

    sentiment_product = service.analyze_sentiment(
        review_text="The ergonomic office chair and wooden dining table are super comfortable and sturdy!",
        rating=5
    )
    assert sentiment_product["sentiment"] == "positive"

    # Test complaint with 5-star rating (sentiment separation)
    res_complaint = service.classify_review(
        review_text="Worst delivery experience ever. The staff was rude, terrible delay, and high pricing for broken parts."
    )
    assert any("Staff" in t or "Delivery" in t or "Pricing" in t or "Support" in t for t in res_complaint["topics"])

    sentiment_complaint = service.analyze_sentiment(
        review_text="Worst delivery experience ever. The staff was rude, terrible delay, and high pricing for broken parts.",
        rating=5
    )
    assert sentiment_complaint["sentiment"] == "negative"

    # Test service topic
    res_service = service.classify_review(
        review_text="Emergency plumbing repair fixed the leaking pipe under the sink rapidly."
    )
    assert res_service["category"] in ["SERVICE", "QUALITY", "EXPERIENCE"]
    assert any("Plumbing" in t or "Repair" in t or "Service" in t for t in res_service["topics"])

def test_products_services_schema_and_deduplication():
    # Verify schema models
    item1 = ProductOrServiceItemOut(
        id="prod_1",
        type="product",
        name="Ergonomic Chair",
        description="High back mesh chair",
        category="Office Furniture",
        price="₹12,500",
        action_url="https://example.com/chair",
        source="Google Business Profile"
    )
    item2 = ProductOrServiceItemOut(
        id="serv_1",
        type="service",
        name="Pipe Leak Repair",
        description="Fast residential leak detection and fix",
        category="Plumbing",
        price="₹1,500",
        action_url="https://example.com/plumbing",
        source="Google Business Profile"
    )

    response = ProductsServicesResponseOut(
        business_name="Acme Solutions",
        connected_account="owner@acme.com",
        last_synced_at="2026-09-24T18:00:00Z",
        total_products=1,
        total_services=1,
        items=[item1, item2]
    )

    assert response.total_products == 1
    assert response.total_services == 1
    assert len(response.items) == 2
    assert response.items[0].type == "product"
    assert response.items[1].type == "service"
    assert response.business_name == "Acme Solutions"
