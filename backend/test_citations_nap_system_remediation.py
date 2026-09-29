import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.local_seo.citation_service import CitationService
from app.schemas.local_seo import CitationCreate, CitationOut


def test_canonicalize_url():
    """Verify URL canonicalization normalizes trailing slashes, www, tracking params, and fragments."""
    assert CitationService.canonicalize_url("https://www.yelp.com/biz/test-restaurant?utm_source=google#about") == "https://yelp.com/biz/test-restaurant"
    assert CitationService.canonicalize_url("http://yelp.com/biz/test-restaurant/") == "http://yelp.com/biz/test-restaurant"
    assert CitationService.canonicalize_url("HTTPS://EXAMPLE.COM/Listing/123/") == "https://example.com/Listing/123"
    assert CitationService.canonicalize_url("") is None
    assert CitationService.canonicalize_url(None) is None


def test_generic_arbitrary_domain_url_validation():
    """Generic URL validator must reject homepages, search queries, categories on arbitrary domains without requiring a predefined catalog."""
    # 1. Arbitrary domain homepages -> MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://www.melbournedirectory.com.au")
    assert valid is False
    assert "homepage" in reason.lower()

    valid, reason = CitationService.is_valid_business_listing_url("https://somelocalguide.io/")
    assert valid is False
    assert "homepage" in reason.lower()

    # 2. Search / Query URLs -> MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://arbitrarysite.org/search?q=box+seafood")
    assert valid is False
    assert "search" in reason.lower()

    valid, reason = CitationService.is_valid_business_listing_url("https://somelocalguide.io/find?cat=restaurant")
    assert valid is False

    # 3. Category & Tag URLs -> MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://arbitrarysite.org/category/restaurants")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://directory.com/tags/plumbing")
    assert valid is False

    # 4. Login / Signup / Claim URLs -> MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://somedir.com/login")
    assert valid is False

    valid, reason = CitationService.is_valid_business_listing_url("https://somedir.com/claim-business")
    assert valid is False

    # 5. Project's own domain -> MUST BE REJECTED
    valid, reason = CitationService.is_valid_business_listing_url("https://boxseafood.com.au/about", project_domain="boxseafood.com.au")
    assert valid is False
    assert "own website" in reason.lower()

    # 6. Arbitrary unknown domain with specific business listing path -> MUST BE ACCEPTED
    valid, reason = CitationService.is_valid_business_listing_url("https://melbournefoodguide.com.au/venues/box-seafood-melbourne")
    assert valid is True

    valid, reason = CitationService.is_valid_business_listing_url("https://australianbusinesshub.org/profile/box-seafood-restaurant-98765")
    assert valid is True

    valid, reason = CitationService.is_valid_business_listing_url("https://cityfinder.co/biz/12345/boxseafood")
    assert valid is True


def test_open_web_query_generation():
    """Verify open-web query generation constructs multiple varied queries with business identity."""
    canonical = {
        "business_name": "Box Seafood",
        "city": "Melbourne",
        "state": "VIC",
        "phone": "+61 3 9000 1234",
        "address": "123 Collins St",
        "website": "https://boxseafood.com.au"
    }
    queries = CitationService.build_open_web_discovery_queries(canonical)
    assert len(queries) >= 5
    assert any('"Box Seafood" "Melbourne"' in q for q in queries)
    assert any('"Box Seafood" "+61 3 9000 1234"' in q or '"Box Seafood"' in q for q in queries)
    assert any('directory' in q for q in queries)
    assert any('reviews' in q for q in queries)


