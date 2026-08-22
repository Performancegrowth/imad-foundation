"""Design result model — mirrors the ``design_results`` table."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ResultStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DesignResult(BaseModel):
    """Outcome row produced by the structural engine (Sprint 3+)."""

    id: int
    project_id: int
    file_id: Optional[int] = None
    status: ResultStatus = ResultStatus.PENDING
    engine: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class DesignResultCreate(BaseModel):
    """Payload used to enqueue a new engine run."""

    project_id: int
    file_id: Optional[int] = None
    engine: Optional[str] = "core"
    options: Dict[str, Any] = Field(default_factory=dict)