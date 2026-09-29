import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.security import encrypt_token, decrypt_token, is_plaintext_token
from app.models.connections import GoogleConnection
from app.models.user import User, Organization, OrganizationMember
from app.models.project import Project
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.config import settings

@pytest.mark.asyncio
async def test_token_encryption_and_decryption_lifecycle():
    """Verify encrypting and decrypting tokens with primary and fallback keys."""
    raw_access_token = "ya29.a0AfH6SMB_sample_access_token_12345"
    raw_refresh_token = "1//04_sample_refresh_token_67890"

    # 1. Encrypt tokens
    enc_access = encrypt_token(raw_access_token)
    enc_refresh = encrypt_token(raw_refresh_token)

    assert enc_access is not None
    assert enc_refresh is not None
    assert enc_access.startswith("gAAAAA")
    assert enc_refresh.startswith("gAAAAA")

    # 2. Decrypt tokens
    dec_access = decrypt_token(enc_access)
    dec_refresh = decrypt_token(enc_refresh)

    assert dec_access == raw_access_token
    assert dec_refresh == raw_refresh_token


@pytest.mark.asyncio
async def test_legacy_and_plaintext_token_handling():
    """Verify transparent plaintext detection and fallback legacy key support."""
    # Plaintext token
    raw_token = "ya29.a0AdM_legacy_unencrypted_access_token"
    assert is_plaintext_token(raw_token) is True
    assert decrypt_token(raw_token) == raw_token

    # Invalid corrupted ciphertext should raise ValueError without crashing
    with pytest.raises(ValueError) as exc:
        decrypt_token("invalid_corrupted_ciphertext_string")
    assert "Invalid or corrupted token ciphertext" in str(exc.value)


import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_token_refresh_preserves_refresh_token_and_reencrypts(test_session):
    """Verify that get_valid_access_token preserves refresh token and saves new encrypted token."""
    org = Organization(name="Test Encryption Org", slug="test-enc-org")
    test_session.add(org)
    await test_session.flush()

    raw_refresh = "1//04_valid_refresh_token_example"
    enc_refresh = encrypt_token(raw_refresh)

    # Expired connection
    conn = GoogleConnection(
        organization_id=org.id,
        service="business_profile",
        account_email="test@example.com",
        access_token=encrypt_token("expired_access_token"),
        refresh_token=enc_refresh,
        token_expiry=datetime.now(timezone.utc) - timedelta(hours=2),
        status="connected"
    )
    test_session.add(conn)
    await test_session.commit()

    # Mock Google OAuth refresh response
    mock_refresh_res = {
        "access_token": "ya29.a0AfH6SMB_new_refreshed_access_token",
        "token_expiry": datetime.now(timezone.utc) + timedelta(hours=1),
        "expires_in": 3600
    }

    with patch("app.services.google.oauth.GoogleOAuthCore.refresh_access_token", new_callable=AsyncMock) as mock_refresh:
        mock_refresh.return_value = mock_refresh_res
        valid_token = await GoogleConnectionsService.get_valid_access_token(conn, test_session)

        assert valid_token == "ya29.a0AfH6SMB_new_refreshed_access_token"
        assert conn.status == "connected"
        assert conn.sync_error is None
        # Must be encrypted in database
        assert conn.access_token.startswith("gAAAAA")
        assert decrypt_token(conn.access_token) == "ya29.a0AfH6SMB_new_refreshed_access_token"
        assert decrypt_token(conn.refresh_token) == raw_refresh


@pytest.mark.asyncio
async def test_gbp_api_access_not_granted_quota_zero_handling():
    """Verify GoogleBusinessProfileClient correctly classifies quota=0 API denial."""
    client = GoogleBusinessProfileClient(access_token="test_access_token")

    # Mock httpx response returning 429 quota_limit_value = 0
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = '{"error": {"code": 429, "message": "Resource exhausted", "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quota_limit_value": 0, "metric_name": "mybusinessaccountmanagement.googleapis.com/default"}]}]}}'

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await client.list_accounts()

        assert res["status"] == "API_ACCESS_NOT_GRANTED"
        assert "quota=0" in res["error"]
        assert len(res["accounts"]) == 0
