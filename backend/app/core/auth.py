"""Authentication utilities - JWT tokens, password hashing, and API keys"""

from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
from jose import JWTError, jwt
from passlib.context import CryptContext
import hashlib
import secrets
import logging

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def password_verify(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary with claims to encode (should include 'sub' for user id)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token

    Args:
        data: Dictionary with claims to encode (should include 'sub' for user id)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token

    Args:
        token: The JWT token string

    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None


def is_jwt_configured() -> bool:
    """Check if JWT secret key is configured"""
    return bool(settings.jwt_secret_key)


def generate_api_key() -> tuple[str, str]:
    """Generate a new hrm_ API key. Returns (full_key, key_hash)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"hrm_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_hash


def verify_api_key(key: str, db: "Session") -> Optional[object]:
    """Verify an hrm_ API key and return the associated User, or None."""
    from app.models.database import ApiKey, User
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if not api_key:
        return None
    api_key.last_used = datetime.utcnow()
    db.commit()
    return db.query(User).filter(User.id == api_key.user_id, User.is_active.is_(True)).first()
