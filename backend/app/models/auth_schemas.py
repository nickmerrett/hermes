"""Pydantic schemas for authentication"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role types"""
    PLATFORM_ADMIN = "platform_admin"
    USER = "user"


# Auth Request/Response Schemas
class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """JWT token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires


class RefreshRequest(BaseModel):
    """Token refresh request schema"""
    refresh_token: str


# User Schemas
class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a user"""
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response (excludes password)"""
    id: int
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Schema for list of users response"""
    users: List[UserResponse]
    total: int


# RSS Token Schemas
class RSSTokenBase(BaseModel):
    """Base RSS token schema"""
    name: str = Field(min_length=1, max_length=255)
    customer_id: int


class RSSTokenCreate(RSSTokenBase):
    """Schema for creating an RSS token"""
    pass


class RSSTokenResponse(RSSTokenBase):
    """Schema for RSS token response"""
    id: int
    token: str
    user_id: int
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    customer_name: Optional[str] = None  # Populated from join
    rss_url: Optional[str] = None  # Computed field for convenience

    model_config = ConfigDict(from_attributes=True)


class RSSTokenListResponse(BaseModel):
    """Schema for list of RSS tokens response"""
    tokens: List[RSSTokenResponse]
    total: int
