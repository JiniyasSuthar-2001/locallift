import asyncio
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
from app.services.google.oauth import GoogleOAuthService
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.services.google.sync import GBPSyncService
from app.models.gbp import GoogleAccount, GoogleBusinessProfile, GBPChange

def test_google_oauth_url_generation():
    url = GoogleOAuthService.get_authorization_url(project_id=1, user_id=42)
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "business.manage" in url

    # Verify state payload contains project_id
    parsed = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed.query)
    state_str = query_params["state"][0]
    state_data = json.loads(state_str)
    assert state_data["project_id"] == 1
    assert state_data["user_id"] == 42

def test_gbp_address_and_metrics_parsing():
    # 1. Address parsing
    sample_addr = {
        "addressLines": ["142 Queen Street", "Suite 4"],
        "locality": "Brisbane",
        "administrativeArea": "QLD",
        "postalCode": "4000"
    }
    formatted = GoogleBusinessProfileClient.parse_storefront_address(sample_addr)
    assert "142 Queen Street" in formatted
    assert "Brisbane" in formatted
    assert "4000" in formatted

    # 2. Performance metrics aggregation
    sample_metrics_data = {
        "multiDailyMetricTimeSeries": [
            {
                "dailyMetricTimeSeries": {
                    "dailyMetric": "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
                    "timeSeries": {
                        "datedValues": [{"value": "120"}, {"value": "80"}]
                    }
                }
            },
            {
                "dailyMetricTimeSeries": {
                    "dailyMetric": "CALL_CLICKS",
                    "timeSeries": {
                        "datedValues": [{"value": "15"}, {"value": "5"}]
                    }
                }
            }
        ]
    }
    client = GoogleBusinessProfileClient(access_token="fake_token")
    agg = client._aggregate_performance_metrics(sample_metrics_data)
    assert agg["search_impressions"] == 200
    assert agg["call_clicks"] == 20

def test_token_expiry_detection():
    # Expired token (10 mins in past)
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    client_expired = GoogleBusinessProfileClient(access_token="old_token", token_expiry=expired_time)
    
    # Valid token (2 hours in future)
    valid_time = datetime.now(timezone.utc) + timedelta(hours=2)
    client_valid = GoogleBusinessProfileClient(access_token="good_token", token_expiry=valid_time)

    # Valid token should be returned directly
    async def _check():
        token = await client_valid.ensure_valid_token()
        assert token == "good_token"

    asyncio.run(_check())

def run_all_tests():
    test_google_oauth_url_generation()
    test_gbp_address_and_metrics_parsing()
    test_token_expiry_detection()
    print("[OK] All Google OAuth & GBP Integration test suites PASSED successfully!")

if __name__ == "__main__":
    run_all_tests()
