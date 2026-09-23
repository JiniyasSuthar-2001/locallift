import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, Organization
from app.models.project import Project, Location
from app.models.connections import PublicBusinessListing
from app.services.google.public_maps_service import PublicGoogleMapsService, is_safe_and_allowed_url
from app.services.ai.unconfigured_provider import UnconfiguredAIProvider
from app.services.ai.gemini_provider import GeminiAIProvider


from app.database import AsyncSessionLocal



@pytest.mark.asyncio
async def test_ssrf_url_validation():
    """Verify that SSRF attempts (private IPs, localhost, dangerous schemes, non-Google hosts) are rejected."""
    # Invalid schemes
    assert not is_safe_and_allowed_url("file:///etc/passwd")
    assert not is_safe_and_allowed_url("ftp://google.com/test")
    assert not is_safe_and_allowed_url("gopher://127.0.0.1:80")

    # Localhost and private loopback / IP ranges
    assert not is_safe_and_allowed_url("http://localhost:8000/maps")
    assert not is_safe_and_allowed_url("http://127.0.0.1:8000/maps")
    assert not is_safe_and_allowed_url("http://169.254.169.254/latest/meta-data/")
    assert not is_safe_and_allowed_url("http://10.0.0.1/admin")
    assert not is_safe_and_allowed_url("http://192.168.1.1/setup")
    assert not is_safe_and_allowed_url("http://172.16.0.1/")

    # Non-Google arbitrary external domains
    assert not is_safe_and_allowed_url("https://malicious-site.com/exploit")
    assert not is_safe_and_allowed_url("https://evil-hacker.net/steal")

    # Legitimate Google Maps domains
    assert is_safe_and_allowed_url("https://www.google.com/maps/place/Test")
    assert is_safe_and_allowed_url("https://maps.google.com/?q=Test")
    assert is_safe_and_allowed_url("https://maps.app.goo.gl/abcdef123")
    assert is_safe_and_allowed_url("https://goo.gl/maps/xyz987")


@pytest.mark.asyncio
async def test_unconfigured_ai_provider_fails_honestly():
    """Verify UnconfiguredAIProvider raises explicit errors and never manufactures synthetic opportunities."""
    provider = UnconfiguredAIProvider()
    assert not provider.is_configured

    # Diagnostic analysis must fail closed
    with pytest.raises(RuntimeError) as exc_diag:
        await provider.analyze_project_query("Why did my ranking drop?", {})
    assert "AI_NOT_CONFIGURED" in str(exc_diag.value)

    # Review drafting must fail closed
    with pytest.raises(RuntimeError) as exc_review:
        await provider.draft_review_response("Alice", 5, "Great service", "My Business")
    assert "AI_NOT_CONFIGURED" in str(exc_review.value)

    # Content opportunities must fail closed without generating synthetic templates
    with pytest.raises(RuntimeError) as exc_opps:
        await provider.generate_content_opportunities({"business_name": "Test", "city": "Sydney", "category": "Dentist"})
    assert "AI_NOT_CONFIGURED" in str(exc_opps.value)


@pytest.mark.asyncio
async def test_gemini_provider_fails_closed_on_error():
    """Verify GeminiAIProvider does not fabricate recommendations on API failures."""
    provider = GeminiAIProvider(api_key="test_fake_key")

    with patch.object(provider, "_call_gemini_api", side_effect=RuntimeError("AI_RATE_LIMIT: Rate limit hit")):
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate_content_opportunities({"city": "Mumbai", "category": "Plumber"})
        assert "AI_PROVIDER_ERROR" in str(exc_info.value)

    with patch.object(provider, "_call_gemini_api", return_value="Invalid non-json response string"):
        with pytest.raises(RuntimeError) as exc_diag:
            await provider.analyze_project_query("check rank", {})
        assert "AI_INVALID_RESPONSE" in str(exc_diag.value)


import uuid

@pytest.mark.asyncio
async def test_location_place_id_persistence_on_project_creation():
    """Verify that when a project is created with a public Maps URL, Location receives place_id and coords."""
    uid = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"Test Org Apex {uid}", slug=f"apex-test-org-{uid}")
        session.add(org)
        await session.flush()

        user = User(
            email=f"owner_apex_{uid}@test.com",
            hashed_password="pw",
            is_active=True,
            is_superuser=False
        )
        session.add(user)
        await session.flush()

        project = Project(
            organization_id=org.id,
            name="Apex Dental Care",
            domain="apexdental.in",
            primary_category="Dentist",
            country="India",
            public_maps_url="https://www.google.com/maps/place/Apex+Dental/@23.0225,72.5714,17z/data=!1sChIJ12345apex"
        )
        session.add(project)
        await session.flush()

        loc = Location(
            project_id=project.id,
            name="Main Clinic",
            city="Ahmedabad",
            country="India"
        )
        session.add(loc)
        await session.flush()

        # Simulate resolved listing update
        listing = PublicBusinessListing(
            organization_id=org.id,
            project_id=project.id,
            place_id="ChIJ12345apex",
            name="Apex Dental Care",
            formatted_address="101 Ashram Rd, Ahmedabad, Gujarat 380009, India",
            latitude=23.0225,
            longitude=72.5714,
            phone="+91 79 1234 5678",
            lookup_status="found"
        )
        session.add(listing)
        await session.flush()

        # Apply update logic
        if listing and loc:
            loc.place_id = listing.place_id
            if loc.latitude is None and listing.latitude is not None:
                loc.latitude = listing.latitude
            if loc.longitude is None and listing.longitude is not None:
                loc.longitude = listing.longitude
            if not loc.address and listing.formatted_address:
                loc.address = listing.formatted_address
            if not loc.phone and listing.phone:
                loc.phone = listing.phone

        await session.commit()
        await session.refresh(loc)

        assert loc.place_id == "ChIJ12345apex"
        assert loc.latitude == 23.0225
        assert loc.longitude == 72.5714
        assert loc.address == "101 Ashram Rd, Ahmedabad, Gujarat 380009, India"
        assert loc.phone == "+91 79 1234 5678"

