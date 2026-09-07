import asyncio
import os
import sys
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import AsyncSessionLocal, engine, Base
from app.services.category_taxonomy import CategoryTaxonomy, BUSINESS_CATEGORIES_DATA
from app.models.user import User, Organization, OrganizationMember
from app.models.project import Project, Location
from app.core.security import get_password_hash, create_access_token

async def test_category_taxonomy_search_and_ranking():
    """Test category search behavior, ranking, and alias matching."""
    # 1. Search 'dentist'
    results = CategoryTaxonomy.search("dentist")
    assert len(results) > 0
    assert results[0]["name"] == "Dentist", f"Expected 'Dentist' as top result, got '{results[0]['name']}'"
    names = [r["name"] for r in results]
    assert any("Dental" in n or "Dentist" in n or "Orthodontist" in n for n in names)

    # 2. Search 'plumb'
    results_plumb = CategoryTaxonomy.search("plumb")
    assert len(results_plumb) > 0
    assert any("Plumb" in r["name"] for r in results_plumb)

    # 3. Search 'law'
    results_law = CategoryTaxonomy.search("law")
    assert len(results_law) > 0
    assert any("Law" in r["name"] or "Attorney" in r["name"] or "Lawyer" in r["name"] for r in results_law)

    # 4. Search 'real estate'
    results_re = CategoryTaxonomy.search("real estate")
    assert len(results_re) > 0
    assert any("Real Estate" in r["name"] for r in results_re)

    # 5. Nonexistent query
    results_none = CategoryTaxonomy.search("xyzabc nonexistent term 12345")
    assert len(results_none) == 0

    # 6. Popular only
    popular = CategoryTaxonomy.search(popular_only=True, limit=15)
    assert len(popular) > 0
    for p in popular:
        assert p.get("is_popular") is True

    # 7. Groups
    groups = CategoryTaxonomy.get_groups()
    assert "Healthcare & Medical" in groups
    assert "Home Services" in groups
    assert "Legal" in groups
    assert "Restaurants & Food" in groups

async def test_category_legacy_normalization():
    """Verify legacy project category strings are gracefully normalized without data loss."""
    assert CategoryTaxonomy.normalize_category_name("Dentist / Dental Clinic") == "Dentist"
    assert CategoryTaxonomy.normalize_category_name("Law Firm / Attorney") == "Law Firm"
    assert CategoryTaxonomy.normalize_category_name("Local Contractor / Service") == "General Contractor"
    assert CategoryTaxonomy.normalize_category_name("HVAC / Air Conditioning") == "HVAC Contractor"
    assert CategoryTaxonomy.normalize_category_name("Automotive Repair Shop") == "Auto Repair Shop"
    assert CategoryTaxonomy.normalize_category_name("Roofing Contractor") == "Roofing Contractor"
    assert CategoryTaxonomy.normalize_category_name("Plumbing Contractor") == "Plumber"
    assert CategoryTaxonomy.normalize_category_name("Electrical Contractor") == "Electrician"
    assert CategoryTaxonomy.normalize_category_name("") == "Local Business"
    assert CategoryTaxonomy.normalize_category_name(None) == "Local Business"

async def test_schema_type_resolution():
    """Verify specific Schema.org entity resolution for various business categories."""
    assert CategoryTaxonomy.get_schema_type_for_category("Dentist") == "Dentist"
    assert CategoryTaxonomy.get_schema_type_for_category("Plumber") == "Plumber"
    assert CategoryTaxonomy.get_schema_type_for_category("Electrician") == "Electrician"
    assert CategoryTaxonomy.get_schema_type_for_category("Law Firm") == "LegalService"
    assert CategoryTaxonomy.get_schema_type_for_category("Restaurant") == "Restaurant"
    assert CategoryTaxonomy.get_schema_type_for_category("Auto Repair Shop") == "AutoRepair"
    assert CategoryTaxonomy.get_schema_type_for_category("Hotel") == "Hotel"
    assert CategoryTaxonomy.get_schema_type_for_category("Custom Unknown Category XYZ") == "LocalBusiness"

