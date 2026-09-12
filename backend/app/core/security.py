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

def _get_fernet_suite() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    b64_key = base64.urlsafe_b64encode(key)
    return Fernet(b64_key)

def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    if not plain_token:
        return None
    try:
        suite = _get_fernet_suite()
        return suite.encrypt(plain_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        return plain_token

def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    if not encrypted_token:
        return None
    try:
        suite = _get_fernet_suite()
        return suite.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # Fallback for legacy plaintext token gracefully
        return encrypted_token

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

