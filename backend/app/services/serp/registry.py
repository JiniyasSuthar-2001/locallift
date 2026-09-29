import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.future import select

from app.core.security import decrypt_token
from app.models.connections import OrganizationSERPConfig
from app.services.serp.adapters.base import (
    SERPProviderAdapter,
    SERPNormalizedAccountInfo,
    SERPConnectionStatus
)
from app.services.serp.adapters.serpapi_adapter import SerpApiAdapter
from app.services.serp.adapters.serper_adapter import SerperAdapter
from app.services.serp.adapters.dataforseo_adapter import DataForSEOAdapter
from app.services.serp.adapters.searchapi_adapter import SearchApiAdapter
from app.services.serp.adapters.openserp_adapter import OpenSERPAdapter
from app.services.serp.adapters.not_configured_adapter import NotConfiguredAdapter

logger = logging.getLogger("locallift.serp.registry")


class SERPProviderRegistry:
    """
    Central Registry for all SERP Provider Adapters in LocalLift.
    Handles dynamic provider discovery, credential unpacking, and execution routing.
    """

    _adapters: Dict[str, SERPProviderAdapter] = {
        "serpapi": SerpApiAdapter(),
        "serper": SerperAdapter(),
        "dataforseo": DataForSEOAdapter(),
        "searchapi": SearchApiAdapter(),
        "openserp": OpenSERPAdapter(),
        "not_configured": NotConfiguredAdapter()
    }

    @classmethod
    def list_available_providers(cls) -> List[Dict[str, Any]]:
        """
        Returns active provider descriptors for the frontend settings dropdown & dynamic forms.
        Only functional, implemented adapters are returned.
        """
        active_providers = ["serpapi", "serper", "dataforseo", "searchapi", "openserp"]
        result = []
        for pid in active_providers:
            adapter = cls._adapters.get(pid)
            if adapter:
                result.append({
                    "provider_id": adapter.provider_id,
                    "display_name": adapter.display_name,
                    "description": adapter.description,
                    "credential_fields": [f.dict() for f in adapter.credential_fields],
                    "capabilities": adapter.capabilities.dict(),
                    "supported_billing_models": adapter.supported_billing_models
                })
        return result

    @classmethod
    def get_adapter(cls, provider_id: Optional[str]) -> SERPProviderAdapter:
        """Retrieves a provider adapter by ID, defaulting to NotConfiguredAdapter."""
        if not provider_id:
            return cls._adapters["not_configured"]
        clean_id = str(provider_id).strip().lower()
        return cls._adapters.get(clean_id, cls._adapters["not_configured"])

    @classmethod
    def unpack_credentials(cls, serp_config: Optional[OrganizationSERPConfig]) -> Dict[str, Any]:
        """
        Safely decrypts and unpacks stored credentials into a dictionary.
        Handles single API key or multi-field credentials (e.g. login/password).
        """
        if not serp_config:
            return {}

        creds: Dict[str, Any] = {}
        if serp_config.api_key:
            try:
                decrypted = decrypt_token(serp_config.api_key)
                if decrypted:
                    creds["api_key"] = decrypted
            except Exception as e:
                logger.warning(f"[SERP] Failed to decrypt api_key: {e}")

        if serp_config.base_url:
            creds["base_url"] = serp_config.base_url.strip()

        if hasattr(serp_config, "credentials_extra") and serp_config.credentials_extra:
            try:
                decrypted_extra = decrypt_token(serp_config.credentials_extra)
                if decrypted_extra:
                    extra_dict = json.loads(decrypted_extra)
                    if isinstance(extra_dict, dict):
                        creds.update(extra_dict)
            except Exception as e:
                logger.warning(f"[SERP] Failed to decrypt credentials_extra: {e}")

        return creds

    @classmethod
    async def resolve_for_org(
        cls,
        db: Any,
        organization_id: int
    ) -> Tuple[SERPProviderAdapter, Dict[str, Any], Optional[OrganizationSERPConfig]]:
        """
        Resolves the active provider adapter and decrypted credentials for an organization.
        """
        stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == organization_id)
        res = await db.execute(stmt)
        config = res.scalars().first()

        if not config or not config.enabled:
            return cls._adapters["not_configured"], {}, None

        adapter = cls.get_adapter(config.provider)
        credentials = cls.unpack_credentials(config)
        return adapter, credentials, config
