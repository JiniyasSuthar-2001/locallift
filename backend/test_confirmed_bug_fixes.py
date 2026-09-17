import sys
import os
import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.seo_auditor import SEOAuditor
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.services.google.sync import GBPSyncService

class TestConfirmedBugFixes(unittest.TestCase):
    def test_scoring_methodology_source_of_truth(self):
        weights = SEOAuditor.get_pillar_weights_formatted()
        methodology = SEOAuditor.get_scoring_methodology()
        
        self.assertEqual(weights["crawl_health"], "20%")
        self.assertEqual(weights["onpage_content"], "20%")
        self.assertEqual(weights["schema_structured_data"], "25%")
        self.assertEqual(weights["gbp_alignment"], "15%")
        self.assertEqual(weights["citations_nap"], "10%")
        self.assertEqual(weights["reviews_reputation"], "10%")

        total_weight = sum(v["weight_fraction"] for v in methodology.values())
        self.assertAlmostEqual(total_weight, 1.0, places=4)
        self.assertEqual(len(methodology), 6)

    def test_fetch_location_reviews_structured_error_handling(self):
        async def run_test():
            client = GoogleBusinessProfileClient(access_token="fake_token")
            client.ensure_valid_token = AsyncMock(return_value="fake_token")

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 403
                mock_response.text = "Forbidden"
                mock_get.return_value = mock_response

                res = await client.fetch_location_reviews("accounts/123", "locations/456")
                
                self.assertFalse(res["success"])
                self.assertEqual(res["reviews"], [])
                self.assertEqual(res["status_code"], 403)
                self.assertEqual(res["error_type"], "google_api_error")

        asyncio.run(run_test())

    def test_fetch_location_reviews_success(self):
        async def run_test():
            client = GoogleBusinessProfileClient(access_token="fake_token")
            client.ensure_valid_token = AsyncMock(return_value="fake_token")

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "reviews": [
                        {
                            "reviewer": {"displayName": "Jane Doe"},
                            "starRating": "FIVE",
                            "comment": "Great local service!"
                        }
                    ]
                }
                mock_get.return_value = mock_response

                res = await client.fetch_location_reviews("accounts/123", "locations/456")
                
                self.assertTrue(res["success"])
                self.assertEqual(len(res["reviews"]), 1)
                self.assertEqual(res["reviews"][0]["author_name"], "Jane Doe")
                self.assertEqual(res["reviews"][0]["rating"], 5)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
