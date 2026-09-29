import os
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.local_seo import Review, BusinessProfile
from app.models.connections import PublicBusinessListing
from app.services.local_seo.review_classifier_service import ReviewClassifierService
from app.services.google.public_maps_service import PublicGoogleMapsService


# ─── 1. TEST REVIEW CLASSIFIER SERVICE ───

def test_review_classification_categories():
    # Product / Website
    res1 = ReviewClassifierService.classify_review("Very professional product and clean design with high quality material!", 5)
    assert res1["category"] in ["PRODUCT", "QUALITY", "EXPERIENCE"]
    assert res1["confidence"] >= 0.7

    # Service / App
    res2 = ReviewClassifierService.classify_review("Great plumbing repair and maintenance service team. Quick fix on the pipe.", 5)
    assert res2["category"] in ["SERVICE", "QUALITY", "EXPERIENCE"]
    assert res2["confidence"] >= 0.7

    # Staff
    res3 = ReviewClassifierService.classify_review("The staff was super friendly, polite, and very knowledgeable technicians.", 5)
    assert res3["category"] in ["STAFF", "EXPERIENCE"]
    assert res3["confidence"] >= 0.7

    # Pricing
    res4 = ReviewClassifierService.classify_review("Fair price, great discount, and affordable cost for the quality delivered.", 5)
    assert res4["category"] in ["PRICING", "QUALITY"]
    assert res4["confidence"] >= 0.7

    # Support
    res6 = ReviewClassifierService.classify_review("Super responsive customer service and prompt assistance whenever we need troubleshooting.", 5)
    assert res6["category"] in ["SUPPORT", "SERVICE", "EXPERIENCE"]
    assert res6["confidence"] >= 0.7

    # General / Other
    res7 = ReviewClassifierService.classify_review("Great team to work with! Wonderful experience.", 5)
    assert res7["category"] in ["EXPERIENCE", "STAFF", "OTHER"]

    # Empty text
    res8 = ReviewClassifierService.classify_review("", 5)
    assert res8["category"] == "OTHER"


def test_sentiment_analysis():
    # Positive
    s1 = ReviewClassifierService.analyze_sentiment("Excellent work! Top-notch quality and fantastic team.", 5)
    assert s1["sentiment"] == "positive"
    assert s1["sentiment_score"] >= 0.7

    # Negative
    s2 = ReviewClassifierService.analyze_sentiment("Terrible experience. Rude staff, slow delivery, and waste of money.", 1)
    assert s2["sentiment"] == "negative"
    assert s2["sentiment_score"] <= 0.3

    # Neutral
    s3 = ReviewClassifierService.analyze_sentiment("Average service. Nothing special to mention.", 3)
    assert s3["sentiment"] == "neutral"

    # Rating only (no text)
    s4 = ReviewClassifierService.analyze_sentiment("", 5)
    assert s4["sentiment"] == "positive"
    assert s4["has_text"] is False

    s5 = ReviewClassifierService.analyze_sentiment("", 1)
    assert s5["sentiment"] == "negative"
    assert s5["has_text"] is False


# ─── 2. TEST BACKEND REST ENDPOINTS & MULTI-TENANT AUTHORIZATION ───

