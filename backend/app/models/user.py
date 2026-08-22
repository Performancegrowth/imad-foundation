"""User model — mirrors the ``users`` table in database/schema.sql."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """Application role levels (kept minimal for Sprint 0)."""

    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    organization: Optional[str] = None
    locale: str = "en"  # 'en' | 'ar'
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    """Payload used at registration time."""

    password: str = Field(min_length=10, max_length=256)
    role: UserRole = UserRole.ENGINEER


class User(UserBase):
    """Full user record as stored in the database."""

    id: int
    hashed_password: str
    role: UserRole = UserRole.ENGINEER
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UserPublic(UserBase):
    """PII-free projection safe to return to clients."""

    id: int
    role: UserRole = UserRole.ENGINEER

    class Config:
        orm_mode = True