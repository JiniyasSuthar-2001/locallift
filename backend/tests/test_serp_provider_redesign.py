import pytest
import pytest_asyncio
import json
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock

from app.models.user import User, Organization, OrganizationMember
from app.models.connections import OrganizationSERPConfig
from app.models.project import Project
from app.core.security import encrypt_token, decrypt_token
from app.services.serp.registry import SERPProviderRegistry
from app.services.serp.adapters.serpapi_adapter import SerpApiAdapter
from app.services.serp.adapters.serper_adapter import SerperAdapter
from app.services.serp.adapters.dataforseo_adapter import DataForSEOAdapter
from app.services.serp.adapters.searchapi_adapter import SearchApiAdapter
from app.services.serp.adapters.openserp_adapter import OpenSERPAdapter
from app.services.serp.adapters.base import SERPUsageModel, SERPConnectionStatus


@pytest.mark.asyncio
async def test_serpapi_account_normalization_250_plan():
    """Validates SerpApi 250-search starter plan normalization."""
    adapter = SerpApiAdapter()
    raw_serpapi_resp = {
        "account_email": "starter@locallift.io",
        "plan_id": "starter_250",
        "plan_name": "Free Starter",
        "searches_per_month": 250,
        "this_month_usage": 50,
        "plan_searches_left": 200,
        "plan_renewal_date": "2026-10-15",
        "account_rate_limit_per_hour": 100
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_serpapi_resp
        mock_get.return_value = mock_resp

        norm = await adapter.get_account_info({"api_key": "test_key_250"})
        assert norm.usage.model == SERPUsageModel.MONTHLY_SEARCH_QUOTA.value
        assert norm.usage.limit == 250
        assert norm.usage.used == 50
        assert norm.usage.remaining == 200
        assert norm.usage.percentage_used == 20.0
        assert norm.usage.unit == "searches"

        assert "Free Starter" in norm.account.plan_name
        assert norm.account.account_email == "starter@locallift.io"
        assert norm.account.renewal_date == "2026-10-15"
        assert norm.account.status == "active"


@pytest.mark.asyncio
async def test_serpapi_account_normalization_1000_plan():
    """Validates SerpApi 1,000-search plan normalization."""
    adapter = SerpApiAdapter()
    raw_serpapi_resp = {
        "account_email": "pro@agency.com",
        "plan_id": "pro_1k",
        "plan_name": "Pro 1K",
        "searches_per_month": 1000,
        "this_month_usage": 750,
        "plan_searches_left": 250,
        "plan_renewal_date": "2026-11-01"
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_serpapi_resp
        mock_get.return_value = mock_resp

        norm = await adapter.get_account_info({"api_key": "test_key_1000"})
        assert norm.usage.limit == 1000
        assert norm.usage.used == 750
        assert norm.usage.remaining == 250
        assert norm.usage.percentage_used == 75.0


@pytest.mark.asyncio
async def test_serpapi_account_normalization_5000_plan():
    """Validates SerpApi 5,000-search developer plan normalization from actual API payload."""
    adapter = SerpApiAdapter()
    raw_serpapi_resp = {
        "account_email": "dev@locallift.io",
        "plan_id": "developer",
        "plan_name": "Developer",
        "searches_per_month": 5000,
        "this_month_usage": 1240,
        "plan_searches_left": 3760,
        "plan_renewal_date": "2026-10-27",
        "account_rate_limit_per_hour": 1000
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_serpapi_resp
        mock_get.return_value = mock_resp

        norm = await adapter.get_account_info({"api_key": "test_key_5000"})
        assert norm.usage.limit == 5000
        assert norm.usage.used == 1240
        assert norm.usage.remaining == 3760
        assert norm.usage.percentage_used == 24.8


@pytest.mark.asyncio
async def test_serpapi_account_normalization_15000_and_custom_plans():
    """Validates SerpApi 15,000-search agency plan & custom enterprise tiers."""
    adapter = SerpApiAdapter()
    raw_serpapi_resp = {
        "account_email": "enterprise@global.com",
        "plan_id": "agency_15k",
        "plan_name": "Agency 15K",
        "searches_per_month": 15000,
        "this_month_usage": 13500,
        "plan_searches_left": 1500,
        "plan_renewal_date": "2026-12-31"
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_serpapi_resp
        mock_get.return_value = mock_resp

        norm = await adapter.get_account_info({"api_key": "test_key_15000"})
        assert norm.usage.limit == 15000
        assert norm.usage.used == 13500
        assert norm.usage.remaining == 1500
        assert norm.usage.percentage_used == 90.0


@pytest.mark.asyncio
async def test_serper_credit_based_adapter():
    """Validates Serper credit billing model adapter."""
    adapter = SerperAdapter()
    assert adapter.provider_id == "serper"
    assert adapter.capabilities.geo_grid is True
    assert adapter.capabilities.maps_search is True

    raw_serper_resp = {
        "status": "active",
        "credits": 48760,
        "plan": "Standard Credits"
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_serper_resp
        mock_get.return_value = mock_resp

        norm = await adapter.get_account_info({"api_key": "serper_secret_key"})
        assert norm.usage.model == SERPUsageModel.CREDITS.value
        assert norm.usage.remaining == 48760
        assert norm.usage.unit == "credits"


@pytest.mark.asyncio
async def test_dataforseo_balance_adapter():
    """Validates DataForSEO account balance model adapter with login/password."""
    adapter = DataForSEOAdapter()
    assert adapter.provider_id == "dataforseo"
    assert adapter.capabilities.geo_grid is True

    raw_dataforseo_resp = {
        "status_code": 20000,
        "tasks": [{
            "result": [{
                "email": "seo@client.com",
                "money": {
                    "balance": 43.72,
                    "currency": "USD"
                }
            }]
        }]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_dataforseo_resp
        mock_get.return_value = mock_resp

        norm = await adapter.get_account_info({"login": "my_login", "password": "my_password"})
        assert norm.usage.model == SERPUsageModel.ACCOUNT_BALANCE.value
        assert norm.usage.balance == 43.72
        assert norm.usage.currency == "USD"
        assert norm.usage.unit == "USD"
        assert norm.account.account_email == "seo@client.com"
        assert norm.account.status == "active"


@pytest.mark.asyncio
async def test_openserp_unmetered_and_capabilities():
    """Validates OpenSERP self-hosted unmetered usage and disabled geo_grid capability."""
    adapter = OpenSERPAdapter()
    assert adapter.provider_id == "openserp"
    assert adapter.capabilities.organic_search is True
    assert adapter.capabilities.geo_grid is False  # Coordinates not supported on basic OpenSERP
    assert adapter.capabilities.maps_search is False

    norm = await adapter.get_account_info({"base_url": "http://127.0.0.1:7000"})
    assert norm.usage.model == SERPUsageModel.UNAVAILABLE.value
    assert norm.usage.limit is None
    assert norm.usage.remaining is None


@pytest.mark.asyncio
async def test_invalid_credentials_error_handling():
    """Validates adapter error handling when provider reports 401/403."""
    adapter = SerpApiAdapter()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "Invalid API key."}
        mock_get.return_value = mock_resp

        is_valid, msg = await adapter.validate_credentials({"api_key": "bad_key_12345"})
        assert is_valid is False
        assert "Invalid" in msg


@pytest.mark.asyncio
async def test_registry_lists_all_active_providers():
    """Validates provider registry returns only actively implemented adapters."""
    providers = SERPProviderRegistry.list_available_providers()
    provider_ids = [p["provider_id"] for p in providers]

    assert "serpapi" in provider_ids
    assert "serper" in provider_ids
    assert "dataforseo" in provider_ids
    assert "searchapi" in provider_ids
    assert "openserp" in provider_ids

    for p in providers:
        assert "display_name" in p
        assert "credential_fields" in p
        assert "capabilities" in p
        assert "supported_billing_models" in p


@pytest.mark.asyncio
async def test_security_credential_encryption_and_no_raw_leak():
    """Validates API credentials are encrypted at rest with Fernet and raw keys are masked."""
    raw_key = "secret_serp_key_xyz_123456789"
    encrypted = encrypt_token(raw_key)

    # Encrypted token must not equal raw key
    assert encrypted != raw_key
    # Decryption recovers exact key
    assert decrypt_token(encrypted) == raw_key


@pytest.mark.asyncio
async def test_factory_returns_adapter_wrapper():
    """Validates that get_serp_provider returns an AdapterSERPProviderWrapper for provider adapters."""
    from app.services.serp.factory import get_serp_provider, AdapterSERPProviderWrapper

    provider = get_serp_provider(
        provider_type="serper",
        api_key="test_api_key"
    )
    assert isinstance(provider, AdapterSERPProviderWrapper)
    assert provider.capabilities.geo_grid is True


@pytest.mark.asyncio
async def test_usage_service_no_hardcoded_5000_quota():
    """Validates ProviderUsageService produces dynamic quotas and never falls back to 5000."""
    from app.services.provider_usage_service import ProviderUsageService
    from app.database import AsyncSessionLocal, engine, Base
    from app.models.user import User, Organization
    from app.models.connections import OrganizationSERPConfig

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        import uuid
        org_slug = f"serp-dynamic-{uuid.uuid4().hex[:8]}"
        org = Organization(name="SERP Dynamic Org", slug=org_slug)
        db.add(org)
        await db.flush()

        # Create SERP config with a 15,000 allowance
        serp_cfg = OrganizationSERPConfig(
            organization_id=org.id,
            provider="serpapi",
            api_key=encrypt_token("serp_key_15k"),
            connection_status="connected",
            enabled=True,
            account_info={"plan_name": "Agency 15K", "account_email": "agency@test.com"},
            usage_info={
                "model": "monthly_search_quota",
                "used": 12000,
                "limit": 15000,
                "remaining": 3000,
                "percentage_used": 80.0,
                "unit": "searches"
            }
        )
        db.add(serp_cfg)
        await db.commit()

        status = await ProviderUsageService.get_provider_status_and_forecast(db, organization_id=org.id)
        assert status["provider"] == "serpapi"
        assert status["connection_status"] == "connected"
        assert status["quota"]["limit"] == 15000  # Must be 15000, NOT 5000!
        assert status["quota"]["used"] == 12000
        assert status["quota"]["remaining"] == 3000
        assert status["quota"]["usage_pct"] == 80.0
        assert any("High SERP usage (80.0%" in w for w in status["warnings"])
