import pytest
import socket
import asyncio
import httpx
from app.config import settings
from app.services.crawler import SSRFValidator, SafeHTTPTransport, URLNormalizer

def test_ssrf_validator_localhost_and_loopback():
    is_safe, msg, _ = SSRFValidator.validate_url("http://localhost:8000/admin", allow_local_dev=False)
    assert not is_safe
    assert "SSRF_BLOCKED" in msg

    is_safe, msg, _ = SSRFValidator.validate_url("http://127.0.0.1:8000/admin", allow_local_dev=False)
    assert not is_safe
    assert "SSRF_BLOCKED" in msg

    is_safe, msg, _ = SSRFValidator.validate_url("http://[::1]:8000/admin", allow_local_dev=False)
    assert not is_safe
    assert "SSRF_BLOCKED" in msg

def test_ssrf_validator_private_ipv4_and_ipv6():
    private_urls = [
        "http://10.0.0.1/secret",
        "http://172.16.0.5/api",
        "http://192.168.1.1/router",
        "http://169.254.1.1/link-local",
        "http://[fc00::1]/private",
        "http://[fe80::1]/link-local",
    ]
    for url in private_urls:
        is_safe, msg, _ = SSRFValidator.validate_url(url, allow_local_dev=False)
        assert not is_safe, f"Expected {url} to be rejected by SSRFValidator, got safe."
        assert "SSRF_BLOCKED" in msg or "UNSAFE" in msg or "INVALID" in msg

def test_ssrf_validator_cloud_metadata_unconditional_block():
    metadata_urls = [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.253/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data/latest/meta-data/"
    ]
    for url in metadata_urls:
        # Check that even if allow_local_dev=True, cloud metadata is BLOCKED UNCONDITIONAL!
        is_safe, msg, _ = SSRFValidator.validate_url(url, allow_local_dev=True)
        assert not is_safe, f"Cloud metadata URL {url} must be unconditionally blocked!"
        assert "SSRF_BLOCKED" in msg

def test_ssrf_validator_internal_hostnames():
    internal_hosts = [
        "http://my-service.local/api",
        "http://cluster.internal/status",
        "http://router.lan/config"
    ]
    for url in internal_hosts:
        is_safe, msg, _ = SSRFValidator.validate_url(url, allow_local_dev=False)
        assert not is_safe
        assert "SSRF_BLOCKED" in msg

def test_ssrf_validator_unsafe_schemes():
    unsafe_urls = [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "gopher://example.com/search",
        "dict://example.com/word"
    ]
    for url in unsafe_urls:
        is_safe, msg, _ = SSRFValidator.validate_url(url, allow_local_dev=True)
        assert not is_safe
        assert "UNSAFE_SCHEME" in msg or "INVALID_URL" in msg

def test_ssrf_production_policy_enforcement(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    
    # Even when user passes allow_local_dev=True, in production it must be forced False!
    is_safe, msg, _ = SSRFValidator.validate_url("http://127.0.0.1:8000/api", allow_local_dev=True)
    assert not is_safe
    assert "SSRF_BLOCKED" in msg

def test_safe_http_transport_blocks_private_ip():
    async def _test():
        transport = SafeHTTPTransport(allow_local_dev=False)
        req = httpx.Request("GET", "http://127.0.0.1:8000/internal")
        with pytest.raises(httpx.RequestError) as exc_info:
            await transport.handle_async_request(req)
        assert "SSRF_BLOCKED" in str(exc_info.value)

    asyncio.run(_test())
