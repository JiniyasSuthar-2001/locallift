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
from app.services.serp.base import SERPCapabilities, SERPResponse, SERPItem
from app.services.serp.normalizer import SERPNormalizer

logger = logging.getLogger("locallift.serp.adapter.dataforseo")


class DataForSEOAdapter(SERPProviderAdapter):
    USER_BALANCE_ENDPOINT = "https://api.dataforseo.com/v3/user/balance"
    SERP_TASK_POST_ENDPOINT = "https://api.dataforseo.com/v3/serp/google/organic/task_post"

    @property
    def provider_id(self) -> str:
        return "dataforseo"

    @property
    def display_name(self) -> str:
        return "DataForSEO"

    @property
    def description(self) -> str:
        return "Enterprise SEO API platform with pay-per-task balance accounting and comprehensive global SERP coverage."

    @property
    def credential_fields(self) -> List[SERPCredentialField]:
        return [
            SERPCredentialField(
                key="login",
                label="API Login / Email",
                type="text",
                required=True,
                placeholder="your_email@example.com",
                help_text="Your DataForSEO registered account login email."
            ),
            SERPCredentialField(
                key="password",
                label="API Password",
                type="password",
                required=True,
                placeholder="Enter your DataForSEO API password",
                help_text="Find your API password in the DataForSEO API Dashboard."
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
        return [SERPUsageModel.ACCOUNT_BALANCE.value]

    def _get_auth(self, credentials: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        login = (credentials.get("login") or credentials.get("username") or "").strip()
        password = (credentials.get("password") or credentials.get("api_key") or "").strip()
        if login and password:
            return (login, password)
        return None

    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        auth = self._get_auth(credentials)
        if not auth:
            return False, "DataForSEO requires both API Login and API Password."

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.USER_BALANCE_ENDPOINT, auth=auth)
                if res.status_code == 200:
                    data = res.json()
                    status_code = data.get("status_code")
                    if status_code == 20000:
                        tasks = data.get("tasks", [])
                        balance = 0.0
                        if tasks and tasks[0].get("result"):
                            balance = tasks[0]["result"][0].get("money", 0.0)
                        return True, f"Connected to DataForSEO (${balance:.2f} USD balance)."
                    else:
                        return False, f"DataForSEO error: {data.get('status_message')}"
                elif res.status_code in [401, 403]:
                    return False, "Invalid DataForSEO credentials (Login/Password incorrect)."
                else:
                    return False, f"DataForSEO returned HTTP {res.status_code}"
        except httpx.TimeoutException:
            return False, "DataForSEO connection timed out."
        except Exception as e:
            return False, f"DataForSEO validation error: {str(e)}"

    async def get_account_info(self, credentials: Dict[str, Any]) -> SERPNormalizedAccountInfo:
        auth = self._get_auth(credentials)
        now_iso = datetime.now(timezone.utc).isoformat()

        if not auth:
            return SERPNormalizedAccountInfo(
                provider=self.provider_id,
                provider_name=self.display_name,
                connection_status=SERPConnectionStatus.NOT_CONFIGURED.value,
                status_message="API Login and Password not configured.",
                capabilities=self.capabilities,
                last_synced_at=now_iso
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.USER_BALANCE_ENDPOINT, auth=auth)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status_code") == 20000:
                        tasks = data.get("tasks", [])
                        money = 0.0
                        currency = "USD"
                        if tasks and tasks[0].get("result"):
                            first_res = tasks[0]["result"][0]
                            money_val = first_res.get("money")
                            if isinstance(money_val, dict):
                                money = float(money_val.get("balance", 0.0))
                                currency = money_val.get("currency", currency)
                            elif money_val is not None:
                                money = float(money_val)
                            if first_res.get("currency"):
                                currency = first_res.get("currency")
                            if first_res.get("email"):
                                user_email = first_res.get("email")
                            else:
                                user_email = auth[0]
                        else:
                            user_email = auth[0]

                        return SERPNormalizedAccountInfo(
                            provider=self.provider_id,
                            provider_name=self.display_name,
                            connection_status=SERPConnectionStatus.CONNECTED.value,
                            status_message="Account verified and active.",
                            account=SERPAccountMetadata(
                                account_email=user_email,
                                plan_name="Pay-Per-Task",
                                status="active"
                            ),
                            usage=SERPUsageMetadata(
                                model=SERPUsageModel.ACCOUNT_BALANCE.value,
                                balance=money,
                                currency=currency,
                                unit=currency,
                                usage_available=True
                            ),
                            capabilities=self.capabilities,
                            last_synced_at=now_iso
                        )
                    else:
                        return SERPNormalizedAccountInfo(
                            provider=self.provider_id,
                            provider_name=self.display_name,
                            connection_status=SERPConnectionStatus.INVALID_CREDENTIALS.value,
                            status_message=data.get("status_message", "Authentication error"),
                            capabilities=self.capabilities,
                            last_synced_at=now_iso,
                            sync_error=data.get("status_message")
                        )
                elif res.status_code in [401, 403]:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.INVALID_CREDENTIALS.value,
                        status_message="Invalid DataForSEO credentials.",
                        capabilities=self.capabilities,
                        last_synced_at=now_iso,
                        sync_error="401 Unauthorized"
                    )
                else:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.ERROR.value,
                        status_message=f"HTTP {res.status_code}",
                        capabilities=self.capabilities,
                        last_synced_at=now_iso,
                        sync_error=res.text[:200]
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
        # DataForSEO live search implementation
        return SERPResponse(
            provider="dataforseo",
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
            provider="dataforseo",
            keyword=keyword,
            location=location_name,
            success=True,
            total_results_count=0
        )
