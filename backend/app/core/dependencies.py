"""Shared FastAPI dependencies for authentication and authorization.

Canonical home for ``get_current_user`` / ``require_owner`` so every router
enforces the same bearer-token + ownership checks.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_session
from app.core.security import TokenPayload, decode_access_token


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> TokenPayload:
    """Authenticate a request from its ``Authorization: Bearer <token>`` header.

    Returns the decoded token claims (``.uid`` = user id, ``.sub`` = email).
    Raises 401 when missing, malformed, expired or forged.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw = authorization.split(" ", 1)[1].strip()
    try:
        return decode_access_token(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_owner(
    project_id: int,
    user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> TokenPayload:
    """Raise 404 unless the authenticated user owns the given project.

    404 (not 403) avoids leaking the existence of other users' projects.
    Returns the user claims so callers can chain the dependency.
    """
    row = db.execute(
        text("SELECT id FROM projects WHERE id = :id AND owner_id = :owner"),
        {"id": project_id, "owner": int(user.uid)},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found.")
    return user


def verify_project_owner(
    project_id: int,
    user: TokenPayload,
    db: Session,
) -> None:
    """Raise 404 unless ``user`` owns the SQL project ``project_id``.

    For routes whose ``project_id`` arrives inside a JSON body (and therefore
    cannot be injected via ``Depends``), callers resolve ownership themselves
    with this helper. 404 (not 403) avoids leaking existence.
    """
    row = db.execute(
        text("SELECT id FROM projects WHERE id = :id AND owner_id = :owner"),
        {"id": project_id, "owner": int(user.uid)},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found.")
