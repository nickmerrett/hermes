"""Authentication API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.limiter import limiter

from app.core.database import get_db
from app.core.auth import (
    password_hash,
    password_verify,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_jwt_configured
)
from app.models.database import User
from app.models.auth_schemas import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserRole
)
from app.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user_from_token(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.
    Raises HTTPException if token is invalid or user not found.
    """
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


def require_platform_admin(current_user: User = Depends(get_current_user_from_token)) -> User:
    """Require the current user to be a platform admin"""
    if current_user.role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required"
        )
    return current_user


def ensure_bootstrap_admin(db: Session):
    """Create the bootstrap admin user if no users exist and credentials are configured"""
    # Check if any users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return

    # Check if bootstrap credentials are configured
    if not settings.first_admin_email or not settings.first_admin_password:
        logger.warning("No users exist and FIRST_ADMIN_EMAIL/FIRST_ADMIN_PASSWORD not configured")
        return

    # Create the bootstrap admin
    admin = User(
        email=settings.first_admin_email,
        hashed_password=password_hash(settings.first_admin_password),
        role=UserRole.PLATFORM_ADMIN.value,
        is_active=True
    )
    db.add(admin)
    db.commit()
    logger.info(f"Created bootstrap admin user: {settings.first_admin_email}")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    login_request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens

    Returns access_token and refresh_token on successful authentication.
    """
    if not is_jwt_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured. Set JWT_SECRET_KEY environment variable."
        )

    # Ensure bootstrap admin exists
    ensure_bootstrap_admin(db)

    # Find user by email
    user = db.query(User).filter(User.email == login_request.email).first()
    if not user:
        # Always run bcrypt to prevent timing-based email enumeration
        password_verify("dummy", "$2b$12$KIXqFakeHashForTimingProtection")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not password_verify(login_request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create tokens
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token

    Returns new access_token and refresh_token.
    """
    payload = decode_token(refresh_request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Verify user still exists and is active
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )

    # Create new tokens
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_user_from_token)
):
    """Get the current authenticated user's information"""
    return current_user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only)

    Only platform admins can create new users.
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == user_create.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = User(
        email=user_create.email,
        hashed_password=password_hash(user_create.password),
        role=user_create.role.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"User created: {user.email} (role: {user.role}) by admin {current_user.email}")
    return user


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only)

    Returns all users in the system.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return UserListResponse(users=users, total=len(users))


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Get a specific user (admin only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Update a user (admin only)

    Platform admins can update any user's email, password, role, or active status.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent disabling the last admin
    if user_update.is_active is False and user.role == UserRole.PLATFORM_ADMIN.value:
        admin_count = db.query(User).filter(
            User.role == UserRole.PLATFORM_ADMIN.value,
            User.is_active.is_(True),
            User.id != user_id
        ).count()
        if admin_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disable the last active admin"
            )

    # Prevent demoting the last admin
    if user_update.role and user_update.role != UserRole.PLATFORM_ADMIN and user.role == UserRole.PLATFORM_ADMIN.value:
        admin_count = db.query(User).filter(
            User.role == UserRole.PLATFORM_ADMIN.value,
            User.is_active.is_(True),
            User.id != user_id
        ).count()
        if admin_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active admin"
            )

    # Update fields
    if user_update.email is not None:
        # Check if email already exists
        existing = db.query(User).filter(User.email == user_update.email, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = user_update.email

    if user_update.password is not None:
        user.hashed_password = password_hash(user_update.password)

    if user_update.role is not None:
        user.role = user_update.role.value

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    db.commit()
    db.refresh(user)

    logger.info(f"User updated: {user.email} by admin {current_user.email}")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a user (admin only)

    Cannot delete yourself or the last active admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Cannot delete yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    # Cannot delete the last admin
    if user.role == UserRole.PLATFORM_ADMIN.value:
        admin_count = db.query(User).filter(
            User.role == UserRole.PLATFORM_ADMIN.value,
            User.is_active.is_(True),
            User.id != user_id
        ).count()
        if admin_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last active admin"
            )

    logger.info(f"User deleted: {user.email} by admin {current_user.email}")
    db.delete(user)
    db.commit()

    return None
