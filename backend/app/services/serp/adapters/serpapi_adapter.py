import logging
import httpx
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone

from app.services.serp.adapters.base import (
    SERPProviderAdapter,
    SERPCredentialField,
    SERPNormalizedAccountInfo,
    SERPAccountMetadata,
    SERPUsageMetadata,
    SERPRateLimitMetadata,
    SERPUsageModel,
    SERPConnectionStatus
)
from app.services.serp.base import SERPCapabilities, SERPResponse
from app.services.serp.serpapi import SerpApiProvider

logger = logging.getLogger("locallift.serp.adapter.serpapi")


class SerpApiAdapter(SERPProviderAdapter):
    ACCOUNT_ENDPOINT = "https://serpapi.com/account.json"

    @property
    def provider_id(self) -> str:
        return "serpapi"

    @property
    def display_name(self) -> str:
        return "SerpApi"

    @property
    def description(self) -> str:
        return "Authoritative cloud SERP provider with real-time Google Maps, Local Pack, and monthly allowance tracking."

    @property
    def credential_fields(self) -> List[SERPCredentialField]:
        return [
            SERPCredentialField(
                key="api_key",
                label="SerpApi API Key",
                type="password",
                required=True,
                placeholder="Enter your SerpApi private API key",
                help_text="Find your API key in your SerpApi dashboard (serpapi.com/manage-api-key)."
            )
        ]

    @property
    def capabilities(self) -> SERPCapabilities:
        return SERPCapabilities(
            organic_search=True,
            local_search=True,
            maps_search=True,
            coordinate_search=True,
            geo_grid=True,
            maps_reviews=True
        )

    @property
    def supported_billing_models(self) -> List[str]:
        return [SERPUsageModel.MONTHLY_SEARCH_QUOTA.value]

    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        if not api_key:
            return False, "SerpApi API key is required."
        if len(api_key) < 10:
            return False, "SerpApi API key is too short or invalid."

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.ACCOUNT_ENDPOINT, params={"api_key": api_key})
                if res.status_code == 200:
                    data = res.json()
                    plan = data.get("plan_name") or data.get("plan_id") or "Active"
                    return True, f"Connected to SerpApi ({plan} Plan)."
                elif res.status_code in [401, 403]:
                    return False, "Invalid SerpApi API key. Authentication failed."
                else:
                    return False, f"SerpApi returned HTTP {res.status_code}: {res.text[:100]}"
        except httpx.TimeoutException:
            return False, "SerpApi connection timed out after 10 seconds."
        except Exception as e:
            return False, f"SerpApi validation error: {str(e)}"

    async def get_account_info(self, credentials: Dict[str, Any]) -> SERPNormalizedAccountInfo:
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        now_iso = datetime.now(timezone.utc).isoformat()

        if not api_key:
            return SERPNormalizedAccountInfo(
                provider=self.provider_id,
                provider_name=self.display_name,
                connection_status=SERPConnectionStatus.NOT_CONFIGURED.value,
                status_message="API key not configured.",
                capabilities=self.capabilities,
                last_synced_at=now_iso
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.ACCOUNT_ENDPOINT, params={"api_key": api_key})

                if res.status_code == 200:
                    data = res.json()
                    plan_name = data.get("plan_name") or data.get("plan_id") or "Standard Plan"
                    # Handle plan name formatting nicely
                    if isinstance(plan_name, str) and not plan_name.lower().endswith("plan"):
                        plan_display = f"{plan_name.title()} Plan"
                    else:
                        plan_display = str(plan_name).title()

                    monthly_limit = data.get("searches_per_month")
                    used_searches = data.get("this_month_usage", 0)
                    remaining_searches = data.get("total_searches_left")
                    if remaining_searches is None:
                        remaining_searches = data.get("plan_searches_left")

                    pct_used = None
                    if monthly_limit and monthly_limit > 0 and used_searches is not None:
                        pct_used = round((used_searches / monthly_limit) * 100, 1)

                    rate_limit_info = None
                    if data.get("account_rate_limit_per_hour"):
                        rate_limit_info = SERPRateLimitMetadata(
                            limit=data.get("account_rate_limit_per_hour"),
                            unit="searches_per_hour",
                            period="hour"
                        )

                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.CONNECTED.value,
                        status_message="Account verified and active.",
                        account=SERPAccountMetadata(
                            plan_id=data.get("plan_id"),
                            plan_name=plan_display,
                            account_email=data.get("account_email"),
                            account_id=data.get("account_id"),
                            status="active",
                            renewal_date=data.get("plan_renewal_date")
                        ),
                        usage=SERPUsageMetadata(
                            model=SERPUsageModel.MONTHLY_SEARCH_QUOTA.value,
                            used=used_searches,
                            limit=monthly_limit,
                            remaining=remaining_searches,
                            unit="searches",
                            percentage_used=pct_used,
                            renewal_date=data.get("plan_renewal_date"),
                            usage_available=True
                        ),
                        rate_limit=rate_limit_info,
                        capabilities=self.capabilities,
                        last_synced_at=now_iso
                    )

                elif res.status_code in [401, 403]:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.INVALID_CREDENTIALS.value,
                        status_message="Invalid SerpApi API key.",
                        capabilities=self.capabilities,
                        last_synced_at=now_iso,
                        sync_error="Authentication failed: 401 Unauthorized"
                    )
                else:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.ERROR.value,
                        status_message=f"SerpApi returned HTTP {res.status_code}",
                        capabilities=self.capabilities,
                        last_synced_at=now_iso,
                        sync_error=res.text[:200]
                    )

        except httpx.TimeoutException:
            return SERPNormalizedAccountInfo(
                provider=self.provider_id,
                provider_name=self.display_name,
                connection_status=SERPConnectionStatus.TIMEOUT.value,
                status_message="SerpApi account inspection timed out.",
                capabilities=self.capabilities,
                last_synced_at=now_iso,
                sync_error="Timeout connecting to serpapi.com/account.json"
            )
        except Exception as e:
            return SERPNormalizedAccountInfo(
                provider=self.provider_id,
                provider_name=self.display_name,
                connection_status=SERPConnectionStatus.ERROR.value,
                status_message=f"Account inspection failed: {str(e)}",
                capabilities=self.capabilities,
                last_synced_at=now_iso,
                sync_error=str(e)
            )

    async def search_keyword(
        self,
        keyword: str,
        credentials: Dict[str, Any],
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        provider = SerpApiProvider(api_key=api_key)
        return await provider.search_keyword(
            keyword=keyword,
            location=location,
            country=country,
            language=language,
            device=device,
            num_results=num_results
        )

    async def search_local_grid_point(
        self,
        keyword: str,
        credentials: Dict[str, Any],
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        provider = SerpApiProvider(api_key=api_key)
        return await provider.search_local_grid_point(
            keyword=keyword,
            lat=lat,
            lng=lng,
            location_name=location_name,
            zoom=zoom
        )
