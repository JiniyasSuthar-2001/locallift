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

logger = logging.getLogger("locallift.serp.adapter.serper")


class SerperAdapter(SERPProviderAdapter):
    SEARCH_ENDPOINT = "https://google.serper.dev/search"
    PLACES_ENDPOINT = "https://google.serper.dev/places"
    ACCOUNT_ENDPOINT = "https://google.serper.dev/account"

    @property
    def provider_id(self) -> str:
        return "serper"

    @property
    def display_name(self) -> str:
        return "Serper"

    @property
    def description(self) -> str:
        return "Fast Google Search API with prepaid search credit accounting and place search capabilities."

    @property
    def credential_fields(self) -> List[SERPCredentialField]:
        return [
            SERPCredentialField(
                key="api_key",
                label="Serper API Key",
                type="password",
                required=True,
                placeholder="Enter your Serper.dev API key",
                help_text="Get your API key from serper.dev/dashboard."
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
        return [SERPUsageModel.CREDITS.value]

    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        if not api_key:
            return False, "Serper API key is required."

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.ACCOUNT_ENDPOINT, headers={"X-API-KEY": api_key})
                if res.status_code == 200:
                    data = res.json()
                    credits = data.get("credits", data.get("balance", "Active"))
                    return True, f"Connected to Serper ({credits} credits available)."
                elif res.status_code in [401, 403]:
                    return False, "Invalid Serper API key. Authentication failed."
                else:
                    return False, f"Serper returned HTTP {res.status_code}"
        except httpx.TimeoutException:
            return False, "Serper connection timed out."
        except Exception as e:
            return False, f"Serper validation error: {str(e)}"

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
                res = await client.get(self.ACCOUNT_ENDPOINT, headers={"X-API-KEY": api_key})
                if res.status_code == 200:
                    data = res.json()
                    remaining_credits = data.get("credits", data.get("balance"))
                    plan_name = data.get("plan", "Pay-as-you-go")

                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.CONNECTED.value,
                        status_message="Account verified.",
                        account=SERPAccountMetadata(
                            plan_name=str(plan_name).title(),
                            status="active"
                        ),
                        usage=SERPUsageMetadata(
                            model=SERPUsageModel.CREDITS.value,
                            remaining=remaining_credits,
                            unit="credits",
                            usage_available=True
                        ),
                        capabilities=self.capabilities,
                        last_synced_at=now_iso
                    )
                elif res.status_code in [401, 403]:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.INVALID_CREDENTIALS.value,
                        status_message="Invalid Serper API key.",
                        capabilities=self.capabilities,
                        last_synced_at=now_iso,
                        sync_error="401 Unauthorized"
                    )
                else:
                    return SERPNormalizedAccountInfo(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        connection_status=SERPConnectionStatus.ERROR.value,
                        status_message=f"Serper returned HTTP {res.status_code}",
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
        api_key = (credentials.get("api_key") or "").strip().strip("'\"")
        payload: Dict[str, Any] = {"q": keyword, "num": num_results}
        if location:
            payload["location"] = location
        if country:
            payload["gl"] = country.lower()
        if language:
            payload["hl"] = language.lower()

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(self.SEARCH_ENDPOINT, headers={"X-API-KEY": api_key, "Content-Type": "application/json"}, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    organic_items = []
                    for idx, org in enumerate(data.get("organic", []), start=1):
                        organic_items.append(
                            SERPItem(
                                position=org.get("position", idx),
                                title=org.get("title", ""),
                                link=org.get("link", ""),
                                domain=SERPNormalizer.extract_domain(org.get("link", "")),
                                snippet=org.get("snippet", ""),
                                item_type="organic"
                            )
                        )

                    local_items = []
                    for idx, place in enumerate(data.get("places", []), start=1):
                        local_items.append(
                            SERPItem(
                                position=idx,
                                title=place.get("title", ""),
                                address=place.get("address", ""),
                                phone=place.get("phoneNumber"),
                                category=place.get("category"),
                                rating=place.get("rating"),
                                reviews_count=place.get("ratingCount"),
                                item_type="local_pack",
                                place_id=place.get("placeId"),
                                data_cid=place.get("cid")
                            )
                        )

                    return SERPResponse(
                        provider="serper",
                        keyword=keyword,
                        location=location,
                        organic_results=organic_items,
                        local_pack_results=local_items,
                        total_results_count=len(organic_items) + len(local_items),
                        success=True
                    )
                else:
                    return SERPResponse(
                        provider="serper",
                        keyword=keyword,
                        location=location,
                        success=False,
                        error_code=f"SERPER_HTTP_{res.status_code}",
                        error_message=res.text[:200]
                    )
        except Exception as e:
            return SERPResponse(
                provider="serper",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERPER_REQUEST_ERROR",
                error_message=str(e)
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
        # Query places endpoint with lat/lng search query
        query = f"{keyword} near {lat},{lng}" if not location_name else f"{keyword} {location_name}"
        payload = {"q": query}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(self.PLACES_ENDPOINT, headers={"X-API-KEY": api_key, "Content-Type": "application/json"}, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    local_items = []
                    for idx, place in enumerate(data.get("places", []), start=1):
                        local_items.append(
                            SERPItem(
                                position=idx,
                                title=place.get("title", ""),
                                address=place.get("address", ""),
                                rating=place.get("rating"),
                                reviews_count=place.get("ratingCount"),
                                category=place.get("category"),
                                item_type="local_pack",
                                place_id=place.get("placeId"),
                                data_cid=place.get("cid")
                            )
                        )
                    return SERPResponse(
                        provider="serper",
                        keyword=keyword,
                        location=location_name,
                        local_pack_results=local_items,
                        total_results_count=len(local_items),
                        success=True
                    )
                else:
                    return SERPResponse(
                        provider="serper",
                        keyword=keyword,
                        location=location_name,
                        success=False,
                        error_code=f"SERPER_HTTP_{res.status_code}",
                        error_message=res.text[:200]
                    )
        except Exception as e:
            return SERPResponse(
                provider="serper",
                keyword=keyword,
                location=location_name,
                success=False,
                error_code="SERPER_REQUEST_ERROR",
                error_message=str(e)
            )
