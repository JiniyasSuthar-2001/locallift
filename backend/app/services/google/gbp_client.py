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

    async def list_accounts(self) -> Dict[str, Any]:
        """
        Retrieves all GBP accounts the user has access to with full pagination.
        Endpoint: GET https://mybusinessaccountmanagement.googleapis.com/v1/accounts
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        all_accounts: List[Dict[str, Any]] = []
        page_token = None

        async with httpx.AsyncClient(timeout=20.0) as client:
            while True:
                params: Dict[str, Any] = {"pageSize": 20}
                if page_token:
                    params["pageToken"] = page_token

                try:
                    resp = await client.get(f"{self.ACCOUNT_MGMT_API}/accounts", headers=headers, params=params)
                except Exception as e:
                    logger.error(f"[GBP_CLIENT] Connection error listing accounts: {e}")
                    return {
                        "accounts": all_accounts,
                        "status": "ERROR",
                        "error": f"Failed to connect to Google Business Profile API: {str(e)}"
                    }

                if resp.status_code == 200:
                    data = resp.json()
                    accounts = data.get("accounts", [])
                    all_accounts.extend(accounts)
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                elif resp.status_code == 429:
                    err_body = resp.text
                    if "quota_limit_value" in err_body or "RATE_LIMIT_EXCEEDED" in err_body or "RESOURCE_EXHAUSTED" in err_body:
                        logger.warning("[GBP_CLIENT] Google Business Profile API access not granted (quota=0) for GCP project.")
                        return {
                            "accounts": all_accounts,
                            "status": "API_ACCESS_NOT_GRANTED",
                            "error": "Google Business Profile API access has not been granted (quota=0). Request API access in Google Cloud Console."
                        }
                    else:
                        logger.warning(f"[GBP_CLIENT] Google Business Profile rate limited: 429 - {err_body[:120]}")
                        return {
                            "accounts": all_accounts,
                            "status": "RATE_LIMITED",
                            "error": "Google Business Profile API rate limit exceeded. Please try again in a few minutes."
                        }
                elif resp.status_code == 401:
                    logger.warning("[GBP_CLIENT] Google authorization token expired or revoked (401).")
                    return {
                        "accounts": all_accounts,
                        "status": "AUTH_EXPIRED",
                        "error": "Google authorization token is expired or revoked. Reconnect Google Business Profile."
                    }
                elif resp.status_code == 403:
                    logger.warning(f"[GBP_CLIENT] Permission denied: 403 - {resp.text[:120]}")
                    return {
                        "accounts": all_accounts,
                        "status": "PERMISSION_DENIED",
                        "error": "Permission denied by Google Business Profile API. Ensure your Google account has Business Profile management permissions."
                    }
                else:
                    logger.error(f"Failed to list GBP accounts: {resp.status_code} - {resp.text[:120]}")
                    return {
                        "accounts": all_accounts,
                        "status": "ERROR",
                        "error": f"Google API error: HTTP {resp.status_code} - {resp.text[:120]}"
                    }

        if not all_accounts:
            return {
                "accounts": [],
                "status": "NO_BUSINESS_PROFILES",
                "error": "No Google Business Profile accounts found for this Google user."
            }

        return {
            "accounts": all_accounts,
            "status": "CONNECTED",
            "error": None
        }

    async def list_locations(self, account_name: str) -> Dict[str, Any]:
        """
        Retrieves all locations under a specific GBP account with full pagination.
        Handles 1, 3, 20, 40+ locations across multiple pages.
        Endpoint: GET https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        read_mask = "name,title,storefrontAddress,phoneNumbers,websiteUri,regularHours,specialHours,categories,serviceArea,profile,latlng,metadata"
        all_locations: List[Dict[str, Any]] = []
        page_token = None

        async with httpx.AsyncClient(timeout=25.0) as client:
            url = f"{self.BUSINESS_INFO_API}/{account_name}/locations"
            while True:
                params: Dict[str, Any] = {
                    "readMask": read_mask,
                    "pageSize": 100
                }
                if page_token:
                    params["pageToken"] = page_token

                try:
                    resp = await client.get(url, headers=headers, params=params)
                except Exception as e:
                    logger.error(f"[GBP_CLIENT] Connection error listing locations for {account_name}: {e}")
                    return {
                        "locations": all_locations,
                        "status": "ERROR",
                        "error": f"Failed to connect to Google Business Information API: {str(e)}"
                    }

                if resp.status_code == 200:
                    data = resp.json()
                    locations = data.get("locations", [])
                    all_locations.extend(locations)
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                elif resp.status_code == 429:
                    err_body = resp.text
                    if "quota_limit_value" in err_body or "RATE_LIMIT_EXCEEDED" in err_body or "RESOURCE_EXHAUSTED" in err_body:
                        logger.warning("[GBP_CLIENT] Google Business Profile API access not granted (quota=0) for GCP project.")
                        return {
                            "locations": all_locations,
                            "status": "API_ACCESS_NOT_GRANTED",
                            "error": "Google Business Profile API access has not been granted (quota=0). Request API access in Google Cloud Console."
                        }
                    else:
                        logger.warning(f"[GBP_CLIENT] Google Business Profile rate limited: 429 - {err_body[:120]}")
                        return {
                            "locations": all_locations,
                            "status": "RATE_LIMITED",
                            "error": "Google Business Profile API rate limit exceeded."
                        }
                elif resp.status_code == 401:
                    return {
                        "locations": all_locations,
                        "status": "AUTH_EXPIRED",
                        "error": "Google authorization token is expired or revoked."
                    }
                elif resp.status_code == 403:
                    return {
                        "locations": all_locations,
                        "status": "PERMISSION_DENIED",
                        "error": "Permission denied for this Google Business Profile account."
                    }
                else:
                    logger.error(f"Failed to list GBP locations for {account_name}: {resp.status_code} - {resp.text[:120]}")
                    return {
                        "locations": all_locations,
                        "status": "ERROR",
                        "error": f"Google API error: HTTP {resp.status_code}"
                    }

        return {
            "locations": all_locations,
            "status": "CONNECTED" if all_locations else "NO_LOCATIONS",
            "error": None
        }

    async def fetch_location(self, location_resource_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single location by its exact resource name (e.g. 'locations/12345').
        Endpoint: GET https://mybusinessbusinessinformation.googleapis.com/v1/{location_resource_name}
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        read_mask = "name,title,storefrontAddress,phoneNumbers,websiteUri,regularHours,specialHours,categories,serviceArea,profile,latlng,metadata"

        loc_str = location_resource_name if location_resource_name.startswith("locations/") else f"locations/{location_resource_name}"
        params = {"readMask": read_mask}

        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.BUSINESS_INFO_API}/{loc_str}"
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"[GBP_CLIENT] Failed to fetch single location {location_resource_name}: {resp.status_code}")
                return None

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

    async def fetch_location_reviews(
        self,
        account_id: str,
        location_id: str,
        max_pages: int = 10,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieves owner-authorized customer reviews for a GBP location with real pagination.
        Endpoint: GET https://mybusiness.googleapis.com/v4/{account_id}/{location_id}/reviews
        Paginates until next_page_token is empty or max_pages safety limit is reached.
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}

        acc_str = account_id if account_id.startswith("accounts/") else f"accounts/{account_id}"
        loc_str = location_id.split("/")[-1]

        star_map = {
            "STAR_RATING_UNSPECIFIED": None,
            "ONE": 1,
            "TWO": 2,
            "THREE": 3,
            "FOUR": 4,
            "FIVE": 5
        }

        reviews_list: List[Dict[str, Any]] = []
        next_page_token = None
        pages_fetched = 0

        base_url = f"https://mybusiness.googleapis.com/v4/{acc_str}/locations/{loc_str}/reviews"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                while pages_fetched < max_pages:
                    params: Dict[str, Any] = {"pageSize": page_size}
                    if next_page_token:
                        params["pageToken"] = next_page_token

                    resp = await client.get(base_url, headers=headers, params=params)
                    if resp.status_code != 200:
                        if pages_fetched > 0:
                            # Partial success on earlier pages
                            logger.warning(f"[GBP_REVIEWS] Pagination stopped at page {pages_fetched}: HTTP {resp.status_code}")
                            break
                        logger.warning(f"[GBP_REVIEWS] Reviews endpoint returned status {resp.status_code} for {loc_str}")
                        return {
                            "success": False,
                            "reviews": [],
                            "error": f"Google API returned HTTP {resp.status_code}",
                            "status_code": resp.status_code,
                            "error_type": "google_api_error",
                            "has_more": False,
                            "pages_fetched": pages_fetched
                        }

                    data = resp.json()
                    raw_reviews = data.get("reviews", [])
                    for r in raw_reviews:
                        reviewer = r.get("reviewer", {})
                        author = reviewer.get("displayName") or "Google Customer"
                        avatar = reviewer.get("profilePhotoUrl")
                        rating_raw = r.get("starRating")
                        if rating_raw is not None:
                            rating = star_map.get(rating_raw) if isinstance(rating_raw, str) else int(rating_raw)
                        else:
                            rating = None
                        comment = r.get("comment", "")
                        
                        created_raw = r.get("createTime")
                        try:
                            rev_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00")) if created_raw else datetime.now(timezone.utc)
                        except Exception:
                            rev_dt = datetime.now(timezone.utc)

                        updated_raw = r.get("updateTime")
                        try:
                            up_dt = datetime.fromisoformat(updated_raw.replace("Z", "+00:00")) if updated_raw else None
                        except Exception:
                            up_dt = None

                        reply_obj = r.get("reviewReply", {})
                        reply_comment = reply_obj.get("comment") if reply_obj else None
                        response_status = "published" if reply_comment else "unanswered"

                        raw_rev_id = r.get("reviewId") or r.get("name")
                        ext_id = str(raw_rev_id) if raw_rev_id else None

                        reviews_list.append({
                            "external_review_id": ext_id,
                            "author_name": author,
                            "author_photo_url": avatar,
                            "rating": rating,
                            "review_text": comment,
                            "review_date": rev_dt,
                            "update_time": up_dt,
                            "response_text": reply_comment,
                            "response_status": response_status,
                            "source": "Google Business Profile",
                            "raw_review": r
                        })

                    pages_fetched += 1
                    next_page_token = data.get("nextPageToken")
                    if not next_page_token:
                        break

                return {
                    "success": True,
                    "reviews": reviews_list,
                    "error": None,
                    "status_code": 200,
                    "error_type": None,
                    "has_more": bool(next_page_token),
                    "next_page_token": next_page_token,
                    "pages_fetched": pages_fetched
                }
        except Exception as e:
            logger.warning(f"[GBP_REVIEWS] Failed to query reviews: {e}")
            return {
                "success": False,
                "reviews": reviews_list,
                "error": str(e),
                "status_code": 500,
                "error_type": "network_exception",
                "has_more": False,
                "pages_fetched": pages_fetched
            }

    async def list_categories(
        self,
        query: Optional[str] = None,
        region_code: str = "US",
        language_code: str = "en",
        page_size: int = 50,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Queries Google Business Information Category API for official GBP categories.
        Endpoint: GET https://mybusinessbusinessinformation.googleapis.com/v1/categories
        """
        token = await self.ensure_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        params: Dict[str, Any] = {
            "regionCode": region_code,
            "languageCode": language_code,
            "pageSize": page_size
        }
        if query and query.strip():
            params["searchTerm"] = query.strip()
        if page_token:
            params["pageToken"] = page_token

        url = f"{self.BUSINESS_INFO_API}/categories"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_cats = data.get("categories", [])
                    formatted = []
                    for c in raw_cats:
                        cat_id = c.get("name", "")
                        display_name = c.get("displayName", "")
                        formatted.append({
                            "id": cat_id.replace("categories/", ""),
                            "resource_name": cat_id,
                            "name": display_name,
                            "display_name": display_name,
                            "service_types": [st.get("displayName") for st in c.get("serviceTypes", []) if st.get("displayName")],
                            "more_hours_types": [ht.get("displayName") for ht in c.get("moreHoursTypes", []) if ht.get("displayName")]
                        })
                    return {
                        "success": True,
                        "categories": formatted,
                        "next_page_token": data.get("nextPageToken"),
                        "total": len(formatted)
                    }
                else:
                    logger.warning(f"[GBP_CATEGORIES] Categories API returned HTTP {resp.status_code}: {resp.text[:120]}")
                    return {
                        "success": False,
                        "categories": [],
                        "error": f"Google API error HTTP {resp.status_code}",
                        "status_code": resp.status_code
                    }
        except Exception as e:
            logger.warning(f"[GBP_CATEGORIES] Failed to fetch Google categories: {e}")
            return {
                "success": False,
                "categories": [],
                "error": str(e),
                "status_code": 500
            }
