import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

logger = logging.getLogger("locallift.config")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

INSECURE_DEFAULT_KEYS = {
    "locallift-super-secret-key-production-change-me-12345",
    "change-me",
    "secret",
    "change-this-to-a-secure-random-secret-key",
    "replace-with-a-secure-random-secret-key-for-production",
    "default-secret-key-12345"
}

class Settings(BaseSettings):
    PROJECT_NAME: str = "LocalLift"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # production, development, testing
    ALLOW_DEV_SEEDING: bool = False
    
    # Security
    SECRET_KEY: str = "locallift-super-secret-key-production-change-me-12345"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./locallift.db"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
    
    # Integrations - Google Platform
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/integrations/google/callback"
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    
    # Integrations - SERP / Rank Tracking
    SERP_PROVIDER: str = "openserp"  # openserp (default self-hosted), serpapi, mock (testing only)
    OPENSERP_BASE_URL: str = "http://127.0.0.1:7000"
    OPENSERP_TIMEOUT: int = 30
    OPENSERP_DEFAULT_ENGINE: str = "google"
    SERP_FALLBACK_PROVIDER: str = "serpapi"  # serpapi fallback when enabled
    SERPAPI_KEY: str = ""
    
    # AI Engine
    AI_PROVIDER: str = "rule_based"  # rule_based, gemini, openai
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-1.5-flash"
    
    def validate_production_security(self) -> None:
        """Fails fast if production uses insecure or default credentials."""
        env = self.ENVIRONMENT.strip().lower()
        if env == "production":
            if (
                not self.SECRET_KEY
                or self.SECRET_KEY in INSECURE_DEFAULT_KEYS
                or len(self.SECRET_KEY) < 32
            ):
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "In production environment, SECRET_KEY must be explicitly set to a strong, "
                    "secure secret (at least 32 characters). Startup aborted."
                )
            # Ensure CORS origins are not wildcard in production
            for origin in self.BACKEND_CORS_ORIGINS:
                if origin == "*":
                    raise RuntimeError(
                        "CRITICAL SECURITY CONFIGURATION ERROR: "
                        "Wildcard '*' in BACKEND_CORS_ORIGINS is prohibited when allow_credentials=True in production."
                    )
        elif env == "development":
            if self.SECRET_KEY in INSECURE_DEFAULT_KEYS:
                logger.warning(
                    "SECURITY NOTICE: LocalLift is using a default development SECRET_KEY. "
                    "Set a unique SECRET_KEY before deploying to production."
                )

    class Config:
        case_sensitive = True
        env_file = (
            str(ROOT_DIR / ".env"),
            str(BACKEND_DIR / ".env"),
            ".env",
        )
        extra = "ignore"

def validate_production_security(custom_settings: Settings = None) -> None:
    s = custom_settings or settings
    s.validate_production_security()

settings = Settings()
settings.validate_production_security()
