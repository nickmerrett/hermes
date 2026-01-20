"""FastAPI dependencies for authentication"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.auth import decode_token, is_jwt_configured
from app.models.database import User
from app.models.auth_schemas import UserRole

# OAuth2 scheme for token extraction (auto_error=False allows optional auth)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.

    This is the main dependency for protecting routes.
    Raises 401 if token is missing, invalid, or user not found.
    """
    # If auth is not configured, allow access (development mode)
    if not is_jwt_configured():
        # Return a mock admin user for development
        return User(
            id=0,
            email="dev@localhost",
            role=UserRole.PLATFORM_ADMIN.value,
            is_active=True
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.

    Use this for endpoints that work both with and without authentication.
    """
    if not is_jwt_configured() or not token:
        return None

    try:
        return get_current_user(token, db)
    except HTTPException:
        return None


def require_platform_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require the current user to be a platform admin.

    Use as a dependency for admin-only endpoints.
    """
    if current_user.role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required"
        )
    return current_user


def require_user_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require any authenticated user (either user or admin role).

    This is equivalent to get_current_user, but makes the intent clearer
    when used alongside require_platform_admin.
    """
    return current_user
