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


class NotConfiguredAdapter(SERPProviderAdapter):
    @property
    def provider_id(self) -> str:
        return "not_configured"

    @property
    def display_name(self) -> str:
        return "Not Configured"

    @property
    def description(self) -> str:
        return "No SERP search provider configured. Add your account credentials in Settings to enable rank tracking and Geo-Grid."

    @property
    def credential_fields(self) -> List[SERPCredentialField]:
        return []

    @property
    def capabilities(self) -> SERPCapabilities:
        return SERPCapabilities()

    @property
    def supported_billing_models(self) -> List[str]:
        return [SERPUsageModel.NOT_CONFIGURED.value]

    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        return False, "No SERP provider configured."

    async def get_account_info(self, credentials: Dict[str, Any]) -> SERPNormalizedAccountInfo:
        return SERPNormalizedAccountInfo(
            provider="not_configured",
            provider_name="Not Configured",
            connection_status=SERPConnectionStatus.NOT_CONFIGURED.value,
            status_message="Connect your SERP provider account in Settings.",
            usage=SERPUsageMetadata(
                model=SERPUsageModel.NOT_CONFIGURED.value,
                usage_available=False
            ),
            capabilities=self.capabilities,
            last_synced_at=datetime.now(timezone.utc).isoformat()
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
            provider="not_configured",
            keyword=keyword,
            location=location,
            success=False,
            error_code="SERP_PROVIDER_NOT_CONFIGURED",
            error_message="Connect your SERP provider account in Settings to enable rank tracking."
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
            provider="not_configured",
            keyword=keyword,
            location=location_name,
            success=False,
            error_code="SERP_PROVIDER_NOT_CONFIGURED",
            error_message="Connect your SERP provider account in Settings to enable Geo-Grid scans."
        )
