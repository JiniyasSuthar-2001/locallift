import urllib.parse
import json
import logging
import uuid
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from app.config import settings

logger = logging.getLogger("locallift.google.oauth")

# In-memory nonce cache to prevent OAuth replay attacks (stores nonces with expiration)
_USED_NONCES: Dict[str, datetime] = {}

class GoogleOAuthService:
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

    DEFAULT_SCOPES = [
        "https://www.googleapis.com/auth/business.manage",
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/analytics.readonly",
        "https://www.googleapis.com/auth/adwords",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid"
    ]

    @classmethod
    def is_configured(cls) -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    @classmethod
    def encode_oauth_state(
        cls,
        project_id: int,
        user_id: int,
        organization_id: int,
        custom_state: Optional[str] = None
    ) -> str:
        """
        Creates a cryptographically-signed JWT OAuth state to prevent CSRF and parameter tampering.
        """
        now = datetime.now(timezone.utc)
        nonce = str(uuid.uuid4())
        payload = {
            "project_id": project_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "nonce": nonce,
            "custom": custom_state,
            "iat": now,
            "exp": now + timedelta(minutes=15)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @classmethod
    def decode_and_validate_oauth_state(cls, state_str: str) -> Dict[str, Any]:
        """
        Decodes and verifies cryptographic signature, expiry, and one-time nonce of OAuth state.
        """
        if not state_str:
            raise ValueError("OAuth state parameter is missing.")

        # Clean up expired nonces
        now = datetime.now(timezone.utc)
        expired_keys = [k for k, exp in _USED_NONCES.items() if exp < now]
        for k in expired_keys:
            _USED_NONCES.pop(k, None)

        try:
            payload = jwt.decode(
                state_str,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except JWTError as e:
            logger.warning(f"OAuth state signature validation failed: {e}")
            raise ValueError(f"Invalid or tampered OAuth state: {str(e)}")

        nonce = payload.get("nonce")
        if not nonce or nonce in _USED_NONCES:
            logger.warning(f"OAuth state replay attack detected for nonce: {nonce}")
            raise ValueError("OAuth state has already been used or is invalid.")

        # Mark nonce as used
        _USED_NONCES[nonce] = now + timedelta(minutes=20)
        return payload

    @classmethod
    def get_authorization_url(
        cls,
        project_id: int,
        user_id: int,
        organization_id: int = 1,
        custom_state: Optional[str] = None
    ) -> str:
        """
        Builds the Google OAuth 2.0 consent URL with signed state and multi-service scopes.
        """
        if not cls.is_configured():
            logger.warning("Google OAuth credentials are not configured in settings.")

        signed_state = cls.encode_oauth_state(
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            custom_state=custom_state
        )

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(cls.DEFAULT_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": signed_state
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
                "scope": token_data.get("scope", "").split(" ") if token_data.get("scope") else [],
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
