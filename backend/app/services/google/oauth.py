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


class GoogleOAuthCore:
    """
    Shared Google OAuth Core responsible for:
    - Service scope management
    - Cryptographic state generation & verification with service binding
    - Expiration & single-use nonce tracking
    - Authorization code exchange
    - Token refresh management
    - Google user email resolution
    """
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

    VALID_SERVICES = {
        "business_profile": "Google Business Profile",
        "google_ads": "Google Ads",
        "search_console": "Google Search Console",
        "analytics": "Google Analytics 4"
    }

    SERVICE_SCOPES = {
        "business_profile": [
            "https://www.googleapis.com/auth/business.manage",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        "google_ads": [
            "https://www.googleapis.com/auth/adwords",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        "search_console": [
            "https://www.googleapis.com/auth/webmasters.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        "analytics": [
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ]
    }

    @classmethod
    def is_configured(cls) -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    @classmethod
    def get_service_scopes(cls, service: str) -> List[str]:
        if service not in cls.SERVICE_SCOPES:
            raise ValueError(f"Unsupported Google service '{service}'. Must be one of: {list(cls.VALID_SERVICES.keys())}")
        return cls.SERVICE_SCOPES[service]

    @classmethod
    def encode_oauth_state(
        cls,
        service: str = "business_profile",
        project_id: int = 0,
        user_id: int = 0,
        organization_id: int = 0,
        custom_state: Optional[str] = None
    ) -> str:
        """
        Creates a cryptographically-signed JWT OAuth state to prevent CSRF, parameter tampering, and cross-service replay attacks.
        Strictly binds user_id, organization_id, and service name.
        """
        if service not in cls.VALID_SERVICES:
            raise ValueError(f"Invalid Google service for OAuth state: {service}")

        now = datetime.now(timezone.utc)
        nonce = str(uuid.uuid4())
        payload = {
            "provider": "google",
            "service": service,
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
    def decode_and_validate_oauth_state(
        cls,
        state_str: str,
        expected_service: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Decodes and verifies cryptographic signature, expiry, service binding, and one-time nonce of OAuth state.
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
            logger.warning(f"[OAUTH] State signature validation failed: {e}")
            raise ValueError(f"Invalid or tampered OAuth state: {str(e)}")

        nonce = payload.get("nonce")
        if not nonce or nonce in _USED_NONCES:
            logger.warning(f"[OAUTH] Replay attack detected for nonce: {nonce}")
            raise ValueError("OAuth state has already been used or is invalid.")

        provider = payload.get("provider")
        if provider != "google":
            raise ValueError(f"Invalid OAuth provider '{provider}'. Expected 'google'.")

        service = payload.get("service")
        if not service or service not in cls.VALID_SERVICES:
            raise ValueError(f"Invalid or unsupported Google service in OAuth state: '{service}'")

        if expected_service and service != expected_service:
            raise ValueError(f"OAuth state service mismatch: state is for '{service}', endpoint expected '{expected_service}'.")

        # Mark nonce as used
        _USED_NONCES[nonce] = now + timedelta(minutes=20)
        return payload

    @classmethod
    def get_authorization_url(
        cls,
        service: str = "business_profile",
        project_id: int = 0,
        user_id: int = 0,
        organization_id: int = 0,
        custom_state: Optional[str] = None,
        prompt: Optional[str] = "select_account"
    ) -> str:
        """
        Builds the service-specific Google OAuth 2.0 authorization URL with requesting scopes strictly limited to the target service.
        """
        if not cls.is_configured():
            logger.warning("[OAUTH] Google OAuth credentials are not configured in settings.")

        scopes = cls.get_service_scopes(service)
        signed_state = cls.encode_oauth_state(
            service=service,
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            custom_state=custom_state
        )

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": prompt or "select_account",
            "include_granted_scopes": "true",
            "state": signed_state
        }

        query_str = urllib.parse.urlencode(params)
        logger.info(f"[OAUTH] service={service} stage=authorization_started user_id={user_id} org_id={organization_id}")
        return f"{cls.AUTH_ENDPOINT}?{query_str}"

    @classmethod
    async def exchange_code_for_tokens(cls, code: str) -> Dict[str, Any]:
        """
        Exchanges an OAuth 2.0 authorization code for an access token, refresh token, and user identity.
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
                logger.error(f"[OAUTH] Token exchange failed: {resp.status_code} - {resp.text}")
                raise ValueError(f"Failed to exchange Google OAuth code: {resp.text}")
            
            token_data = resp.json()
            expires_in = token_data.get("expires_in", 3600)
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            access_token = token_data.get("access_token")

            user_email = None
            if access_token:
                user_email = await cls.get_user_email(access_token)

            return {
                "access_token": access_token,
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": expires_in,
                "token_expiry": token_expiry,
                "scopes": token_data.get("scope", "").split(" ") if token_data.get("scope") else [],
                "token_type": token_data.get("token_type", "Bearer"),
                "email": user_email
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
                logger.error(f"[OAUTH] Token refresh failed: {resp.status_code} - {resp.text}")
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
            logger.error(f"[OAUTH] Failed to fetch Google userinfo: {e}")
        return None


# Individual Service Connectors using GoogleOAuthCore
class BusinessProfileConnector:
    SERVICE_KEY = "business_profile"
    SERVICE_NAME = "Google Business Profile"

    @classmethod
    def get_scopes(cls) -> List[str]:
        return GoogleOAuthCore.get_service_scopes(cls.SERVICE_KEY)

    @classmethod
    def get_authorization_url(cls, project_id: int, user_id: int, organization_id: int, **kwargs) -> str:
        return GoogleOAuthCore.get_authorization_url(
            service=cls.SERVICE_KEY,
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            **kwargs
        )


class GoogleAdsConnector:
    SERVICE_KEY = "google_ads"
    SERVICE_NAME = "Google Ads"

    @classmethod
    def get_scopes(cls) -> List[str]:
        return GoogleOAuthCore.get_service_scopes(cls.SERVICE_KEY)

    @classmethod
    def get_authorization_url(cls, project_id: int, user_id: int, organization_id: int, **kwargs) -> str:
        return GoogleOAuthCore.get_authorization_url(
            service=cls.SERVICE_KEY,
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            **kwargs
        )


class SearchConsoleConnector:
    SERVICE_KEY = "search_console"
    SERVICE_NAME = "Google Search Console"

    @classmethod
    def get_scopes(cls) -> List[str]:
        return GoogleOAuthCore.get_service_scopes(cls.SERVICE_KEY)

    @classmethod
    def get_authorization_url(cls, project_id: int, user_id: int, organization_id: int, **kwargs) -> str:
        return GoogleOAuthCore.get_authorization_url(
            service=cls.SERVICE_KEY,
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            **kwargs
        )


class AnalyticsConnector:
    SERVICE_KEY = "analytics"
    SERVICE_NAME = "Google Analytics 4"

    @classmethod
    def get_scopes(cls) -> List[str]:
        return GoogleOAuthCore.get_service_scopes(cls.SERVICE_KEY)

    @classmethod
    def get_authorization_url(cls, project_id: int, user_id: int, organization_id: int, **kwargs) -> str:
        return GoogleOAuthCore.get_authorization_url(
            service=cls.SERVICE_KEY,
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            **kwargs
        )


# Backward compatibility alias
GoogleOAuthService = GoogleOAuthCore
