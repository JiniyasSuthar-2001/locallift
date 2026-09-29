import enum
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.services.serp.base import SERPCapabilities, SERPResponse, SERPItem


class SERPUsageModel(str, enum.Enum):
    MONTHLY_SEARCH_QUOTA = "monthly_search_quota"
    CREDITS = "credits"
    ACCOUNT_BALANCE = "account_balance"
    REQUESTS = "requests"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


class SERPConnectionStatus(str, enum.Enum):
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    INVALID_CREDENTIALS = "invalid_credentials"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    ERROR = "error"


class SERPCredentialField(BaseModel):
    key: str
    label: str
    type: str = "password"  # text, password, url
    required: bool = True
    placeholder: str = ""
    help_text: Optional[str] = None


class SERPAccountMetadata(BaseModel):
    plan_id: Optional[str] = None
    plan_name: Optional[str] = None
    account_email: Optional[str] = None
    account_id: Optional[str] = None
    status: str = "active"
    renewal_date: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class SERPUsageMetadata(BaseModel):
    model: str = SERPUsageModel.UNAVAILABLE.value
    used: Optional[int] = None
    limit: Optional[int] = None
    remaining: Optional[int] = None
    balance: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = "searches"
    percentage_used: Optional[float] = None
    renewal_date: Optional[str] = None
    usage_available: bool = False


class SERPRateLimitMetadata(BaseModel):
    used: Optional[int] = None
    limit: Optional[int] = None
    unit: str = "searches_per_hour"
    period: str = "hour"


class SERPNormalizedAccountInfo(BaseModel):
    provider: str
    provider_name: str
    connection_status: str = SERPConnectionStatus.NOT_CONFIGURED.value
    status_message: Optional[str] = None
    account: SERPAccountMetadata = Field(default_factory=SERPAccountMetadata)
    usage: SERPUsageMetadata = Field(default_factory=SERPUsageMetadata)
    rate_limit: Optional[SERPRateLimitMetadata] = None
    capabilities: SERPCapabilities = Field(default_factory=SERPCapabilities)
    last_synced_at: Optional[str] = None
    sync_error: Optional[str] = None


class SERPProviderAdapter(ABC):
    """
    Abstract Extensible Adapter Interface for SERP Providers.
    Supports BYO account validation, live account inspection, quota normalization, and search execution.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier, e.g. 'serpapi', 'serper', 'dataforseo'."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider label, e.g. 'SerpApi'."""
        pass

    @property
    def description(self) -> str:
        """Short description for settings UI."""
        return ""

    @property
    @abstractmethod
    def credential_fields(self) -> List[SERPCredentialField]:
        """Schema of credentials required by this provider for frontend form rendering."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> SERPCapabilities:
        """Explicit feature capabilities supported by this provider."""
        pass

    @property
    def supported_billing_models(self) -> List[str]:
        """Billing models used by this provider."""
        return [SERPUsageModel.MONTHLY_SEARCH_QUOTA.value]

    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates whether the provided credentials are valid without counting as a chargeable search where supported.
        Returns (is_valid, status_message).
        """
        pass

    @abstractmethod
    async def get_account_info(self, credentials: Dict[str, Any]) -> SERPNormalizedAccountInfo:
        """
        Inspects the external provider account to retrieve real plan name, allowance, usage, renewal date, etc.
        Must NOT make regular search queries. Never returns fake or hardcoded quotas.
        """
        pass

    @abstractmethod
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
        """Executes real keyword ranking search."""
        pass

    @abstractmethod
    async def search_local_grid_point(
        self,
        keyword: str,
        credentials: Dict[str, Any],
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        """Executes coordinate-based local/maps search for Geo-Grid."""
        pass

    async def health_check(self, credentials: Dict[str, Any]) -> bool:
        """Lightweight connectivity health check."""
        is_valid, _ = await self.validate_credentials(credentials)
        return is_valid
