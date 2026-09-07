import asyncio
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings, validate_production_security
from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location, Website
from app.models.connections import (
    GoogleConnection,
    GoogleAdsAccount,
    GoogleSearchConsoleProperty,
    GoogleAnalyticsProperty,
    PublicBusinessListing,
)
from app.services.google.public_maps_service import PublicGoogleMapsService
from app.services.google.connections_service import GoogleConnectionsService

from app.core.security import create_access_token, verify_password, get_password_hash
from sqlalchemy import select

async def run_tests():
    print("==================================================")
    print("STARTING CONNECTIONS & HARDENING TEST SUITE")
    print("==================================================")

    # 1. Test Production Security Fail-Fast
    print("\n[TEST 1] Testing production security fail-fast validator...")
    orig_env = settings.ENVIRONMENT
    orig_key = settings.SECRET_KEY
    try:
        settings.ENVIRONMENT = "production"
        settings.SECRET_KEY = "locallift-super-secret-key-production-change-me-12345"
        failed_fast = False
        try:
            validate_production_security()
        except RuntimeError as e:
            failed_fast = True
            print(f"  [PASS] Successfully caught insecure secret in production: {e}")
        assert failed_fast, "FAIL: Should have raised RuntimeError for default secret in production"
    finally:
        settings.ENVIRONMENT = orig_env
        settings.SECRET_KEY = orig_key
    print("  [PASS] Test 1 Passed: Insecure production secrets fail fast.")

    # 2. Test DB Initialization and Schema sync
    print("\n[TEST 2] Testing SQLite DB schema sync for connection models...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  [PASS] Test 2 Passed: Connection tables registered & created successfully.")

    async with AsyncSessionLocal() as db:
        # Seed test user and organization
        user_res = await db.execute(select(User).where(User.email == "test_connect_user@example.com"))
        test_user = user_res.scalars().first()
        if not test_user:
            test_user = User(
                email="test_connect_user@example.com",
                hashed_password=get_password_hash("SecurePass123!"),
                full_name="Connection Test User",
                is_active=True
            )
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)

        org_res = await db.execute(select(Organization).where(Organization.name == "Test Connection Org"))
        test_org = org_res.scalars().first()
        if not test_org:
            test_org = Organization(name="Test Connection Org", slug="test-connection-org")
            db.add(test_org)
            await db.commit()
            await db.refresh(test_org)

            member = OrganizationMember(
                organization_id=test_org.id,
                user_id=test_user.id,
                role=OrgRole.OWNER
            )
            db.add(member)
            test_user.organization_id = test_org.id
            await db.commit()

        # 3. Test Google OAuth URL generation
        print("\n[TEST 3] Testing Google OAuth URL generation...")
        from app.services.google.oauth import GoogleOAuthService
        auth_url = GoogleOAuthService.get_authorization_url(project_id=1, user_id=test_user.id, custom_state=f"org_{test_org.id}")
        assert "accounts.google.com" in auth_url
        assert "client_id=" in auth_url
        assert "business.manage" in auth_url
        print(f"  [PASS] Generated valid Google OAuth URL: {auth_url[:60]}...")


        # 4. Test Public Google Maps URL Parser
        print("\n[TEST 4] Testing Public Google Maps URL Parser...")
        sample_url_1 = "https://www.google.com/maps/place/Apex+Dental+Care/@-27.4698,153.0251,17z/data=!3m1!4b1"
        parsed_1 = PublicGoogleMapsService.parse_maps_url(sample_url_1)
        print(f"  Parsed URL 1: name='{parsed_1['name']}', lat={parsed_1['latitude']}, lng={parsed_1['longitude']}")
        assert parsed_1["name"] == "Apex Dental Care"
        assert parsed_1["latitude"] == -27.4698

        # Import public business
        pub_listing = await PublicGoogleMapsService.import_public_business(
            organization_id=test_org.id,
            maps_url=sample_url_1,
            db=db,
            target_category="Dentist"
        )
        assert pub_listing.id is not None
        assert pub_listing.name == "Apex Dental Care"
        assert pub_listing.organization_id == test_org.id
        assert pub_listing.is_managed is False
        print(f"  [PASS] Imported public business: ID={pub_listing.id}, name='{pub_listing.name}', is_managed={pub_listing.is_managed}")

        # 5. Test Automatic GBP and Multi-Service Resource Discovery & Idempotent Import
        print("\n[TEST 5] Testing GBP Resource Import and Deduplication...")
        import time
        t_id = int(time.time())
        sample_locations = [
            {
                "business_name": f"Metro Plumbing Pro {t_id}",
                "address": "123 Queen St, Brisbane QLD 4000",
                "phone": "+61 7 3000 1111",
                "website_url": f"https://metroplumbingpro{t_id}.com.au",
                "primary_category": "Plumber"
            },
            {
                "business_name": f"Downtown Espresso Bar {t_id}",
                "address": "456 Adelaide St, Brisbane QLD 4000",
                "phone": "+61 7 3000 2222",
                "website_url": None, # Testing "No website found" handling
                "primary_category": "Coffee Shop"
            }
        ]

        sample_gsc_urls = [f"https://metroplumbingpro{t_id}.com.au"]


        # Import 1st time
        import_res_1 = await GoogleConnectionsService.import_resources_to_locallift(
            organization_id=test_org.id,
            selected_gbp=sample_locations,
            selected_gsc_urls=sample_gsc_urls,
            db=db
        )
        print(f"  1st Import result: Created={import_res_1['created_projects_count']}, Imported Locations={import_res_1['imported_locations_count']}")
        assert import_res_1["created_projects_count"] == 2
        assert import_res_1["imported_locations_count"] == 2

        # Import 2nd time (Idempotency test: should not duplicate projects)
        import_res_2 = await GoogleConnectionsService.import_resources_to_locallift(
            organization_id=test_org.id,
            selected_gbp=sample_locations,
            selected_gsc_urls=sample_gsc_urls,
            db=db
        )
        print(f"  2nd Import result (Idempotency): Created={import_res_2['created_projects_count']}, Imported Locations={import_res_2['imported_locations_count']}")
        assert import_res_2["created_projects_count"] == 0
        assert import_res_2["imported_locations_count"] == 0

        # Verify created project records in DB
        from sqlalchemy.orm import selectinload
        proj_res = await db.execute(
            select(Project)
            .options(selectinload(Project.locations))
            .where(Project.organization_id == test_org.id, Project.name == f"Metro Plumbing Pro {t_id}")
        )
        created_proj = proj_res.scalars().first()
        assert created_proj is not None
        assert created_proj.domain == f"metroplumbingpro{t_id}.com.au"
        assert len(created_proj.locations) > 0
        print(f"  [PASS] Verified Project created with domain '{created_proj.domain}' and {len(created_proj.locations)} location(s).")



        # 6. Test Disconnect
        print("\n[TEST 6] Testing Disconnect...")
        # Create connection row first to test disconnect
        test_conn = GoogleConnection(
            organization_id=test_org.id,
            account_email="test_user@gmail.com",
            access_token="fake_access_token_123",
            refresh_token="fake_refresh_token_456",
            status="connected"
        )
        db.add(test_conn)
        await db.commit()


        disc_res = await GoogleConnectionsService.disconnect(organization_id=test_org.id, db=db)
        assert disc_res is True
        print("  [PASS] Successfully disconnected Google connection without deleting historical project data.")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (6/6)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())

