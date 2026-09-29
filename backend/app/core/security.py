import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import bcrypt
from jose import jwt
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings

logger = logging.getLogger("locallift.security")

def _derive_fernet_key(secret_key: str) -> bytes:
    key = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key)

def _get_primary_key_str() -> str:
    key = settings.CURRENT_ENCRYPTION_KEY or settings.SECRET_KEY
    if not key:
        raise RuntimeError("Security configuration error: CURRENT_ENCRYPTION_KEY / SECRET_KEY is not configured")
    return key

def _get_primary_fernet_suite() -> Fernet:
    return Fernet(_derive_fernet_key(_get_primary_key_str()))

def _get_all_fernet_suites() -> list[Fernet]:
    suites = []
    seen_keys = set()
    
    # 1. Primary key (CURRENT_ENCRYPTION_KEY or SECRET_KEY)
    primary_str = _get_primary_key_str()
    if primary_str:
        k = _derive_fernet_key(primary_str)
        suites.append(Fernet(k))
        seen_keys.add(k)
        
    # 2. Configured legacy migration key from environment
    if settings.LEGACY_ENCRYPTION_KEY:
        k = _derive_fernet_key(settings.LEGACY_ENCRYPTION_KEY)
        if k not in seen_keys:
            suites.append(Fernet(k))
            seen_keys.add(k)

    # 3. Development / Test environment fallback keys (excluded in production)
    is_prod = (getattr(settings, "ENVIRONMENT", "development").lower() == "production")
    if not is_prod:
        candidate_secrets = [
            "locallift-production-hardening-secret-key-928471",
            "locallift-super-secret-key-production-change-me-12345",
            "test-legacy-key-for-migration-validation"
        ]
        for cs in candidate_secrets:
            if cs:
                k = _derive_fernet_key(cs)
                if k not in seen_keys:
                    suites.append(Fernet(k))
                    seen_keys.add(k)
                
    return suites

def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    if plain_token is None:
        return None
    if not isinstance(plain_token, str):
        raise TypeError("Token must be a string")
    try:
        suite = _get_primary_fernet_suite()
        return suite.encrypt(plain_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise RuntimeError(f"Token encryption failed: {e}") from e

def is_plaintext_token(token: str) -> bool:
    if not token or not isinstance(token, str):
        return False
    # Google OAuth access tokens start with ya29., refresh tokens start with 1//
    return token.startswith("ya29.") or token.startswith("1//")

def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    if encrypted_token is None:
        return None
    if not isinstance(encrypted_token, str):
        raise TypeError("Encrypted token must be a string")
    
    clean_token = encrypted_token.strip()
    if not clean_token:
        return ""
        
    # If token is stored unencrypted (legacy OAuth callback write), return safely
    if is_plaintext_token(clean_token):
        return clean_token

    # Attempt decryption with primary and fallback Fernet keys
    suites = _get_all_fernet_suites()
    for suite in suites:
        try:
            return suite.decrypt(clean_token.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, base64.binascii.Error):
            continue
            
    # Ciphertext cannot be decrypted with any configured key
    logger.warning("Token decryption notice: unrecoverable or invalid ciphertext.")
    raise ValueError("Invalid or corrupted token ciphertext")

def migrate_token(encrypted_token: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Validates token ciphertext against current primary key.
    If the token was plaintext or encrypted under a legacy key, decrypts it and
    re-encrypts under the current primary key.
    Returns (migrated_ciphertext, was_migrated_bool).
    """
    if not encrypted_token or not encrypted_token.strip():
        return encrypted_token, False

    clean = encrypted_token.strip()
    # Check if decryptable directly with primary key
    primary_suite = _get_primary_fernet_suite()
    try:
        if not is_plaintext_token(clean):
            primary_suite.decrypt(clean.encode("utf-8"))
            return clean, False  # Already encrypted with primary key
    except (InvalidToken, ValueError, base64.binascii.Error):
        pass

    # Token needs migration: decrypt with fallback suite and re-encrypt
    plain = decrypt_token(clean)
    if plain:
        new_encrypted = encrypt_token(plain)
        return new_encrypted, True
    return clean, False

MAX_BCRYPT_BYTES = 72

def validate_password_length(password: str) -> None:
    if not password:
        raise ValueError("Password cannot be empty.")
    if len(password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        raise ValueError(f"Password must not exceed {MAX_BCRYPT_BYTES} bytes in UTF-8 encoding.")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pw_bytes = plain_password.encode("utf-8")
        if len(pw_bytes) > MAX_BCRYPT_BYTES:
            return False
        return bcrypt.checkpw(
            pw_bytes,
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    validate_password_length(password)
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

