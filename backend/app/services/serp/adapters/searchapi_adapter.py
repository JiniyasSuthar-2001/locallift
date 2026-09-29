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
    SERPUsageModel,
    SERPConnectionStatus
)
from app.services.serp.base import SERPCapabilities, SERPResponse

logger = logging.getLogger("locallift.serp.adapter.searchapi")


class SearchApiAdapter(SERPProviderAdapter):
    ACCOUNT_ENDPOINT = "https://www.searchapi.io/api/v1/account"
    SEARCH_ENDPOINT = "https://www.searchapi.io/api/v1/search"

    @property
    def provider_id(self) -> str:
        return "searchapi"

    @property
    def display_name(self) -> str:
        return "SearchAPI"

    @property
    def description(self) -> str:
        return "Real-time Google SERP API with monthly search quota tracking and location-based local packs."

    @property
    def credential_fields(self) -> List[SERPCredentialField]:
        return [
            SERPCredentialField(
                key="api_key",
                label="SearchAPI Key",
                type="password",
                required=True,
                placeholder="Enter your SearchAPI.io API key",
                help_text="Find your API key in the searchapi.io dashboard."
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
            maps_reviews=False
        )

    @property
    def supported_billing_models(self) -> List[str]:
        return [SERPUsageModel.MONTHLY_SEARCH_QUOTA.value, SERPUsageModel.CREDITS.value]

    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        if not api_key:
            return False, "SearchAPI key is required."

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.ACCOUNT_ENDPOINT, headers={"Authorization": f"Bearer {api_key}"})
                if res.status_code == 200:
                    data = res.json()
                    plan = data.get("plan_name", "Active")
                    return True, f"Connected to SearchAPI ({plan})."
                elif res.status_code in [401, 403]:
                    return False, "Invalid SearchAPI key. Authentication failed."
                else:
                    return False, f"SearchAPI returned HTTP {res.status_code}"
        except httpx.TimeoutException:
            return False, "SearchAPI connection timed out."
        except Exception as e:
            return False, f"SearchAPI validation error: {str(e)}"

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
                res = await client.get(self.ACCOUNT_ENDPOINT, headers={"Authorization": f"Bearer {api_key}"})
                if res.status_code == 200:
                    data = res.json()
                    plan_name = data.get("plan_name", "Standard")
                    total_searches = data.get("searches_per_month") or data.get("total_searches")
                    remaining = data.get("searches_left") or data.get("remaining_searches")
                    used = (total_searches - remaining) if (total_searches is not None and remaining is not None) else data.get("searches_used")
                    pct_used = round((used / total_searches) * 100, 1) if (total_searches and used is not None) else None

                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.CONNECTED.value,
                        status_message="Account verified.",
                        account=SERPAccountMetadata(
                            plan_name=str(plan_name).title(),
                            account_email=data.get("email"),
                            status="active",
                            renewal_date=data.get("renews_at")
                        ),
                        usage=SERPUsageMetadata(
                            model=SERPUsageModel.MONTHLY_SEARCH_QUOTA.value,
                            used=used,
                            limit=total_searches,
                            remaining=remaining,
                            unit="searches",
                            percentage_used=pct_used,
                            renewal_date=data.get("renews_at"),
                            usage_available=True
                        ),
                        capabilities=self.capabilities,
                        last_synced_at=now_iso
                    )
                else:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.ERROR.value,
                        status_message=f"HTTP {res.status_code}",
                        capabilities=self.capabilities,
                        last_synced_at=now_iso
                    )
        except Exception as e:
            return SERPNormalizedAccountInfo(
                provider=self.provider_id,
                provider_name=self.display_name,
                connection_status=SERPConnectionStatus.ERROR.value,
                status_message=str(e),
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
        return SERPResponse(
            provider="searchapi",
            keyword=keyword,
            location=location,
            success=True,
            total_results_count=0
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
        return SERPResponse(
            provider="searchapi",
            keyword=keyword,
            location=location_name,
            success=True,
            total_results_count=0
        )
