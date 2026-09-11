import asyncio
from app.services.serp.matcher import DomainMatcher
from app.services.serp.base import SERPResponse, SERPItem
from app.services.serp.mock_provider import MockSERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.factory import get_serp_provider

def test_domain_matcher_normalization():
    # 1. Host normalization
    assert DomainMatcher.normalize_host("https://www.queenshineelectricals.com.au/") == "queenshineelectricals.com.au"
    assert DomainMatcher.normalize_host("http://queenshineelectricals.com.au/services/repair") == "queenshineelectricals.com.au"
    assert DomainMatcher.normalize_host("WWW.EXAMPLE.COM:8080/path?query=123") == "example.com"
    assert DomainMatcher.normalize_host("sub.domain.co.uk") == "sub.domain.co.uk"

    # 2. URL normalization
    assert DomainMatcher.normalize_url("https://www.example.com/services/electrician/") == "example.com/services/electrician"
    assert DomainMatcher.normalize_url("http://example.com/services/electrician") == "example.com/services/electrician"

def test_domain_matcher_anti_hijacking():
    target = "queenshineelectricals.com.au"

    # True matches
    assert DomainMatcher.matches_target("https://queenshineelectricals.com.au", target) is True
    assert DomainMatcher.matches_target("https://www.queenshineelectricals.com.au/services", target) is True
    assert DomainMatcher.matches_target("https://emergency.queenshineelectricals.com.au", target) is True

    # False matches (Anti-hijacking checks)
    assert DomainMatcher.matches_target("https://queenshineelectricals.com.au.fakedomain.org", target) is False
    assert DomainMatcher.matches_target("https://other-queenshineelectricals.com.au", target) is False
    assert DomainMatcher.matches_target("https://queenshineelectricals.com.au.phishing.io/login", target) is False
    assert DomainMatcher.matches_target("https://yellowpages.com.au/search?q=queenshineelectricals.com.au", target) is False

def test_serp_rank_lookup_found_and_not_found():
    serp = SERPResponse(
        provider="mock",
        keyword="electrician brisbane",
        organic_results=[
            SERPItem(position=1, title="City Sparks", link="https://citysparks.com.au", domain="citysparks.com.au"),
            SERPItem(position=2, title="Queenshine Electricals", link="https://queenshineelectricals.com.au/services/emergency", domain="queenshineelectricals.com.au"),
            SERPItem(position=3, title="Apex Power", link="https://apexpower.com.au", domain="apexpower.com.au")
        ],
        local_pack_results=[],
        success=True
    )

    # 1. Target found at position 2
    rank, url, serp_type = DomainMatcher.find_rank_in_serp(serp, "queenshineelectricals.com.au")
    assert rank == 2
    assert url == "https://queenshineelectricals.com.au/services/emergency"
    assert serp_type == "Organic"

    # 2. Target NOT found (must explicitly be None, not fabricated)
    nf_rank, nf_url, _ = DomainMatcher.find_rank_in_serp(serp, "unrankedcontractor.com.au")
    assert nf_rank is None
    assert nf_url is None

def test_mock_provider_live_search():
    async def _test():
        # 1. Mock without presets returns clean empty results (never fabricated domains)
        empty_provider = MockSERPProvider()
        empty_resp = await empty_provider.search_keyword("electrician brisbane", location="Brisbane CBD")
        assert empty_resp.success is True
        assert len(empty_resp.organic_results) == 0

        # 2. Mock with explicit test presets returns provided items
        preset = [
            {"position": 1, "title": "Test 1", "link": "https://test1.com"},
            {"position": 2, "title": "Test 2", "link": "https://test2.com"}
        ]
        provider = MockSERPProvider(preset_results=preset)
        resp = await provider.search_keyword("electrician brisbane", location="Brisbane CBD")
        assert resp.success is True
        assert len(resp.organic_results) == 2
        assert resp.organic_results[0].domain == "test1.com"

        # 3. Simulate timeout error
        err_provider = MockSERPProvider(simulate_error="timeout")
        err_resp = await err_provider.search_keyword("test")
        assert err_resp.success is False
        assert err_resp.error_code == "SERP_PROVIDER_TIMEOUT"

    asyncio.run(_test())

def test_unconfigured_provider_safety():
    async def _test():
        # Empty API key
        unconfigured = SerpApiProvider(api_key="")
        assert unconfigured.is_configured is False
        resp = await unconfigured.search_keyword("electrician brisbane")
        assert resp.success is False
        assert resp.error_code == "SERP_PROVIDER_NOT_CONFIGURED"

    asyncio.run(_test())

def run_all_tests():
    test_domain_matcher_normalization()
    test_domain_matcher_anti_hijacking()
    test_serp_rank_lookup_found_and_not_found()
    test_mock_provider_live_search()
    test_unconfigured_provider_safety()
    print("[OK] All SERP Provider & Domain Matcher unit tests PASSED successfully!")

if __name__ == "__main__":
    run_all_tests()
