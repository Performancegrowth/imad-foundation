"""Project management endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import schemas
from app.core.database import get_session
from app.core.security import decode_access_token

router = APIRouter()


def _current_uid(authorization: str = Header(...)) -> int:
    """Extract + decode a bearer token; return the authenticated user id."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Malformed bearer token")
    raw = authorization.split(" ", 1)[1].strip()
    try:
        return int(decode_access_token(raw).uid)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "",
    response_model=List[schemas.Project],
    summary="List the caller's projects",
)
async def list_projects(
    owner_id: int = Depends(_current_uid),
    db: Session = Depends(get_session),
):
    """Return the current user's projects."""
    rows = db.execute(
        text("SELECT * FROM projects WHERE owner_id = :owner ORDER BY id"),
        {"owner": owner_id},
    ).mappings().all()
    return [schemas.Project(**dict(r)) for r in rows]


@router.post(
    "",
    response_model=schemas.Project,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project for the current user",
)
async def create_project(
    payload: schemas.ProjectCreate,
    owner_id: int = Depends(_current_uid),
    db: Session = Depends(get_session),
):
    """Create a project owned by the authenticated user."""
    result = db.execute(
        text(
            "INSERT INTO projects "
            "(owner_id, name, description, project_code, city, country, "
            " latitude, longitude, status, design_standard) "
            "VALUES (:owner, :name, :desc, :code, :city, :country, "
            "        :lat, :lng, 'draft', :standard)"
        ),
        {
            "owner": owner_id,
            "name": payload.name,
            "desc": payload.description,
            "code": payload.project_code,
            "city": payload.city,
            "country": payload.country,
            "lat": payload.latitude,
            "lng": payload.longitude,
            "standard": payload.design_standard or "ACI 318-19",
        },
    )
    db.commit()
    row = db.execute(
        text("SELECT * FROM projects WHERE id = :id"), {"id": int(result.lastrowid)}
    ).mappings().first()
    return schemas.Project(**dict(row))