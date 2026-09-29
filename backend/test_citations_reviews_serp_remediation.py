import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.serp.location_canonicalizer import LocationCanonicalizer
from app.services.local_seo.citation_service import CitationService
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.schemas.gbp import ProductsServicesResponseOut
from app.schemas.local_seo import ReviewOut, CitationCreate


def test_location_canonicalizer():
    # Australian state canonicalization
    assert LocationCanonicalizer.canonicalize("Melbourne, VIC") == "Melbourne,Victoria,Australia"
    assert LocationCanonicalizer.canonicalize("Sydney, NSW") == "Sydney,New South Wales,Australia"
    assert LocationCanonicalizer.canonicalize("Brisbane, QLD") == "Brisbane,Queensland,Australia"
    assert LocationCanonicalizer.canonicalize("Perth, WA", country="au") == "Perth,Western Australia,Australia"
    
    # US state canonicalization
    assert LocationCanonicalizer.canonicalize("Austin, TX") == "Austin,Texas,United States"
    assert LocationCanonicalizer.canonicalize("Miami, FL") == "Miami,Florida,United States"
    assert LocationCanonicalizer.canonicalize("Seattle, WA", country="us") == "Seattle,Washington,United States"
    
    # Already formatted / clean locations
    assert LocationCanonicalizer.canonicalize("Melbourne, Victoria, Australia", country="au") == "Melbourne,Victoria,Australia"
    
    # Empty / None
    assert LocationCanonicalizer.canonicalize("") is None
    assert LocationCanonicalizer.canonicalize(None) is None


def test_citation_url_validation():
    # Root domains MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://www.yelp.com.au", "yelp.com.au")
    assert valid is False
    assert "homepage" in reason

    valid, reason = CitationService.is_valid_business_listing_url("https://www.yelp.com.au/", "yelp.com.au")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://yellowpages.com.au", "yellowpages.com.au")
    assert valid is False
    
    # Search / Query / Category URLs MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://www.yelp.com.au/search?find_desc=boxseefood", "yelp.com.au")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://www.yelp.com.au/search", "yelp.com.au")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://yellowpages.com.au/search/results?q=plumber", "yellowpages.com.au")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://www.hotfrog.com.au/search/melbourne", "hotfrog.com.au")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://www.yelp.com.au/c/melbourne/restaurants", "yelp.com.au")
    assert valid is False
    
    # Domain mismatch MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://randomsite.com/biz/boxseefood", "yelp.com.au")
    assert valid is False
    
    # Valid business-specific URLs MUST BE ACCEPTED
    valid, _ = CitationService.is_valid_business_listing_url("https://www.yelp.com.au/biz/boxseefood-melbourne", "yelp.com.au")
    assert valid is True

    valid, _ = CitationService.is_valid_business_listing_url("https://www.yellowpages.com.au/vic/melbourne/boxseefood-12345-service.html", "yellowpages.com.au")
    assert valid is True

    valid, _ = CitationService.is_valid_business_listing_url("https://www.truelocal.com.au/business/boxseefood/melbourne", "truelocal.com.au")
    assert valid is True

    valid, _ = CitationService.is_valid_business_listing_url("https://www.hotfrog.com.au/company/10928374/boxseefood/melbourne", "hotfrog.com.au")
    assert valid is True

    valid, _ = CitationService.is_valid_business_listing_url("https://facebook.com/boxseefoodrestaurant", "facebook.com")
    assert valid is True


def test_citation_verification_from_serp_item():
    canonical = {
        "business_name": "Boxseefood Restaurant",
        "website": "https://boxseefood.com.au",
        "phone": "+61 3 9000 1234",
        "address": "123 Collins St",
        "city": "Melbourne",
        "state": "VIC",
        "country": "Australia"
    }
    
    # 1. Matching business result with valid listing URL
    serp_item = {
        "title": "Boxseefood Restaurant - Melbourne, VIC - Yelp",
        "link": "https://www.yelp.com.au/biz/boxseefood-melbourne",
        "snippet": "Boxseefood Restaurant in 123 Collins St, Melbourne. Call +61 3 9000 1234 for reservations.",
        "position": 1
    }
    
    ver = CitationService.verify_citation_from_serp_item(
        serp_item=serp_item,
        expected_domain="yelp.com.au",
        canonical_identity=canonical,
        search_query='"Boxseefood Restaurant" "Melbourne" site:yelp.com.au'
    )
    
    assert ver["verified"] is True
    assert ver["status"] == "listed"
    assert ver["listing_url"] == "https://www.yelp.com.au/biz/boxseefood-melbourne"
    assert ver["verification_status"] in ["OBSERVED", "VERIFIED"]
    assert ver["confidence"] > 0.5
    assert ver["nap_status"] in ["consistent", "not_checked"]
    
    # 2. Generic Yelp homepage returned in SERP -> MUST NOT be marked verified
    homepage_item = {
        "title": "Yelp Australia - Restaurants, Dentists, Bars, Beauty Salons",
        "link": "https://www.yelp.com.au",
        "snippet": "Find the best businesses in Australia on Yelp.",
        "position": 1
    }
    
    ver_home = CitationService.verify_citation_from_serp_item(
        serp_item=homepage_item,
        expected_domain="yelp.com.au",
        canonical_identity=canonical,
        search_query='"Boxseefood Restaurant" "Melbourne" site:yelp.com.au'
    )
    
    assert ver_home["verified"] is False
    assert ver_home["status"] == "missing"
    assert ver_home["listing_url"] is None
    assert ver_home["verification_status"] == "NOT_VERIFIED"


