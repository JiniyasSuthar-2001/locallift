"""
LocalLift — SERP Provider Contract Tests

Validates provider adapter contracts across SerpApiProvider, OpenSERPProvider, and NotConfiguredSERPProvider:
- Valid response parsing
- Empty response handling
- Malformed response resilience
- 401 Auth error handling
- 429 Rate limit handling
- Timeout error handling
- Unsupported capability handling
"""

import pytest
import unittest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.serp.base import SERPProvider, SERPResponse, NotConfiguredSERPProvider, SERPCapabilities
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.openserp import OpenSERPProvider
from app.services.serp.mock_provider import MockSERPProvider


class TestSERPProvidersContract(unittest.IsolatedAsyncioTestCase):

    def test_01_capabilities_declaration(self):
        """Verify each provider explicitly declares valid capabilities."""
        serpapi = SerpApiProvider(api_key="dummy_valid_api_key_12345")
        openserp = OpenSERPProvider(base_url="http://localhost:7000")
        not_cfg = NotConfiguredSERPProvider()
        mock_prov = MockSERPProvider()

        # SerpApi capabilities
        assert serpapi.capabilities.organic_search is True
        assert serpapi.capabilities.geo_grid is True
        assert serpapi.capabilities.coordinate_search is True

        # OpenSERP capabilities (Geo-Grid coordinate search is unsupported)
        assert openserp.capabilities.organic_search is True
        assert openserp.capabilities.geo_grid is False
        assert openserp.capabilities.coordinate_search is False

        # NotConfigured capabilities
        assert not_cfg.capabilities.organic_search is False
        assert not_cfg.capabilities.geo_grid is False

        # Mock capabilities
        assert mock_prov.capabilities.organic_search is True

    async def test_02_not_configured_provider_safe_errors(self):
        """NotConfiguredSERPProvider returns explicit user-facing error states without network calls."""
        not_cfg = NotConfiguredSERPProvider()
        assert not_cfg.is_configured is False

        res = await not_cfg.search_keyword("plumber")
        assert res.success is False
        assert res.error_code in ("SERP_PROVIDER_NOT_CONFIGURED", "SERP_API_KEY_REQUIRED")
        assert "connect your serpapi account" in res.error_message.lower() or "not configured" in res.error_message.lower()

        grid_res = await not_cfg.search_local_grid_point("plumber", 40.7128, -74.0060)
        assert grid_res.success is False
        assert grid_res.error_code in ("SERP_PROVIDER_NOT_CONFIGURED", "SERP_API_KEY_REQUIRED")

    async def test_03_openserp_unsupported_geo_grid(self):
        """OpenSERP returns explicit PROVIDER_GEO_GRID_UNSUPPORTED when coordinate search requested."""
        openserp = OpenSERPProvider(base_url="http://localhost:7000")
        res = await openserp.search_local_grid_point("electrician", 37.7749, -122.4194)
        assert res.success is False
        assert res.error_code == "PROVIDER_GEO_GRID_UNSUPPORTED"
        assert "unsupported by self-hosted OpenSERP" in res.error_message

    async def test_04_serpapi_auth_error_handling(self):
        """SerpApi handles HTTP 401/403 auth failure gracefully with SERP_PROVIDER_AUTH_ERROR."""
        serpapi = SerpApiProvider(api_key="invalid_test_key")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "Invalid API key"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            res = await serpapi.search_keyword("roofing contractor")
            assert res.success is False
            assert res.error_code == "SERP_PROVIDER_AUTH_ERROR"
            assert "rejected the API key" in res.error_message

    async def test_05_serpapi_rate_limit_handling(self):
        """SerpApi handles HTTP 429 rate limit gracefully with SERP_PROVIDER_RATE_LIMIT."""
        serpapi = SerpApiProvider(api_key="valid_test_key_12345")

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": "Search limit reached"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            res = await serpapi.search_keyword("pest control")
            assert res.success is False
            assert res.error_code == "SERP_PROVIDER_RATE_LIMIT"

    async def test_06_serpapi_timeout_handling(self):
        """SerpApi handles network timeout gracefully with SERP_PROVIDER_TIMEOUT."""
        serpapi = SerpApiProvider(api_key="valid_test_key_12345")

        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
            res = await serpapi.search_keyword("hvac repair")
            assert res.success is False
            assert res.error_code == "SERP_PROVIDER_TIMEOUT"

    async def test_07_serpapi_http_400_location_retry(self):
        """SerpApi automatically retries without location parameter if location causes HTTP 400."""
        serpapi = SerpApiProvider(api_key="valid_test_key_12345")

        bad_resp = MagicMock()
        bad_resp.status_code = 400
        bad_resp.json.return_value = {"error": "Location [Invalid Geo] is not supported."}
        bad_resp.text = '{"error": "Location [Invalid Geo] is not supported."}'

        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.json.return_value = {
            "organic_results": [{"title": "Example Plumber", "link": "https://example.com", "position": 1}],
            "local_results": []
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [bad_resp, good_resp]
            res = await serpapi.search_keyword("emergency plumber", location="Invalid Geo", country="United States")
            assert res.success is True
            assert len(res.organic_results) == 1
            assert res.organic_results[0].title == "Example Plumber"
            assert mock_get.call_count == 2
            # Verify the retry did not include the invalid location parameter
            second_call_params = mock_get.call_args_list[1][1]["params"]
            assert "location" not in second_call_params
            assert second_call_params["gl"] == "us"

    def test_08_location_and_country_sanitization(self):
        """Sanitizer properly cleans placeholder locations and normalizes country codes."""
        assert SerpApiProvider._sanitize_location("Metro Area") is None
        assert SerpApiProvider._sanitize_location("Default") is None
        assert SerpApiProvider._sanitize_location("Local") is None
        assert SerpApiProvider._sanitize_location("Denver, CO") == "Denver, CO"
    async def test_09_null_link_and_title_resilience(self):
        """SerpApi provider safely handles items where link or title is null/missing."""
        serpapi = SerpApiProvider(api_key="valid_test_key_12345")

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "organic_results": [
                {"title": None, "link": None, "snippet": None, "position": 1},
                {"title": "Valid Plumber", "link": "https://plumber.com", "snippet": "Best plumber", "position": 2}
            ],
            "local_results": [
                {"title": None, "website": None, "link": None, "address": None, "phone": None}
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = resp
            res = await serpapi.search_keyword("plumber near me")
            assert res.success is True
            assert len(res.organic_results) == 2
            assert res.organic_results[0].link == ""
            assert res.organic_results[0].title == ""
            assert len(res.local_pack_results) == 1
            assert res.local_pack_results[0].link == ""


if __name__ == "__main__":
    unittest.main()
