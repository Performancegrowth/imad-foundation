"""Design file model — mirrors the ``design_files`` table (CAD + non-CAD)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class FileKind(str, Enum):
    CAD = "cad"
    NONCAD = "noncad"


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    ERROR = "error"


class FileUpload(BaseModel):
    """Metadata supplied when a client uploads a design file."""

    project_id: int
    kind: FileKind = FileKind.CAD


class DesignFile(BaseModel):
    """Stored file row returned by the API."""

    id: int
    project_id: int
    uploader_id: int
    original_name: str
    stored_name: str
    kind: FileKind
    mime_type: Optional[str] = None
    file_ext: Optional[str] = None
    size_bytes: int = 0
    status: FileStatus = FileStatus.UPLOADED
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        orm_mode = True


class DesignFilePublic(BaseModel):
    """Safe representation without storage paths."""

    id: int
    project_id: int
    original_name: str
    kind: FileKind
    status: FileStatus
    size_bytes: int
    created_at: datetime

    class Config:
        orm_mode = True