def test_missing_citation_semantics():
    """Missing citation must have status MISSING and nap_status not_checked, NOT mismatch."""
    missing = CitationCreate(
        project_id=1,
        source_name="Yelp",
        domain="yelp.com.au",
        listing_url=None,
        status="MISSING",
        nap_status="not_checked",
        verification_status="NOT_VERIFIED"
    )
    assert missing.status == "MISSING"
    assert missing.nap_status == "not_checked"
    assert missing.listing_url is None


@pytest.mark.asyncio
async def test_gbp_client_reviews_star_rating_unspecified():
    """Ensure unspecified star ratings do not fabricate 5 stars."""
    client = GoogleBusinessProfileClient(access_token="fake_token")
    
    mock_reviews_data = {
        "reviews": [
            {
                "reviewer": {"displayName": "Jane Doe"},
                "starRating": "STAR_RATING_UNSPECIFIED",
                "comment": "Had an experience.",
                "createTime": "2026-09-20T10:00:00Z"
            },
            {
                "reviewer": {"displayName": "John Smith"},
                "starRating": "FIVE",
                "comment": "Outstanding food and service!",
                "createTime": "2026-09-21T10:00:00Z"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_reviews_data
        mock_get.return_value = mock_resp
        
        res = await client.fetch_location_reviews("accounts/123", "locations/456")
        assert res["success"] is True
        reviews = res["reviews"]
        assert len(reviews) == 2
        # First review: STAR_RATING_UNSPECIFIED -> rating must be None (not 5)
        assert reviews[0]["rating"] is None
        # Second review: FIVE -> rating must be 5
        assert reviews[1]["rating"] == 5


def test_products_services_truthful_sync_response():
    """Ensure ProductsServicesResponseOut honestly reflects sync capabilities without false success."""
    resp = ProductsServicesResponseOut(
        business_name="Boxseefood",
        place_id="ChIJ123456",
        is_connected=True,
        connected_account="owner@boxseefood.com.au",
        total_products=0,
        total_services=0,
        last_synced_at="2026-09-26T12:00:00Z",
        sync_status="NOT_AVAILABLE",
        sync_message="Product/service catalog sync is not available through the connected Google API. Items are maintained in LocalLift catalog.",
        can_sync=False,
        items=[]
    )
    assert resp.sync_status == "NOT_AVAILABLE"
    assert resp.can_sync is False
    assert "not available through the connected Google API" in resp.sync_message


def test_business_profile_canonical_fields_compatibility():
    """Verify BusinessProfile model attributes and canonical_identity dict mapping."""
    from app.models.local_seo import BusinessProfile
    
    profile = BusinessProfile(
        project_id=1,
        business_name="Boxseefood Restaurant",
        website="https://boxseefood.com.au",
        primary_phone="+61 3 9000 1234",
        primary_address="123 Collins St",
        city="Melbourne",
        state="VIC",
        country="Australia"
    )
    
    canonical_identity = {
        "business_name": (profile.business_name if profile and profile.business_name else None) or "Default",
        "city": (profile.city if profile and profile.city else "") or "",
        "state": (profile.state if profile and profile.state else "") or "",
        "phone": (profile.primary_phone if profile and profile.primary_phone else "") or "",
        "address": (profile.primary_address if profile and profile.primary_address else "") or "",
        "country": (profile.country if profile and profile.country else "") or "US",
        "website": (profile.website if profile and profile.website else "") or ""
    }
    
    assert canonical_identity["business_name"] == "Boxseefood Restaurant"
    assert canonical_identity["phone"] == "+61 3 9000 1234"
    assert canonical_identity["address"] == "123 Collins St"
    assert canonical_identity["website"] == "https://boxseefood.com.au"
    assert canonical_identity["city"] == "Melbourne"
    assert canonical_identity["state"] == "VIC"
    assert canonical_identity["country"] == "Australia"

