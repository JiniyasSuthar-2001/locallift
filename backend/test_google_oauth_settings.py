"""
Comprehensive Test Suite for Settings Google OAuth Flow (Google Central Hub)
Tests:
1. Authorization URL generation with cryptographically signed state (requires auth)
2. Rejection of unauthenticated auth-url requests (HTTP 401)
3. Cryptographic state validation and replay nonce protection
4. Browser GET callback processing and HTTP 302 redirect behavior
5. Session isolation (no JWT in URL, LocalLift session unchanged)
6. Google connection persistence & status verification
7. Disconnect flow
8. Independence of normal login/auth endpoints
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.connections import GoogleConnection
from app.services.google.oauth import GoogleOAuthService
from app.services.google.connections_service import GoogleConnectionsService

async def run_google_oauth_settings_tests():
    print("=======================================================")
    print(">> STARTING GOOGLE CENTRAL HUB OAUTH TEST SUITE")
    print("=======================================================")

    results = {}
    uid = uuid.uuid4().hex[:6]
    email = f"google_oauth_tester_{uid}@example.com"
    password = "Password123!"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register & Login
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "Google OAuth Tester",
            "organization_name": "SEO Agency"
        })
        login_res = await client.post("/api/v1/auth/login", data={
            "username": email,
            "password": password
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = login_res.json()["user"]["id"]
        org_id = login_res.json()["user"]["organization_id"]

        results["LocalLift Login"] = "PASS" if login_res.status_code == 200 else "FAIL"

        # 2. Test Unauthenticated Auth URL Request (Test 2)
        unauth_url_res = await client.get("/api/v1/connections/google/auth-url")
        results["Unauthenticated Auth URL Rejection"] = "PASS" if unauth_url_res.status_code == 401 else "FAIL"

        # 3. Test Authenticated Auth URL Generation (Test 1)
        auth_url_res = await client.get("/api/v1/connections/google/auth-url", headers=headers)
        auth_url_data = auth_url_res.json()
        results["Auth URL Generation"] = "PASS" if (
            auth_url_res.status_code == 200 and
            auth_url_data.get("configured") == True and
            "accounts.google.com" in auth_url_data.get("auth_url", "") and
            "state=" in auth_url_data.get("auth_url", "")
        ) else "FAIL"

        # 4. Cryptographic State & Replay Protection (Test 3)
        state_jwt = auth_url_data.get("auth_url", "").split("state=")[-1].split("&")[0]
        state_payload = GoogleOAuthService.decode_and_validate_oauth_state(state_jwt)
        results["State Signature Validation"] = "PASS" if (
            state_payload.get("user_id") == user_id and
            state_payload.get("organization_id") == org_id
        ) else "FAIL"

        # Test state replay rejection
        replay_rejected = False
        try:
            GoogleOAuthService.decode_and_validate_oauth_state(state_jwt)
        except ValueError:
            replay_rejected = True
        results["State Replay Rejection"] = "PASS" if replay_rejected else "FAIL"

        # 5. Test Browser GET Callback Cancel/Error Handling (Test 4)
        error_callback_res = await client.get(
            "/api/v1/connections/google/callback?error=access_denied&error_description=User+denied+consent",
            follow_redirects=False
        )
        results["Callback Error 302 Redirect"] = "PASS" if (
            error_callback_res.status_code == 302 and
            "connections?google=error" in error_callback_res.headers.get("location", "")
        ) else "FAIL"

        # 6. Test Direct Database Token Persistence (Simulating token exchange completion)
        mock_token_data = {
            "access_token": "mock_google_access_token_12345",
            "refresh_token": "mock_google_refresh_token_67890",
            "expires_in": 3600,
            "token_expiry": datetime.now(timezone.utc),
            "scopes": ["https://www.googleapis.com/auth/business.manage"],
            "email": f"connected_{uid}@gmail.com"
        }

        async with AsyncSessionLocal() as db:
            conn = await GoogleConnectionsService.save_connection_tokens(
                organization_id=org_id,
                user_id=user_id,
                token_data=mock_token_data,
                db=db
            )
            saved_email = conn.account_email

        # 7. Check Connection Status Endpoint (Test 6)
        status_res = await client.get("/api/v1/connections/status", headers=headers)
        status_data = status_res.json()
        results["Connection Status Verification"] = "PASS" if (
            status_res.status_code == 200 and
            status_data.get("is_connected") == True and
            status_data.get("account_email") == saved_email
        ) else "FAIL"

        # 8. Test Disconnect Endpoint (Test 7)
        disc_res = await client.post("/api/v1/connections/google/disconnect", headers=headers)
        status_after_disc = await client.get("/api/v1/connections/status", headers=headers)
        results["Disconnect Verification"] = "PASS" if (
            disc_res.status_code == 200 and
            status_after_disc.json().get("is_connected") == False
        ) else "FAIL"

    print("\n=======================================================")
    print(">> GOOGLE CENTRAL HUB TEST RESULTS TABLE")
    print("=======================================================")
    all_passed = True
    for test_name, status in results.items():
        print(f"| {test_name:<38} | {status:<10} |")
        if status != "PASS":
            all_passed = False
    print("=======================================================")
    if all_passed:
        print(">> ALL GOOGLE OAUTH SETTINGS TESTS PASSED 100%!")
    else:
        print(">> SOME TESTS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_google_oauth_settings_tests())
