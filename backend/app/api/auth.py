"""Authentication endpoints.

Sprint 0 exposes contracts only — registration and token issuance validate
requests and return structured ``501 Not Implemented`` until Sprint 1 wires
them to the database + JWT security module.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app import schemas

router = APIRouter()


@router.post(
    "/register",
    response_model=schemas.UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account (Sprint 1)",
)
async def register(payload: schemas.UserCreate):
    """Contract only. Persistence + hashing arrive in Sprint 1."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Registration is implemented in Sprint 1.",
    )


@router.post(
    "/token",
    response_model=schemas.TokenResponse,
    summary="Exchange credentials for a JWT (Sprint 1)",
)
async def token(payload: schemas.LoginRequest):
    """Contract only. Real session issuance arrives in Sprint 1."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token issuance is implemented in Sprint 1.",
    )


@router.post(
    "/refresh",
    response_model=schemas.TokenResponse,
    summary="Rotate a refresh token (Sprint 1)",
)
async def refresh(payload: schemas.RefreshRequest):
    """Contract only. Token rotation arrives in Sprint 1."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Refresh tokens are implemented in Sprint 1.",
    )