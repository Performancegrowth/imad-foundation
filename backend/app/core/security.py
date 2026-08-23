"""
Security helpers: password hashing + JWT creation/verification.

Sprint 0 ships a working, dependency-light implementation (passlib removed in
favour of stdlib ``hashlib`` PBKDF2). Sprint 1 will layer refresh tokens and
role claims on top of this module.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pydantic import BaseModel

from .config import get_settings

_jwt_algorithms = {"HS256"}  # locked set; add algorithms deliberately only

# ---------------------------------------------------------------- hashing --
def hash_password(password: str) -> str:
    """Return a PBKDF2-HMAC-SHA256 hex digest with a random salt.

    Format: ``pbkdf2$<rounds>$<salt_hex>$<hash_hex>``.
    """
    rounds = 260_000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), rounds)
    return f"pbkdf2${rounds}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification against the ``hash_password`` output."""
    try:
        scheme, rounds_s, salt, expected = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    rounds = int(rounds_s)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), rounds)
    return hmac.compare_digest(digest.hex(), expected)


# ------------------------------------------------------------------------- jwt --
class TokenPayload(BaseModel):
    """Shape of the claims encoded inside an Imad access token."""

    sub: str                      # user email
    uid: int                      # user id
    exp: int
    iat: int
    jti: str                      # unique token id (revocation readiness)


def create_access_token(subject_id: int, email: str) -> str:
    """Create a signed HS256 access token for the given user."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "uid": subject_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode + validate a token, raising on expiry / bad signature."""
    settings = get_settings()
    raw = jwt.decode(token, settings.SECRET_KEY, algorithms=_jwt_algorithms)
    return TokenPayload(**raw)


def get_current_user(authorization: Optional[str] = None) -> TokenPayload:
    """FastAPI-friendly dependency returning the authenticated token claims.

    Reads the ``Authorization: Bearer <token>`` header and raises a 401 when
    missing, malformed, expired or forged. Sprint 1 will resolve the user row
    from the DB using ``TokenPayload.uid``.
    """
    from fastapi import HTTPException, status

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw = authorization.split(" ", 1)[1].strip()
    try:
        return decode_access_token(raw)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )