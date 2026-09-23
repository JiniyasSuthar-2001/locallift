import uuid
import pytest
from sqlalchemy.future import select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.models.connections import PublicBusinessListing
from app.services.google.public_maps_service import PublicGoogleMapsService
from app.core.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_parse_maps_urls():
    # 1. Full place URL with place name and coordinates
    url_1 = "https://www.google.com/maps/place/Apex+Dental+Studio/@-27.4705,153.0260,17z/data=!1sChIJrTLr-GyuEmsRBfy61i59si0"
    parsed_1 = PublicGoogleMapsService.parse_maps_url(url_1)
    assert parsed_1["name"] == "Apex Dental Studio"
    assert parsed_1["place_id"] == "ChIJrTLr-GyuEmsRBfy61i59si0"
    assert parsed_1["latitude"] == -27.4705
    assert parsed_1["longitude"] == 153.0260

    # 2. Search query URL
    url_2 = "https://www.google.com/maps/search/?api=1&query=Shree+Ram+Electricals+Ahmedabad"
    parsed_2 = PublicGoogleMapsService.parse_maps_url(url_2)
    assert parsed_2["name"] == "Shree Ram Electricals Ahmedabad"

    # 3. Query param place_id
    url_3 = "https://maps.google.com/?place_id=ChIJ12345abcdef"
    parsed_3 = PublicGoogleMapsService.parse_maps_url(url_3)
    assert parsed_3["place_id"] == "ChIJ12345abcdef"

    # 4. Short URL does not treat hash path as business name
    url_short = "https://maps.app.goo.gl/wXYZ12345abc"
    parsed_short = PublicGoogleMapsService.parse_maps_url(url_short)
    assert parsed_short["name"] is None  # Unresolved hash must not be fabricated as a name


@pytest.mark.asyncio
async def test_project_creation_with_country_and_public_maps_url():
    uid = uuid.uuid4().hex[:8]
    test_email = f"global_seo_tester_{uid}@locallift.test"
    org_slug = f"global-seo-test-org-{uid}"

    async with AsyncSessionLocal() as db:
        # Create test user and organization with unique slug
        org = Organization(name=f"Global SEO Test Org {uid}", slug=org_slug)
        db.add(org)
        await db.flush()

        user = User(
            email=test_email,
            hashed_password=get_password_hash("StrongSecret123!"),
            full_name="Global Tester",
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        await db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=OrgRole.OWNER
        )
        db.add(member)
        await db.commit()
        await db.refresh(user)

        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Project creation with non-Australian country (India) and Google Maps URL
            payload = {
                "name": "Bharat Electric Co",
                "domain": "bharatelectric.in",
                "primary_category": "Electrician",
                "country": "India",
                "public_maps_url": "https://www.google.com/maps/place/Bharat+Electric+Co/@23.0225,72.5714,15z",
                "location": {
                    "name": "Headquarters",
                    "city": "Ahmedabad",
                    "state": "Gujarat",
                    "postal_code": "380001",
                    "country": "India"
                }
            }

            resp = await ac.post("/api/v1/projects", json=payload, headers=headers)
            assert resp.status_code == 200, f"Project creation failed: {resp.text}"
            data = resp.json()
            assert data["name"] == "Bharat Electric Co"
            assert data["country"] == "India"
            assert data["public_maps_url"] == payload["public_maps_url"]
            assert len(data["locations"]) == 1
            assert data["locations"][0]["country"] == "India"
            assert data["locations"][0]["city"] == "Ahmedabad"

            proj_id = data["id"]

            # 2. Verify stored PublicBusinessListing and ensure no fake Australian address was fabricated
            res = await db.execute(
                select(PublicBusinessListing).where(PublicBusinessListing.project_id == proj_id)
            )
            listing = res.scalars().first()
            if listing:
                assert "Commercial Rd" not in (listing.formatted_address or "")
                assert "Sydney" not in (listing.formatted_address or "")
                assert listing.rating != 4.8 or listing.review_count != 42


@pytest.mark.asyncio
async def test_project_creation_without_maps_url_succeeds():
    uid = uuid.uuid4().hex[:8]
    test_email = f"uk_legal_tester_{uid}@locallift.test"
    org_slug = f"uk-legal-org-{uid}"

    async with AsyncSessionLocal() as db:
        org = Organization(name=f"UK Legal Org {uid}", slug=org_slug)
        db.add(org)
        await db.flush()

        user = User(
            email=test_email,
            hashed_password=get_password_hash("StrongSecret123!"),
            full_name="UK Legal Tester",
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        await db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=OrgRole.OWNER
        )
        db.add(member)
        await db.commit()
        await db.refresh(user)

        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "name": "London Legal Partners",
                "domain": "londonlegal.co.uk",
                "primary_category": "Legal Services",
                "country": "United Kingdom",
                "location": {
                    "name": "London Office",
                    "city": "London",
                    "country": "United Kingdom"
                }
            }

            resp = await ac.post("/api/v1/projects", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "London Legal Partners"
            assert data["country"] == "United Kingdom"
            assert data["public_maps_url"] is None
