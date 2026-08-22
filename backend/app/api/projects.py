"""Project management endpoints (CRUD lands in Sprint 1)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.core.database import get_session
from app.core.security import decode_access_token
from app.models import Project

router = APIRouter()


def _read_bearer(authorization: str = Header(...)) -> str:
    """Extract + decode a bearer token from the Authorization header."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Malformed bearer token")
    raw = authorization.split(" ", 1)[1]
    decode_access_token(raw)  # raises on expiry/forged signature
    return raw


@router.get(
    "",
    response_model=List[schemas.Project],
    summary="List projects (placeholder, secured)",
)
async def list_projects(
    token_payload: str = Depends(_read_bearer),
    db: Session = Depends(get_session),
):
    """Return the current user's projects.

    Sprint 0 returns an empty list because storage is not yet wired; the
    dependency chain (auth + db session) is fully exercised here.
    """
    # Sprint 1: filter by owner from token claims.
    return []