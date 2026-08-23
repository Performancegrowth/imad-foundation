"""Sprint 4 — Survey engineering endpoints."""
from __future__ import annotations

import logging
import tempfile
from typing import Any, Dict

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.survey_processor import (
    FileSurveyProcessor,
    ManualSurveyProcessor,
    SurveyError,
)

log = logging.getLogger("imad.api.survey")
router = APIRouter()

manual_processor = ManualSurveyProcessor()
file_processor = FileSurveyProcessor()
SURVEY_EXTENSIONS = (".pdf", ".csv", ".dxf", ".las", ".laz")


class ManualEntry(BaseModel):
    project_id: int
    reading: Dict[str, Any]


@router.post("/manual", summary="Record a hand-entered geotechnical reading")
async def manual(payload: ManualEntry):
    try:
        summary = manual_processor.process(payload.project_id, payload.reading)
    except SurveyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return summary


@router.post("/upload", summary="Import survey data from a PDF/CSV/DXF/LAS file")
async def upload(file: UploadFile, project_id: int = Form(...)):
    filename = (file.filename or "").strip()
    ext = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if ext not in SURVEY_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported survey type '{ext or '?'}'. Allow: {', '.join(SURVEY_EXTENSIONS)}",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = file_processor.process(tmp_path, project_id)
        # persist alongside manual entries for the summary card
        manual_processor._write_entries(
            project_id,
            manual_processor._load_entries(project_id)
            + [{**result, "source": ext.lstrip(".")}],
        )
    except SurveyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.get("/{project_id}", summary="Fetch the survey summary card")
async def summary(project_id: int):
    return manual_processor.load_summary(project_id).model_dump(mode="json")