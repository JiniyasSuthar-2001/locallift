import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.services.google.oauth import GoogleOAuthService

logger = logging.getLogger("locallift.google.gbp_client")

class GoogleBusinessProfileClient:
    ACCOUNT_MGMT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
    BUSINESS_INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
    PERFORMANCE_API = "https://businessprofileperformance.googleapis.com/v1"

    def __init__(self, access_token: str, refresh_token: Optional[str] = None, token_expiry: Optional[datetime] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = token_expiry
        self.token_refreshed = False

    async def ensure_valid_token(self) -> str:
        """
        Checks if current access token is expired or about to expire (within 5 mins).
        Refreshes it automatically if a refresh token is present.
        """
        now = datetime.now(timezone.utc)
        is_expired = False

        if self.token_expiry:
            # Make sure timezone-aware comparison
            expiry = self.token_expiry if self.token_expiry.tzinfo else self.token_expiry.replace(tzinfo=timezone.utc)
            if now >= expiry - timedelta(minutes=5):
                is_expired = True
        
        if is_expired and self.refresh_token:
            logger.info("Google access token expired or expiring soon. Refreshing...")
            try:
                refresh_res = await GoogleOAuthService.refresh_access_token(self.refresh_token)
                self.access_token = refresh_res["access_token"]
                self.token_expiry = refresh_res["token_expiry"]
                self.token_refreshed = True
                logger.info("Google access token refreshed successfully.")
            except Exception as e:
                logger.error(f"Failed to auto-refresh Google access token: {e}")
                raise

        return self.access_token

    async def list_accounts(self) -> List[Dict[str, Any]]:
        """
        Retrieves all GBP accounts the user has access to.
        Endpoint: GET https://mybusinessaccountmanagement.googleapis.com/v1/accounts
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{self.ACCOUNT_MGMT_API}/accounts", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("accounts", [])
            else:
                logger.error(f"Failed to list GBP accounts: {resp.status_code} - {resp.text}")
                return []

    async def list_locations(self, account_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all locations under a specific GBP account.
        Endpoint: GET https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        read_mask = "name,title,storefrontAddress,phoneNumbers,websiteUri,regularHours,categories,serviceArea,profile"

        params = {
            "readMask": read_mask,
            "pageSize": 100
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            url = f"{self.BUSINESS_INFO_API}/{account_name}/locations"
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("locations", [])
            else:
                logger.error(f"Failed to list GBP locations for {account_name}: {resp.status_code} - {resp.text}")
                return []

    async def fetch_location_performance(self, location_resource_name: str) -> Dict[str, int]:
        """
        Retrieves recent 30-day performance impressions, clicks, calls, and direction requests.
        Endpoint: GET https://businessprofileperformance.googleapis.com/v1/{location_resource_name}:fetchMultiDailyMetricsTimeSeries
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Daily metrics to request
        metrics = [
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
            "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
            "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
            "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
            "CALL_CLICKS",
            "WEBSITE_CLICKS",
            "BUSINESS_DIRECTION_REQUESTS"
        ]

        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=30)

        params = {
            "dailyMetrics": metrics,
            "dailyRange.startDate.year": start_date.year,
            "dailyRange.startDate.month": start_date.month,
            "dailyRange.startDate.day": start_date.day,
            "dailyRange.endDate.year": now.year,
            "dailyRange.endDate.month": now.month,
            "dailyRange.endDate.day": now.day
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.PERFORMANCE_API}/{location_resource_name}:fetchMultiDailyMetricsTimeSeries"
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return self._aggregate_performance_metrics(data)
        except Exception as e:
            logger.warning(f"Could not fetch GBP performance metrics for {location_resource_name}: {e}")

        return {
            "search_impressions": 0,
            "maps_impressions": 0,
            "call_clicks": 0,
            "website_clicks": 0,
            "direction_requests": 0
        }

    def _aggregate_performance_metrics(self, data: Dict[str, Any]) -> Dict[str, int]:
        aggregated = {
            "search_impressions": 0,
            "maps_impressions": 0,
            "call_clicks": 0,
            "website_clicks": 0,
            "direction_requests": 0
        }

        time_series = data.get("multiDailyMetricTimeSeries", [])
        for series in time_series:
            metric_type = series.get("dailyMetricTimeSeries", {}).get("dailyMetric", "")
            daily_values = series.get("dailyMetricTimeSeries", {}).get("timeSeries", {}).get("datedValues", [])
            total_val = sum(int(v.get("value", 0)) for v in daily_values if "value" in v)

            if "SEARCH" in metric_type:
                aggregated["search_impressions"] += total_val
            elif "MAPS" in metric_type:
                aggregated["maps_impressions"] += total_val
            elif metric_type == "CALL_CLICKS":
                aggregated["call_clicks"] += total_val
            elif metric_type == "WEBSITE_CLICKS":
                aggregated["website_clicks"] += total_val
            elif metric_type == "BUSINESS_DIRECTION_REQUESTS":
                aggregated["direction_requests"] += total_val

        return aggregated

    @staticmethod
    def parse_storefront_address(addr_dict: Optional[Dict[str, Any]]) -> str:
        if not addr_dict:
            return ""
        lines = addr_dict.get("addressLines", [])
        locality = addr_dict.get("locality", "")
        admin_area = addr_dict.get("administrativeArea", "")
        postal_code = addr_dict.get("postalCode", "")

        parts = []
        if lines:
            parts.append(", ".join(lines))
        if locality:
            parts.append(locality)
        if admin_area:
            parts.append(admin_area)
        if postal_code:
            parts.append(postal_code)

        return ", ".join(parts)
