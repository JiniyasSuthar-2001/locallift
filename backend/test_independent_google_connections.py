import asyncio
import logging
import sys
import os
import uuid
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, Organization, OrganizationMember
from app.models.connections import GoogleConnection
from app.services.google.oauth import (
    GoogleOAuthCore,
    BusinessProfileConnector,
    GoogleAdsConnector,
    SearchConsoleConnector,
    AnalyticsConnector
)
from app.services.google.connections_service import GoogleConnectionsService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_independent_google")


async def run_test_suite():
    logger.info("=== STARTING INDEPENDENT GOOGLE CONNECTIONS TEST SUITE ===")
    
    async with AsyncSessionLocal() as db:
        # Create test org & user
        unique_id = str(uuid.uuid4())[:8]
        test_org = Organization(name=f"Test Independent Org {unique_id}", slug=f"test-indep-org-{unique_id}")
        db.add(test_org)
        await db.flush()

        test_user = User(
            email=f"testuser_indep_{unique_id}@example.com",
            hashed_password="hashedpassword123",
            full_name="Test User",
            is_active=True
        )
        db.add(test_user)
        await db.flush()

        member = OrganizationMember(organization_id=test_org.id, user_id=test_user.id, role="owner")
        db.add(member)
        await db.commit()

        # -------------------------------------------------------------
        # TEST 1 — BUSINESS PROFILE SCOPE & AUTH URL ISOLATION
        # -------------------------------------------------------------
        bp_url = GoogleOAuthCore.get_authorization_url(
            service="business_profile",
            project_id=0,
            user_id=test_user.id,
            organization_id=test_org.id
        )
        assert "business.manage" in bp_url, "BP URL must contain business.manage scope"
        assert "adwords" not in bp_url, "BP URL must NOT contain adwords scope"
        assert "webmasters" not in bp_url, "BP URL must NOT contain webmasters scope"
        assert "analytics" not in bp_url, "BP URL must NOT contain analytics scope"
        logger.info("[PASS] TEST 1: Business Profile authorization URL contains only BP scopes.")

        # Save BP connection
        bp_token_data = {
            "email": "bp_user@gmail.com",
            "access_token": "fake_bp_access_token",
            "refresh_token": "fake_bp_refresh_token",
            "scopes": ["https://www.googleapis.com/auth/business.manage"],
            "token_expiry": datetime.now(timezone.utc)
        }
        await GoogleConnectionsService.save_connection_tokens(
            organization_id=test_org.id,
            user_id=test_user.id,
            service="business_profile",
            token_data=bp_token_data,
            db=db
        )

        status_summary = await GoogleConnectionsService.get_services_status_summary(test_org.id, db)
        assert status_summary["business_profile"]["connected"] is True, "BP must be connected"
        assert status_summary["google_ads"]["connected"] is False, "Ads must remain disconnected"
        assert status_summary["search_console"]["connected"] is False, "GSC must remain disconnected"
        assert status_summary["analytics"]["connected"] is False, "GA4 must remain disconnected"
        logger.info("[PASS] TEST 1: Business Profile connected independently.")

        # -------------------------------------------------------------
        # TEST 2 — GOOGLE ADS ISOLATION
        # -------------------------------------------------------------
        ads_url = GoogleOAuthCore.get_authorization_url(
            service="google_ads",
            project_id=0,
            user_id=test_user.id,
            organization_id=test_org.id
        )
        assert "adwords" in ads_url, "Ads URL must contain adwords scope"
        assert "business.manage" not in ads_url, "Ads URL must NOT contain business.manage scope"
        logger.info("[PASS] TEST 2: Google Ads authorization URL contains only Ads scopes.")

        ads_token_data = {
            "email": "ads_user@gmail.com",
            "access_token": "fake_ads_access_token",
            "refresh_token": "fake_ads_refresh_token",
            "scopes": ["https://www.googleapis.com/auth/adwords"],
            "token_expiry": datetime.now(timezone.utc)
        }
        await GoogleConnectionsService.save_connection_tokens(
            organization_id=test_org.id,
            user_id=test_user.id,
            service="google_ads",
            token_data=ads_token_data,
            db=db
        )

        status_summary = await GoogleConnectionsService.get_services_status_summary(test_org.id, db)
        assert status_summary["business_profile"]["connected"] is True, "BP must remain connected"
        assert status_summary["google_ads"]["connected"] is True, "Ads must now be connected"
        assert status_summary["search_console"]["connected"] is False, "GSC must remain disconnected"
        assert status_summary["analytics"]["connected"] is False, "GA4 must remain disconnected"
        logger.info("[PASS] TEST 2: Google Ads connected independently.")

        # -------------------------------------------------------------
        # TEST 3 — SEARCH CONSOLE ISOLATION
        # -------------------------------------------------------------
        gsc_url = GoogleOAuthCore.get_authorization_url(
            service="search_console",
            project_id=0,
            user_id=test_user.id,
            organization_id=test_org.id
        )
        assert "webmasters.readonly" in gsc_url, "GSC URL must contain webmasters scope"
        assert "adwords" not in gsc_url, "GSC URL must NOT contain adwords scope"
        logger.info("[PASS] TEST 3: Search Console authorization URL contains only GSC scopes.")

        gsc_token_data = {
            "email": "gsc_user@gmail.com",
            "access_token": "fake_gsc_access_token",
            "refresh_token": "fake_gsc_refresh_token",
            "scopes": ["https://www.googleapis.com/auth/webmasters.readonly"],
            "token_expiry": datetime.now(timezone.utc)
        }
        await GoogleConnectionsService.save_connection_tokens(
            organization_id=test_org.id,
            user_id=test_user.id,
            service="search_console",
            token_data=gsc_token_data,
            db=db
        )

        # -------------------------------------------------------------
        # TEST 4 — ANALYTICS ISOLATION
        # -------------------------------------------------------------
        ga4_url = GoogleOAuthCore.get_authorization_url(
            service="analytics",
            project_id=0,
            user_id=test_user.id,
            organization_id=test_org.id
        )
        assert "analytics.readonly" in ga4_url, "GA4 URL must contain analytics scope"
        assert "business.manage" not in ga4_url, "GA4 URL must NOT contain business scope"
        logger.info("[PASS] TEST 4: Analytics authorization URL contains only GA4 scopes.")

        # -------------------------------------------------------------
        # TEST 5 — MIXED CONNECTION STATE VERIFICATION
        # -------------------------------------------------------------
        status_summary = await GoogleConnectionsService.get_services_status_summary(test_org.id, db)
        assert status_summary["business_profile"]["connected"] is True
        assert status_summary["google_ads"]["connected"] is True
        assert status_summary["search_console"]["connected"] is True
        assert status_summary["analytics"]["connected"] is False
        logger.info("[PASS] TEST 5: Mixed state verified (BP: True, Ads: True, GSC: True, GA4: False).")

        # -------------------------------------------------------------
        # TEST 6 — INDEPENDENT DISCONNECT
        # -------------------------------------------------------------
        disconnected = await GoogleConnectionsService.disconnect(
            organization_id=test_org.id,
            service="business_profile",
            db=db
        )
        assert disconnected is True

        status_summary_after_disc = await GoogleConnectionsService.get_services_status_summary(test_org.id, db)
        assert status_summary_after_disc["business_profile"]["connected"] is False, "BP must now be disconnected"
        assert status_summary_after_disc["google_ads"]["connected"] is True, "Ads MUST REMAIN connected"
        assert status_summary_after_disc["search_console"]["connected"] is True, "GSC MUST REMAIN connected"
        logger.info("[PASS] TEST 6: Independent disconnect verified (disconnecting BP did NOT affect Ads or GSC).")

        # -------------------------------------------------------------
        # TEST 7 — STATE VALIDATION SECURITY
        # -------------------------------------------------------------
        valid_state = GoogleOAuthCore.encode_oauth_state(
            service="analytics",
            project_id=0,
            user_id=test_user.id,
            organization_id=test_org.id
        )
        decoded = GoogleOAuthCore.decode_and_validate_oauth_state(valid_state, expected_service="analytics")
        assert decoded["service"] == "analytics"
        assert decoded["organization_id"] == test_org.id
        
        # Test wrong service validation failure
        try:
            GoogleOAuthCore.decode_and_validate_oauth_state(valid_state, expected_service="business_profile")
            assert False, "Should have raised ValueError for mismatched service"
        except ValueError as ve:
            logger.info(f"[PASS] TEST 7: State mismatch rejected cleanly: {ve}")

        logger.info("=== ALL INDEPENDENT GOOGLE CONNECTION TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(run_test_suite())