async def test_category_api_endpoints_and_project_lifecycle():
    """Test full HTTP API integration for category lookup and project creation with primary/additional categories."""
    from app.main import _sync_sqlite_schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_schema)

    async with AsyncSessionLocal() as db:
        # Create test user & org
        test_email = "cat_test_user@example.com"
        from sqlalchemy.future import select
        existing_u = (await db.execute(select(User).where(User.email == test_email))).scalars().first()
        if not existing_u:
            org = Organization(name="Category Test Org", slug="cat-test-org")
            db.add(org)
            await db.flush()
            user = User(
                email=test_email,
                hashed_password=get_password_hash("TestPass123!"),
                full_name="Category Tester",
                is_active=True,
                is_superuser=False
            )
            db.add(user)
            await db.flush()
            mem = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
            db.add(mem)
            await db.commit()
            user_id = user.id
            org_id = org.id
        else:
            user_id = existing_u.id
            mem = (await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == user_id))).scalars().first()
            org_id = mem.organization_id

    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test GET /api/v1/categories
        resp = await client.get("/api/v1/categories?q=dentist")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) > 0
        assert data["items"][0]["name"] == "Dentist"

        # 2. Test GET /api/v1/categories/groups
        resp_groups = await client.get("/api/v1/categories/groups")
        assert resp_groups.status_code == 200
        assert "groups" in resp_groups.json()

        # 3. Test GET /api/v1/categories/popular
        resp_pop = await client.get("/api/v1/categories/popular")
        assert resp_pop.status_code == 200
        assert len(resp_pop.json()["items"]) > 0

        # 4. Test GET /api/v1/projects/categories
        resp_proj_cat = await client.get("/api/v1/projects/categories?q=law")
        assert resp_proj_cat.status_code == 200
        assert any("Law" in it["name"] or "Attorney" in it["name"] for it in resp_proj_cat.json()["items"])

        # 5. Create project with primary and additional categories
        create_payload = {
            "name": "Apex Dental & Orthodontics",
            "domain": "apexdentalcare.example.com",
            "primary_category": "Dentist",
            "additional_categories": ["Cosmetic Dentist", "Orthodontist", "Dental Clinic"],
            "country": "United States",
            "location": {
                "name": "Main Office",
                "city": "Dallas",
                "state": "TX",
                "country": "United States"
            }
        }
        res_create = await client.post("/api/v1/projects", json=create_payload, headers=headers)
        assert res_create.status_code == 200, res_create.text
        proj_data = res_create.json()
        assert proj_data["primary_category"] == "Dentist"
        assert "Cosmetic Dentist" in proj_data["additional_categories"]
        assert "Orthodontist" in proj_data["additional_categories"]
        proj_id = proj_data["id"]

        # 6. Verify GET project returns additional categories
        res_get = await client.get(f"/api/v1/projects/{proj_id}", headers=headers)
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["primary_category"] == "Dentist"
        assert len(get_data["additional_categories"]) == 3

        # 7. Create project with legacy composite category label
        legacy_payload = {
            "name": "Old Legal Associates",
            "domain": "oldlegalassoc.example.com",
            "primary_category": "Law Firm / Attorney",
            "country": "United States"
        }
        res_leg = await client.post("/api/v1/projects", json=legacy_payload, headers=headers)
        assert res_leg.status_code == 200
        # Should be cleanly normalized to "Law Firm"
        assert res_leg.json()["primary_category"] == "Law Firm"

        # 8. Update project categories
        update_payload = {
            "primary_category": "Orthodontist",
            "additional_categories": ["Dentist", "Pediatric Dentist"]
        }
        res_patch = await client.patch(f"/api/v1/projects/{proj_id}", json=update_payload, headers=headers)
        assert res_patch.status_code == 200
        patched_data = res_patch.json()
        assert patched_data["primary_category"] == "Orthodontist"
        assert "Dentist" in patched_data["additional_categories"]
        assert "Pediatric Dentist" in patched_data["additional_categories"]

if __name__ == "__main__":
    asyncio.run(test_category_taxonomy_search_and_ranking())
    asyncio.run(test_category_legacy_normalization())
    asyncio.run(test_schema_type_resolution())
    asyncio.run(test_category_api_endpoints_and_project_lifecycle())
    print("ALL CATEGORY SYSTEM TESTS PASSED SUCCESSFULLY!")