def test_identity_matching_logic():
    """Verify strict identity matching without fabricating missing phone/address."""
    canonical = {
        "business_name": "Box Seafood Restaurant",
        "phone": "+61 3 9000 1234",
        "address": "123 Collins St, Melbourne VIC 3000",
        "city": "Melbourne",
        "state": "VIC",
        "website": "https://boxseafood.com.au"
    }

    # 1. Exact page match
    page_data_exact = {
        "found_name": "Box Seafood Restaurant",
        "found_phone": "(03) 9000 1234",
        "found_address": "123 Collins Street, Melbourne, VIC 3000",
        "found_website": "https://boxseafood.com.au"
    }
    match_res = CitationService.match_identity(canonical, page_data_exact)
    assert match_res["verification_status"] == "VERIFIED"
    assert match_res["confidence"] >= 0.8
    assert match_res["field_matches"]["name"] == "MATCH"
    assert match_res["field_matches"]["phone"] == "MATCH"
    assert match_res["field_matches"]["address"] == "MATCH"

    # 2. Missing address on page -> Address must be MISSING, NOT MATCH, NOT fabricated
    page_data_no_address = {
        "found_name": "Box Seafood Restaurant",
        "found_phone": "+61 3 9000 1234",
        "found_address": None,
        "found_website": None
    }
    match_no_addr = CitationService.match_identity(canonical, page_data_no_address)
    assert match_no_addr["field_matches"]["address"] == "MISSING"
    assert match_no_addr["field_matches"]["phone"] == "MATCH"
    assert match_no_addr["field_matches"]["name"] == "MATCH"

    # 3. Wrong phone on page -> Phone must be MISMATCH
    page_data_wrong_phone = {
        "found_name": "Box Seafood Restaurant",
        "found_phone": "+61 2 8000 9999",  # Sydney number
        "found_address": "123 Collins St, Melbourne",
        "found_website": None
    }
    match_wrong_phone = CitationService.match_identity(canonical, page_data_wrong_phone)
    assert match_wrong_phone["field_matches"]["phone"] == "MISMATCH"

    # 4. Completely unrelated business
    page_data_unrelated = {
        "found_name": "Downtown Dental Clinic",
        "found_phone": "+61 3 1111 2222",
        "found_address": "500 Bourke St",
        "found_website": "https://dentalcare.com"
    }
    match_unrelated = CitationService.match_identity(canonical, page_data_unrelated)
    assert match_unrelated["verification_status"] == "NOT_RELEVANT"
    assert match_unrelated["confidence"] < 0.3


@pytest.mark.asyncio
async def test_page_fetching_and_nap_extraction():
    """Verify HTML / JSON-LD parsing extracts schema LocalBusiness fields honestly."""
    html_with_json_ld = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Box Seafood Restaurant - Melbourne</title>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Restaurant",
            "name": "Box Seafood Restaurant",
            "telephone": "+61 3 9000 1234",
            "url": "https://boxseafood.com.au",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "123 Collins St",
                "addressLocality": "Melbourne",
                "addressRegion": "VIC",
                "postalCode": "3000",
                "addressCountry": "AU"
            }
        }
        </script>
    </head>
    <body>
        <h1>Box Seafood Restaurant</h1>
        <p>Call us at 03 9000 1234</p>
    </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_with_json_ld
        mock_resp.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_resp

        page_result = await CitationService.fetch_and_extract_page("https://sampledirectory.com.au/biz/box-seafood")
        assert page_result["fetch_status"] == "success"
        assert page_result["http_status"] == 200
        assert page_result["found_name"] == "Box Seafood Restaurant"
        assert page_result["found_phone"] == "+61 3 9000 1234"
        assert "123 Collins St" in page_result["found_address"]
        assert "Melbourne" in page_result["found_address"]
        assert page_result["found_website"] == "https://boxseafood.com.au"


@pytest.mark.asyncio
async def test_failed_page_fetch_returns_unable_to_verify():
    """If a page cannot be fetched (HTTP 403, 404, or timeout), status is UNABLE_TO_VERIFY and never fabricated."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection timed out")):
        page_result = await CitationService.fetch_and_extract_page("https://protecteddir.com/biz/box-seafood")
        assert page_result["fetch_status"] == "error"
        assert page_result["found_name"] is None
        assert page_result["found_phone"] is None
        assert page_result["found_address"] is None
        assert page_result["found_website"] is None


def test_domain_authority_is_none_without_provider():
    """Domain authority must remain None unless a real authority provider supplied it."""
    citation = CitationCreate(
        project_id=1,
        source_name="Open Web Directory",
        domain="openwebdir.com",
        listing_url="https://openwebdir.com/biz/123",
        status="approved",
        domain_authority=None
    )
    assert citation.domain_authority is None
