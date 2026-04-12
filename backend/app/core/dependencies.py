"""FastAPI dependencies for authentication and customer access control"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.core.auth import decode_token, is_jwt_configured
from app.config.settings import settings
from app.models.database import User, Customer, CustomerAccess
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
    # If auth is not configured, allow access in development only
    if not is_jwt_configured():
        if not settings.is_development:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured. Set JWT_SECRET_KEY environment variable.",
            )
        # Return a mock admin user for local development only
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


# ---------------------------------------------------------------------------
# Customer access helpers
# ---------------------------------------------------------------------------

def _is_dev_mock(user: User) -> bool:
    return user.id == 0


def get_accessible_customer_ids(user: User, db: Session) -> Optional[List[int]]:
    """
    Returns None for the dev mock user (unrestricted).
    Otherwise returns the list of customer IDs the user owns or has been
    explicitly shared with.
    """
    if _is_dev_mock(user):
        return None

    owned = db.query(Customer.id).filter(Customer.owner_id == user.id).all()
    shared = db.query(CustomerAccess.customer_id).filter(
        CustomerAccess.user_id == user.id
    ).all()
    # NULL owner_id = legacy unowned rows visible to everyone
    unowned = db.query(Customer.id).filter(Customer.owner_id.is_(None)).all()

    ids = (
        {r.id for r in owned}
        | {r.customer_id for r in shared}
        | {r.id for r in unowned}
    )
    return list(ids)


def get_customer_access(customer_id: int, user: User, db: Session) -> Optional[CustomerAccess]:
    """Return the CustomerAccess row for this user, or None if they are the owner / dev mock."""
    if _is_dev_mock(user):
        return None
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer and (customer.owner_id == user.id or customer.owner_id is None):
        return None  # owner or legacy unowned — full access
    return db.query(CustomerAccess).filter(
        CustomerAccess.customer_id == customer_id,
        CustomerAccess.user_id == user.id
    ).first()


def check_customer_access(customer_id: int, user: User, db: Session) -> None:
    """Raises 403 if the user has no access to this customer at all."""
    if _is_dev_mock(user):
        return
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.owner_id == user.id or customer.owner_id is None:
        return
    has_access = db.query(CustomerAccess).filter(
        CustomerAccess.customer_id == customer_id,
        CustomerAccess.user_id == user.id
    ).first()
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this customer")


def check_customer_admin(customer_id: int, user: User, db: Session) -> None:
    """Raises 403 unless user is owner (or legacy unowned) or has can_admin=True."""
    if _is_dev_mock(user):
        return
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.owner_id == user.id or customer.owner_id is None:
        return
    access = db.query(CustomerAccess).filter(
        CustomerAccess.customer_id == customer_id,
        CustomerAccess.user_id == user.id,
        CustomerAccess.can_admin.is_(True)
    ).first()
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this customer"
        )


def check_customer_reshare(customer_id: int, user: User, db: Session) -> Optional[CustomerAccess]:
    """
    Raises 403 unless user is owner (or legacy unowned) or has can_reshare=True.
    Returns the CustomerAccess row (for permission-capping), or None if owner.
    """
    if _is_dev_mock(user):
        return None
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.owner_id == user.id or customer.owner_id is None:
        return None  # owner — unrestricted, no cap needed
    access = db.query(CustomerAccess).filter(
        CustomerAccess.customer_id == customer_id,
        CustomerAccess.user_id == user.id,
        CustomerAccess.can_reshare.is_(True)
    ).first()
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Share permission required for this customer"
        )
    return access
