"""Plan model — BOQ / structural / sustainability / cost plans.

Mirrors the ``plans`` table in database/schema.sql.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PlanKind(str, Enum):
    BOQ = "boq"
    STRUCTURAL = "structural"
    SUSTAINABILITY = "sustainability"
    COST = "cost"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    GENERATED = "generated"
    ARCHIVED = "archived"


class PlanLineItem(BaseModel):
    """A single row inside a plan (e.g. one BOQ line)."""

    code: str
    description: str
    quantity: float = 0
    unit: str = "ea"
    unit_price: float = 0
    total: float = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    """A generated or drafted engineering plan."""

    id: int
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    kind: PlanKind = PlanKind.BOQ
    status: PlanStatus = PlanStatus.DRAFT
    items_total: int = 0
    total_amount: float = 0
    currency: str = "USD"
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PlanCreate(BaseModel):
    """Payload for creating a new plan draft."""

    project_id: int
    name: str
    kind: PlanKind = PlanKind.BOQ
    currency: str = "USD"