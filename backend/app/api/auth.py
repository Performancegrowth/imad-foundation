"""Authentication endpoints: register, token (login) and refresh.

Backed by SQLAlchemy Core over ``database/schema.sql``. Passwords use the
dependency-light PBKDF2 helper in ``core.security`` (no passlib needed).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter()
_settings = get_settings()


def _build_issued(row) -> schemas.TokenResponse:
    """Build an authenticated response (token + user) from a users row."""
    row = dict(row)
    uid = int(row["id"])
    email = str(row["email"])
    access = create_access_token(uid, email)
    role = row.get("role") or schemas.UserRole.ENGINEER.value
    user = schemas.UserPublic(
        id=uid,
        email=email,
        full_name=str(row["full_name"]),
        role=role,
        organization=row.get("organization"),
        locale=row.get("locale") or "en",
        is_active=bool(row.get("is_active", True)),
        is_superuser=bool(row.get("is_superuser", False)),
    )
    return schemas.TokenResponse(
        token=schemas.Token(
            access_token=access,
            token_type="bearer",
            expires_in=int(_settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
            refresh_token=access,  # simple reuse until rotation lands
        ),
        user=user,
    )


@router.post(
    "/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and return a token",
)
async def register(payload: schemas.UserCreate, db: Session = Depends(get_session)):
    """Register a new user (hashes the password, persists, issues a token)."""
    email = str(payload.email).strip().lower()

    duplicate = db.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": email}
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    hashed = hash_password(payload.password)
    role = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    result = db.execute(
        text(
            "INSERT INTO users "
            "(email, full_name, hashed_password, is_active, is_superuser, "
            " organization, locale, role) "
            "VALUES (:email, :full_name, :hashed, :active, :super, "
            "        :org, :locale, :role)"
        ),
        {
            "email": email,
            "full_name": payload.full_name,
            "hashed": hashed,
            "active": 1 if payload.is_active else 0,
            "super": 1 if payload.is_superuser else 0,
            "org": payload.organization,
            "locale": payload.locale or "en",
            "role": role,
        },
    )
    db.commit()
    uid = int(result.lastrowid)
    row = db.execute(
        text("SELECT * FROM users WHERE id = :id"), {"id": uid}
    ).mappings().first()
    return _build_issued(row)


@router.post(
    "/token",
    response_model=schemas.TokenResponse,
    summary="Exchange email/password for a JWT",
)
async def token(payload: schemas.LoginRequest, db: Session = Depends(get_session)):
    """Verify credentials and issue an access token."""
    email = str(payload.email).strip().lower()
    row = db.execute(
        text("SELECT * FROM users WHERE email = :email"), {"email": email}
    ).mappings().first()
    if not row or not verify_password(payload.password, row["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _build_issued(row)


@router.post(
    "/refresh",
    response_model=schemas.TokenResponse,
    summary="Rotate a (refresh) token",
)
async def refresh(payload: schemas.RefreshRequest, db: Session = Depends(get_session)):
    """Accept a token and issue a fresh one for the same user."""
    try:
        claims = decode_access_token(payload.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )
    row = db.execute(
        text("SELECT * FROM users WHERE id = :id"), {"id": claims.uid}
    ).mappings().first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
        )
    return _build_issued(row)