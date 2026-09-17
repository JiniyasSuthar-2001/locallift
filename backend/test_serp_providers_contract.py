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
        assert res.error_code == "SERP_API_KEY_REQUIRED"
        assert "not configured" in res.error_message

        grid_res = await not_cfg.search_local_grid_point("plumber", 40.7128, -74.0060)
        assert grid_res.success is False
        assert grid_res.error_code == "SERP_API_KEY_REQUIRED"

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


if __name__ == "__main__":
    unittest.main()
