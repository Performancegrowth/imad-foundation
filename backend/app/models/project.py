"""Project model — mirrors the ``projects`` table."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None
    project_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    design_standard: str = "ACI 318-19"


class ProjectCreate(ProjectBase):
    pass


class Project(ProjectBase):
    """Full project row returned by the API."""

    id: int
    owner_id: int
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True