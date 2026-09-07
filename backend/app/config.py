import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "LocalLift"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production"  # production, development, testing
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
        "http://127.0.0.1:3000"
    ]
    
    # Integrations - Google Platform
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/integrations/google/callback"
    
    # Integrations - SERP / Rank Tracking
    SERP_PROVIDER: str = "serpapi"  # serpapi, mock
    SERPAPI_KEY: str = ""
    
    # AI Engine
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-1.5-pro"
    
    def validate_production_security(self) -> None:
        """Fails fast or logs warnings if production uses insecure defaults."""
        if self.ENVIRONMENT.lower() == "production" and self.SECRET_KEY == "locallift-super-secret-key-production-change-me-12345":
            import logging
            logging.getLogger("locallift.security").warning(
                "SECURITY WARNING: Running in production environment with default SECRET_KEY. "
                "Please configure SECRET_KEY in your production environment variables."
            )

    class Config:
        case_sensitive = True
        env_file = (
            str(ROOT_DIR / ".env"),
            str(BACKEND_DIR / ".env"),
            ".env",
        )
        extra = "ignore"

settings = Settings()
settings.validate_production_security()
