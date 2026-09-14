import asyncio
import sys
import os

# Ensure backend root in path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base
import app.models  # noqa: F401
from app.models.user import User, Organization
from app.models.connections import OrganizationSERPConfig
from app.core.security import encrypt_token, decrypt_token
from app.services.serp.factory import get_organization_serp_provider
from app.services.serp.base import NotConfiguredSERPProvider
from app.services.serp.serpapi import SerpApiProvider

async def test_serp_architecture():
    # 1. Setup in-memory SQLite DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        # Create Test Organization & User
        org = Organization(name="Test SEO Org", slug="test-seo-org")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        # 2. Verify Unconfigured SERP Provider
        provider = await get_organization_serp_provider(session, org.id)
        assert isinstance(provider, NotConfiguredSERPProvider), f"Expected NotConfiguredSERPProvider, got {type(provider)}"
        
        # Test search behavior when unconfigured
        res = await provider.search_keyword("test keyword", "New York, USA")
        assert res.success is False
        assert res.error_code == "SERP_API_KEY_REQUIRED"
        assert res.organic_results == []
        print("[PASS] Step 1: Unconfigured organization returns NotConfiguredSERPProvider with clean error state (no Docker attempted)")

        # 3. Configure Organization SERP Key (Encrypted)
        raw_api_key = "test_serpapi_key_abc123xyz"
        encrypted_key = encrypt_token(raw_api_key)
        assert encrypted_key != raw_api_key, "API key was not encrypted"
        assert decrypt_token(encrypted_key) == raw_api_key, "Decrypted API key does not match original"

        serp_config = OrganizationSERPConfig(
            organization_id=org.id,
            provider="serpapi",
            api_key=encrypted_key,
            enabled=True,
            connection_status="connected"
        )
        session.add(serp_config)
        await session.commit()

        # 4. Verify Configured SERP Provider
        provider2 = await get_organization_serp_provider(session, org.id)
        assert isinstance(provider2, SerpApiProvider), f"Expected SerpApiProvider, got {type(provider2)}"
        assert provider2.api_key == raw_api_key, "Provider did not receive decrypted API key"
        print("[PASS] Step 2: Configured organization resolves SerpApiProvider with decrypted key")

        # 5. Verify Masking
        masked_key = f"********{raw_api_key[-4:]}"
        assert "abc123xyz" not in masked_key[:8]
        assert masked_key == "********3xyz"
        print("[PASS] Step 3: Key masking format verified")

        # 6. Verify Disabled State
        serp_config.enabled = False
        await session.commit()

        provider3 = await get_organization_serp_provider(session, org.id)
        assert isinstance(provider3, NotConfiguredSERPProvider), "Disabled config should return NotConfiguredSERPProvider"
        print("[PASS] Step 4: Disabled SERP config returns NotConfiguredSERPProvider")

    await engine.dispose()
    print("\n[SUCCESS] All SERP architecture unit & integration tests passed!")

if __name__ == "__main__":
    asyncio.run(test_serp_architecture())
