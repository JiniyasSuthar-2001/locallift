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
from app.services.serp.openserp import OpenSERPProvider

logger = logging.getLogger("locallift.serp.adapter.openserp")


class OpenSERPAdapter(SERPProviderAdapter):
    @property
    def provider_id(self) -> str:
        return "openserp"

    @property
    def display_name(self) -> str:
        return "OpenSERP"

    @property
    def description(self) -> str:
        return "Self-hosted, unmetered web scraping engine. Note: Coordinate-based 5x5 Geo-Grid is not supported."

    @property
    def credential_fields(self) -> List[SERPCredentialField]:
        return [
            SERPCredentialField(
                key="base_url",
                label="OpenSERP Base URL",
                type="url",
                required=True,
                placeholder="http://127.0.0.1:7000",
                help_text="The HTTP base URL of your running OpenSERP instance."
            )
        ]

    @property
    def capabilities(self) -> SERPCapabilities:
        return SERPCapabilities(
            organic_search=True,
            local_search=True,
            maps_search=False,
            coordinate_search=False,
            geo_grid=False,
            maps_reviews=False
        )

    @property
    def supported_billing_models(self) -> List[str]:
        return [SERPUsageModel.UNAVAILABLE.value]

    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        base_url = (credentials.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            return False, "OpenSERP Base URL is required."

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(f"{base_url}/")
                if res.status_code in [200, 404]:
                    return True, "Connected to OpenSERP instance."
                return False, f"OpenSERP returned status {res.status_code}"
        except Exception as e:
            return False, f"Cannot connect to OpenSERP at {base_url}: {str(e)}"

    async def get_account_info(self, credentials: Dict[str, Any]) -> SERPNormalizedAccountInfo:
        base_url = (credentials.get("base_url") or "").strip().rstrip("/")
        now_iso = datetime.now(timezone.utc).isoformat()

        if not base_url:
            return SERPNormalizedAccountInfo(
                provider=self.provider_id,
                provider_name=self.display_name,
                connection_status=SERPConnectionStatus.NOT_CONFIGURED.value,
                status_message="OpenSERP Base URL not configured.",
                capabilities=self.capabilities,
                last_synced_at=now_iso
            )

        is_valid, msg = await self.validate_credentials(credentials)
        return SERPNormalizedAccountInfo(
            provider=self.provider_id,
            provider_name=self.display_name,
            connection_status=SERPConnectionStatus.CONNECTED.value if is_valid else SERPConnectionStatus.ERROR.value,
            status_message=msg,
            account=SERPAccountMetadata(
                plan_name="Self-Hosted Unmetered",
                status="active" if is_valid else "error"
            ),
            usage=SERPUsageMetadata(
                model=SERPUsageModel.UNAVAILABLE.value,
                usage_available=False
            ),
            capabilities=self.capabilities,
            last_synced_at=now_iso,
            sync_error=None if is_valid else msg
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
        base_url = (credentials.get("base_url") or "").strip().rstrip("/")
        provider = OpenSERPProvider(base_url=base_url)
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
        base_url = (credentials.get("base_url") or "").strip().rstrip("/")
        provider = OpenSERPProvider(base_url=base_url)
        return await provider.search_local_grid_point(
            keyword=keyword,
            lat=lat,
            lng=lng,
            location_name=location_name,
            zoom=zoom
        )
