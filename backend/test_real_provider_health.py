"""
LocalLift — Real SERP Provider Health Test (Optional Live Smoke Test)

Checks whether live SERPAPI_KEY credentials exist in the environment:
- If credentials exist, executes a single lightweight live smoke test.
- If credentials do NOT exist, explicitly reports LIVE PROVIDER TEST NOT RUN.
- NEVER exposes or logs API keys.
"""

import os
import unittest
import pytest

from app.config import settings
from app.services.serp.serpapi import SerpApiProvider


class TestRealSERPProviderHealth(unittest.IsolatedAsyncioTestCase):

    async def test_01_real_provider_health_check(self):
        """Optional live smoke test for SerpApiProvider."""
        key = getattr(settings, "SERPAPI_KEY", "") or os.environ.get("SERPAPI_KEY", "")
        clean_key = (key or "").strip().strip("'\"").strip()

        if not clean_key or len(clean_key) <= 5 or any(c in clean_key for c in ("•", "*")):
            print("\n[SERP_SMOKE_TEST] RESULT: LIVE PROVIDER TEST NOT RUN (SERPAPI_KEY not configured in environment)")
            pytest.skip("LIVE PROVIDER TEST NOT RUN: SERPAPI_KEY not set in environment.")
            return

        print("\n[SERP_SMOKE_TEST] Live credentials detected. Executing live smoke query...")
        provider = SerpApiProvider(api_key=clean_key)
        res = await provider.search_keyword("weather", num_results=1)

        if res.success:
            print("[SERP_SMOKE_TEST] RESULT: LIVE PROVIDER REACHABLE AND WORKING!")
            assert res.success is True
            assert len(res.organic_results) > 0 or len(res.local_pack_results) > 0
        else:
            print(f"[SERP_SMOKE_TEST] RESULT: LIVE PROVIDER QUERY FAILED with code '{res.error_code}': {res.error_message}")
            pytest.fail(f"Live SerpApi test failed: {res.error_message}")


if __name__ == "__main__":
    unittest.main()
