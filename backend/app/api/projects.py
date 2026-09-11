"""Project management endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import schemas
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.security import TokenPayload

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.Project],
    summary="List the caller's projects",
)
async def list_projects(
    user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Return the current user's projects."""
    rows = db.execute(
        text("SELECT * FROM projects WHERE owner_id = :owner ORDER BY id"),
        {"owner": int(user.uid)},
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
    user: TokenPayload = Depends(get_current_user),
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
            "owner": int(user.uid),
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


@router.get(
    "/{project_id}",
    response_model=schemas.Project,
    summary="Fetch a single project owned by the caller",
)
async def get_project(
    project_id: int,
    user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Return one of the caller's projects by id."""
    row = db.execute(
        text("SELECT * FROM projects WHERE id = :id AND owner_id = :owner"),
        {"id": project_id, "owner": int(user.uid)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found.")
    return schemas.Project(**dict(row))