@pytest.mark.asyncio
async def test_public_reviews_flow_and_authorization():
    await init_test_db(reset=False)

    user1, org1, proj1, token1 = await create_test_tenant(
        project_name="Apex Web Solutions",
        domain="apexwebsolutions.com"
    )
    user2, org2, proj2, token2 = await create_test_tenant(
        project_name="Competitor Web Agency",
        domain="competitoragency.com"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = {"Authorization": f"Bearer {token1}"}
        h2 = {"Authorization": f"Bearer {token2}"}

        # 1. Initial State: No place ID bound yet -> status: "no_place_id"
        res_init = await client.get(f"/api/v1/local-seo/reviews/{proj1.id}", headers=h1)
        assert res_init.status_code == 200
        init_data = res_init.json()
        assert init_data["status"] == "no_place_id"
        assert init_data["error"] == "Select a Google business location to load public reviews."

        # 2. Search for Google Places via Text Search
        res_search = await client.get(
            f"/api/v1/local-seo/places/search?project_id={proj1.id}&query=Apex+Web+Solutions",
            headers=h1
        )
        assert res_search.status_code == 200
        search_data = res_search.json()
        assert search_data["status"] == "found"
        assert len(search_data["places"]) > 0
        cand_place = search_data["places"][0]
        assert "place_id" in cand_place
        assert cand_place["rating"] == 4.8
        assert cand_place["user_rating_count"] == 13

        # 3. Select Place for Project
        res_select = await client.post(
            "/api/v1/local-seo/places/select",
            headers=h1,
            json={
                "project_id": proj1.id,
                "place_id": cand_place["place_id"],
                "name": cand_place["name"],
                "formatted_address": cand_place["formatted_address"],
                "rating": cand_place["rating"],
                "user_rating_count": cand_place["user_rating_count"],
                "maps_url": cand_place["maps_url"],
                "website_url": cand_place["website_url"]
            }
        )
        assert res_select.status_code == 200
        select_data = res_select.json()
        assert select_data["status"] == "found"
        assert len(select_data["reviews"]) == 5  # 5 reviews available via Places API
        assert select_data["summary"]["total_google_reviews"] == 13  # Reported total by Google
        assert select_data["summary"]["reviews_available"] == 5
        assert select_data["summary"]["average_rating"] == 4.8

        # 4. Fetch Reviews List with Intelligence & Filters
        res_reviews = await client.get(f"/api/v1/local-seo/reviews/{proj1.id}", headers=h1)
        assert res_reviews.status_code == 200
        revs_data = res_reviews.json()
        assert revs_data["status"] == "found"
        assert len(revs_data["reviews"]) == 5
        
        # Verify review card fields
        r1 = revs_data["reviews"][0]
        assert "author_name" in r1
        assert "rating" in r1
        assert "review_text" in r1
        assert "category" in r1
        assert "sentiment" in r1
        assert "google_maps_uri" in r1

        # 5. Filter by Sentiment (Positive)
        res_pos = await client.get(f"/api/v1/local-seo/reviews/{proj1.id}?sentiment=positive", headers=h1)
        assert res_pos.status_code == 200
        pos_revs = res_pos.json()["reviews"]
        for pr in pos_revs:
            assert pr["sentiment"] == "positive"

        # 6. Filter by Category (SERVICE or EXPERIENCE)
        first_cat = revs_data["reviews"][0]["category"]
        res_cat = await client.get(f"/api/v1/local-seo/reviews/{proj1.id}?category={first_cat}", headers=h1)
        assert res_cat.status_code == 200
        cat_revs = res_cat.json()["reviews"]
        assert len(cat_revs) >= 1
        for cr in cat_revs:
            assert cr["category"] == first_cat

        # 7. Explicit Public Sync Endpoint
        res_sync = await client.post(f"/api/v1/local-seo/reviews/{proj1.id}/public-sync", headers=h1)
        assert res_sync.status_code == 200
        assert res_sync.json()["status"] == "found"
        assert len(res_sync.json()["reviews"]) == 5

        # 8. Server-Side Multi-Tenant Authorization Checks
        # User 2 attempting to access Project 1's reviews -> Rejection (403 or 404)
        res_unauth = await client.get(f"/api/v1/local-seo/reviews/{proj1.id}", headers=h2)
        assert res_unauth.status_code in [403, 404]

        # User 2 attempting to sync Project 1's reviews -> Rejection (403 or 404)
        res_sync_unauth = await client.post(f"/api/v1/local-seo/reviews/{proj1.id}/public-sync", headers=h2)
        assert res_sync_unauth.status_code in [403, 404]

        # User 2 attempting to select place for Project 1 -> Rejection (403 or 404)
        res_select_unauth = await client.post(
            "/api/v1/local-seo/places/select",
            headers=h2,
            json={"project_id": proj1.id, "place_id": "ChIJ_test_unauth"}
        )
        assert res_select_unauth.status_code in [403, 404]
