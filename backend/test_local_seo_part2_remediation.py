"""
LocalLift — Part 2 Local SEO Modules Remediation Test Suite
Verifies genuine behavior across:
1. Schema Intelligence & Validator (Coverage specs, dynamic applicability, generator prefill)
2. Local Citations & Directory Distribution (No fake seedings, genuine discovery, honest manual status)
3. NAP Consistency (Schema extraction, robust normalization, no fake matches on missing data)
4. Products & Services (LOCALLIFT_MANUAL provenance, unconnected default, local CRUD safety)
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select

from app.main import app
from app.database import get_db, Base
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project
from app.models.local_seo import BusinessProfile, Citation, SchemaRecord
from app.models.gbp import GoogleBusinessProfile
from app.core.security import create_access_token


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
    await engine.dispose()


@pytest_asyncio.fixture
async def auth_setup(test_session: AsyncSession):
    # 1. Organization
    org = Organization(name="Test Org", slug="test-org")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    # 2. User
    user = User(
        email="localseo_tester@example.com",
        hashed_password="hashed_password_sample",
        is_active=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    # 3. Membership
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=OrgRole.OWNER
    )
    test_session.add(member)
    await test_session.commit()

    # 3. Project
    project = Project(
        name="Apex Dental Care",
        domain="apexdentalcare.com",
        organization_id=org.id,
        primary_category="Dentist"
    )
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    # 4. Canonical Profile
    profile = BusinessProfile(
        project_id=project.id,
        business_name="Apex Dental Care",
        primary_phone="+1 (555) 234-5678",
        primary_address="123 Main Street, Suite 400",
        city="Austin",
        state="TX",
        postal_code="78701",
        country="US",
        website="https://apexdentalcare.com"
    )
    test_session.add(profile)
    await test_session.commit()

    token = create_access_token(subject=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "user": user,
        "org": org,
        "project": project,
        "headers": headers,
        "session": test_session
    }


@pytest.mark.asyncio
async def test_schema_intelligence_matrix_and_prefill(auth_setup):
    session = auth_setup["session"]
    headers = auth_setup["headers"]
    project = auth_setup["project"]

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/local-seo/schema/{project.id}/intelligence", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "tier_1_status" in data
        assert len(data["tier_1_status"]) == 18

        local_biz = data["tier_1_status"].get("LocalBusiness")
        assert local_biz is not None
        assert local_biz["definition"]
        assert local_biz["why_it_matters"]
        assert "name" in local_biz["required_properties"]
        assert local_biz["generator_prefill"]["business_name"] == "Apex Dental Care"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_citations_no_fake_seeding(auth_setup):
    session = auth_setup["session"]
    headers = auth_setup["headers"]
    project = auth_setup["project"]

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Listing citations on a fresh project must return 0 records (no fake 98-DA entries seeded)
        resp = await client.get(f"/api/v1/local-seo/citations/{project.id}", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # Distribution on fresh project
        dist_resp = await client.get(f"/api/v1/local-seo/citations/{project.id}/distribution", headers=headers)
        assert dist_resp.status_code == 200
        dist_data = dist_resp.json()
        assert dist_data["total_directories"] == 0
        assert dist_data["approved_count"] == 0

        # Adding a manual citation sets USER_PROVIDED and PENDING
        add_resp = await client.post("/api/v1/local-seo/citations", headers=headers, json={
            "project_id": project.id,
            "source_name": "Austin Business Directory",
            "listing_url": "https://austinbiz.org/apex-dental",
            "category": "Regional Directory",
            "domain_authority": 72
        })
        assert add_resp.status_code == 200
        new_cit = add_resp.json()
        assert new_cit["citation_type"] == "USER_PROVIDED"
        assert new_cit["verification_status"] == "PENDING"
        assert new_cit["listing_url"] == "https://austinbiz.org/apex-dental"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_nap_consistency_with_schema_and_normalization(auth_setup):
    import json
    session = auth_setup["session"]
    headers = auth_setup["headers"]
    project = auth_setup["project"]

    # Add Schema Record
    schema_rec = SchemaRecord(
        project_id=project.id,
        schema_type="Dentist",
        page_url="https://apexdentalcare.com",
        is_valid=True,
        raw_json_ld=json.dumps({
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": "Apex Dental Care",
            "telephone": "(555) 234-5678",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "123 Main St, Ste 400",
                "addressLocality": "Austin",
                "addressRegion": "TX",
                "postalCode": "78701"
            },
            "url": "https://apexdentalcare.com"
        })
    )
    session.add(schema_rec)

    # Add Citation with matching normalized address ("123 Main St, Suite 400")
    cit = Citation(
        project_id=project.id,
        source_name="Yelp",
        domain="yelp.com",
        listing_url="https://www.yelp.com/biz/apex-dental-care-austin",
        status="listed",
        nap_status="consistent",
        found_name="Apex Dental Care",
        found_phone="5552345678",
        found_address="123 Main St, Ste 400",
        found_website="https://apexdentalcare.com"
    )
    session.add(cit)
    await session.commit()

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/local-seo/nap/comparison/{project.id}", headers=headers)
        assert resp.status_code == 200
        nap_data = resp.json()

        assert nap_data["score_available"] is True
        assert nap_data["total_sources_evaluated"] >= 2

        # Check Schema Source
        schema_comp = next((c for c in nap_data["comparisons"] if c["source_type"] == "WEBSITE_SCHEMA"), None)
        assert schema_comp is not None
        assert schema_comp["is_consistent"] is True
        assert schema_comp["fields"]["phone"]["status"] == "match"
        assert schema_comp["fields"]["address"]["status"] == "match"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_products_and_services_provenance(auth_setup):
    session = auth_setup["session"]
    headers = auth_setup["headers"]
    project = auth_setup["project"]

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initial status for unconnected project
        resp = await client.get(f"/api/v1/google/gbp/{project.id}/products-services", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_connected"] is False

        # Create Product manually
        prod_resp = await client.post(f"/api/v1/google/gbp/{project.id}/products", headers=headers, json={
            "name": "Teeth Whitening Kit",
            "description": "Professional in-office whitening kit",
            "category": "Dental Care",
            "price": "$299"
        })
        assert prod_resp.status_code == 200
        prod_data = prod_resp.json()
        assert prod_data["source"] == "LOCALLIFT_MANUAL"
        assert prod_data["name"] == "Teeth Whitening Kit"

        # Create Service manually
        serv_resp = await client.post(f"/api/v1/google/gbp/{project.id}/services", headers=headers, json={
            "name": "Dental Implant Consultation",
            "description": "Comprehensive 3D scan and treatment consultation",
            "category": "Cosmetic Dentistry",
            "price": "$150"
        })
        assert serv_resp.status_code == 200
        serv_data = serv_resp.json()
        assert serv_data["source"] == "LOCALLIFT_MANUAL"
        assert serv_data["name"] == "Dental Implant Consultation"

        # Catalog listing returns both items with accurate counts
        list_resp = await client.get(f"/api/v1/google/gbp/{project.id}/products-services", headers=headers)
        assert list_resp.status_code == 200
        catalog = list_resp.json()
        assert catalog["total_products"] == 1
        assert catalog["total_services"] == 1
        assert len(catalog["items"]) == 2

    app.dependency_overrides.clear()
