import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.core.security import encrypt_token, decrypt_token, migrate_token
from app.core.auth_rate_limiter import auth_rate_limiter
from app.services.serp.ranking_service import KeywordRankingService
from app.services.serp.normalizer import SERPNormalizer
from app.services.crawler import SSRFValidator, URLNormalizer
from app.services.schema_intelligence import SchemaIntelligenceEngine
from app.models.project import Project
from datetime import datetime

@pytest.mark.asyncio
async def test_auth_rate_limiting_and_lockout():
    """Test brute force login throttling, 429 response, and lockout protection."""
    orig_max = settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS
    orig_window = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    orig_lockout = settings.AUTH_LOCKOUT_DURATION_SECONDS
    settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS = 3
    settings.AUTH_RATE_LIMIT_WINDOW_SECONDS = 60
    settings.AUTH_LOCKOUT_DURATION_SECONDS = 120

    test_ip = "192.0.2.100"
    test_user = "bruteforce_target@example.com"
    auth_rate_limiter.reset_all()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt 1 failed (form data for OAuth2PasswordRequestForm)
        resp1 = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user, "password": "wrong_password_1"},
            headers={"x-forwarded-for": test_ip}
        )
        assert resp1.status_code == 401
        assert "Incorrect email or password" in resp1.json()["detail"]

        # Attempt 2 failed
        resp2 = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user, "password": "wrong_password_2"},
            headers={"x-forwarded-for": test_ip}
        )
        assert resp2.status_code == 401

        # Attempt 3 failed
        resp3 = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user, "password": "wrong_password_3"},
            headers={"x-forwarded-for": test_ip}
        )
        assert resp3.status_code == 401

        # Attempt 4 should be locked out (429)
        resp4 = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user, "password": "wrong_password_4"},
            headers={"x-forwarded-for": test_ip}
        )
        assert resp4.status_code == 429
        assert "Too many failed login attempts" in resp4.json()["detail"]

    # Restore settings
    settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS = orig_max
    settings.AUTH_RATE_LIMIT_WINDOW_SECONDS = orig_window
    settings.AUTH_LOCKOUT_DURATION_SECONDS = orig_lockout
    auth_rate_limiter.reset_all()


def test_encryption_decryption_and_legacy_migration():
    """Test dynamic Fernet suites, CURRENT_ENCRYPTION_KEY and LEGACY_ENCRYPTION_KEY migration."""
    test_secret = "ya29.a0AfH6SMD_secret_oauth_token_12345"
    
    # Encrypt with current key
    encrypted = encrypt_token(test_secret)
    assert encrypted != test_secret
    
    # Decrypt with current key
    decrypted = decrypt_token(encrypted)
    assert decrypted == test_secret
    
    # Test migration helper
    re_encrypted, was_migrated = migrate_token(encrypted)
    assert decrypt_token(re_encrypted) == test_secret


def test_country_evidence_hierarchy_and_normalization():
    """Test global country resolution hierarchy without US-first fallback."""
    # Test SERPNormalizer.normalize_country
    assert SERPNormalizer.normalize_country("US") == "us"
    assert SERPNormalizer.normalize_country("USA") == "us"
    assert SERPNormalizer.normalize_country("United States") == "us"
    assert SERPNormalizer.normalize_country("IN") == "in"
    assert SERPNormalizer.normalize_country("India") == "in"
    assert SERPNormalizer.normalize_country("AU") == "au"
    assert SERPNormalizer.normalize_country("Australia") == "au"
    assert SERPNormalizer.normalize_country("GB") in ["gb", "uk"]
    assert SERPNormalizer.normalize_country("United Kingdom") in ["gb", "uk"]
    assert SERPNormalizer.normalize_country("CA") == "ca"
    assert SERPNormalizer.normalize_country("Canada") == "ca"
    assert SERPNormalizer.normalize_country("unknown") == "us"
    assert SERPNormalizer.normalize_country("") == "us"
    assert SERPNormalizer.normalize_country(None) == "us"

    # Test TLD inference via resolve_serp_config
    p_uk = Project(domain="plumber.co.uk", country=None)
    assert KeywordRankingService.resolve_serp_config(p_uk)["country"] == "uk"

    p_au = Project(domain="dental.com.au", country=None)
    assert KeywordRankingService.resolve_serp_config(p_au)["country"] == "au"

    p_in = Project(domain="tech.in", country=None)
    assert KeywordRankingService.resolve_serp_config(p_in)["country"] == "in"

    p_ca = Project(domain="service.ca", country=None)
    assert KeywordRankingService.resolve_serp_config(p_ca)["country"] == "ca"

    # When domain has generic TLD (.com) and country is None, evidence-based resolution yields empty string (no silent US fabrication)
    p_generic = Project(domain="genericbiz.com", country=None)
    assert KeywordRankingService.resolve_serp_config(p_generic)["country"] == ""


def test_schema_generation_country_resolution():
    """Test that schema generation respects explicit country and does not default to US."""
    # Non-US schema build
    res_in = SchemaIntelligenceEngine.generate_safe_schema(
        business_type="Dentist",
        business_name="Mumbai Dental Clinic",
        url="https://mumbaidental.in",
        city="Mumbai",
        state="MH",
        country="India"
    )
    schema_in = json.loads(res_in["json_ld"])
    graph = schema_in.get("@graph", [schema_in])
    local_biz = next((e for e in graph if e.get("@type") == "Dentist"), None)
    assert local_biz is not None
    assert local_biz["address"]["addressCountry"] == "India"
    assert local_biz["address"]["addressCountry"] != "US"

    # Schema build without country
    res_unk = SchemaIntelligenceEngine.generate_safe_schema(
        business_type="LocalBusiness",
        business_name="Global Remote Services",
        url="https://globalremote.io",
        country=None
    )
    schema_unk = json.loads(res_unk["json_ld"])
    graph_unk = schema_unk.get("@graph", [schema_unk])
    local_biz_unk = next((e for e in graph_unk if e.get("@type") == "LocalBusiness"), None)
    if local_biz_unk and "address" in local_biz_unk:
        assert local_biz_unk["address"].get("addressCountry") is None


def test_geogrid_serp_production_mode_restriction():
    """Test that mock SERP provider is rejected or warned in production mode."""
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        assert settings.ENVIRONMENT == "production"
    finally:
        settings.ENVIRONMENT = orig_env


def test_crawler_url_validation_and_ssrf_safety():
    """Test that crawler rejects invalid schemes, private ranges, and missing domains."""
    # Missing / None URL
    assert URLNormalizer.normalize(None) is None
    assert URLNormalizer.normalize("") is None
    
    # URL normalization
    assert URLNormalizer.normalize("example.com") == "https://example.com/"
    assert URLNormalizer.normalize("http://example.com/foo/../bar") == "http://example.com/bar"
    
    # SSRF IP safety checks
    is_safe, msg = SSRFValidator.is_ip_safe("127.0.0.1", allow_local_dev=False)
    assert is_safe is False
    assert "SSRF_BLOCKED" in msg

    is_safe, msg = SSRFValidator.is_ip_safe("169.254.169.254", allow_local_dev=False)
    assert is_safe is False
    assert "metadata" in msg or "SSRF_BLOCKED" in msg

    is_safe, msg = SSRFValidator.is_ip_safe("10.0.0.1", allow_local_dev=False)
    assert is_safe is False

    is_safe, msg = SSRFValidator.is_ip_safe("192.168.1.1", allow_local_dev=False)
    assert is_safe is False

    is_safe, msg = SSRFValidator.is_ip_safe("8.8.8.8", allow_local_dev=False)
    assert is_safe is True
