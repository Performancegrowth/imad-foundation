"""Authentication & response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models import UserPublic


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class Token(BaseModel):
    """A signed JWT returned on successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry
    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    """Answer for login / token-exchange endpoints."""

    token: Token
    user: UserPublic