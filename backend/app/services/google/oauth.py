import urllib.parse
import json
import logging
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from app.config import settings

logger = logging.getLogger("locallift.google.oauth")

class GoogleOAuthService:
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

    DEFAULT_SCOPES = [
        "https://www.googleapis.com/auth/business.manage",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid"
    ]

    @classmethod
    def is_configured(cls) -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    @classmethod
    def get_authorization_url(cls, project_id: int, user_id: int, custom_state: Optional[str] = None) -> str:
        """
        Builds the Google OAuth 2.0 consent URL for connecting a Google Business Profile.
        Encodes project_id and user_id into the OAuth state for CSRF and context preservation.
        """
        if not cls.is_configured():
            logger.warning("Google OAuth credentials are not configured in settings.")

        state_payload = {
            "project_id": project_id,
            "user_id": user_id,
            "nonce": custom_state or "locallift_oauth"
        }
        state_encoded = json.dumps(state_payload)

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(cls.DEFAULT_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state_encoded
        }

        query_str = urllib.parse.urlencode(params)
        return f"{cls.AUTH_ENDPOINT}?{query_str}"

    @classmethod
    async def exchange_code_for_tokens(cls, code: str) -> Dict[str, Any]:
        """
        Exchanges an OAuth 2.0 authorization code for an access token and refresh token.
        """
        if not cls.is_configured():
            raise ValueError("Google OAuth credentials are not configured.")

        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cls.TOKEN_ENDPOINT, data=data)
            if resp.status_code != 200:
                logger.error(f"Google token exchange failed: {resp.status_code} - {resp.text}")
                raise ValueError(f"Failed to exchange Google OAuth code: {resp.text}")
            
            token_data = resp.json()
            expires_in = token_data.get("expires_in", 3600)
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": expires_in,
                "token_expiry": token_expiry,
                "scope": token_data.get("scope", "").split(" "),
                "token_type": token_data.get("token_type", "Bearer")
            }

    @classmethod
    async def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """
        Refreshes an expired Google access token using the stored refresh token.
        """
        if not cls.is_configured():
            raise ValueError("Google OAuth credentials are not configured.")

        data = {
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cls.TOKEN_ENDPOINT, data=data)
            if resp.status_code != 200:
                logger.error(f"Google token refresh failed: {resp.status_code} - {resp.text}")
                raise ValueError(f"Failed to refresh Google access token: {resp.text}")

            token_data = resp.json()
            expires_in = token_data.get("expires_in", 3600)
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": token_data.get("access_token"),
                "token_expiry": token_expiry,
                "expires_in": expires_in
            }

    @classmethod
    async def get_user_email(cls, access_token: str) -> Optional[str]:
        """
        Retrieves user email from Google UserInfo endpoint.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(cls.USERINFO_ENDPOINT, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("email")
        except Exception as e:
            logger.error(f"Failed to fetch Google userinfo: {e}")
        return None
