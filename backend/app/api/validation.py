"""Sprint 11 — Engineering validation & certification endpoints.

POST /validation/run       → run the hand-calc benchmark suite
GET  /validation/report    → latest stored suite report
GET  /validation/report/pdf→ branded PDF accuracy report download
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.docstore import collection
from app.services.validation_engine import ValidationError, run_suite, validation_pdf

log = logging.getLogger("imad.api.validation")
router = APIRouter()

KNOWN_CASES = ["beam_udl", "column_gravity", "frame_elf"]
# Accept either the canonical engine ids above or the friendly aliases below.
_CASE_ALIASES = {"beam": "beam_udl", "column": "column_gravity", "frame": "frame_elf"}


class ValidationRunRequest(BaseModel):
    cases: Optional[List[str]] = None      # default: all benchmarks


@router.post("/validation/run", summary="Run benchmark suite vs hand calculations")
async def run(payload: ValidationRunRequest) -> Dict[str, Any]:
    cases = payload.cases or None
    if cases:
        cases = [_CASE_ALIASES.get(c, c) for c in cases]
    if cases:
        unknown = [c for c in cases if c not in KNOWN_CASES]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown cases {unknown}; valid: {KNOWN_CASES}")
    try:
        report = run_suite(cases)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    stored = collection("validation_reports").put(report, prefix="val")
    return {"report_id": stored["id"], **report}


@router.get("/validation/report", summary="Latest validation suite report")
async def latest() -> Dict[str, Any]:
    reports = collection("validation_reports").list()
    if not reports:
        raise HTTPException(
            status_code=404,
            detail="No validation run yet — POST /validation/run first.")
    latest_report = max(reports, key=lambda r: r.get("created_at", ""))
    return latest_report


@router.get("/validation/report/pdf", summary="Download the latest accuracy report (PDF)")
async def latest_pdf():
    reports = collection("validation_reports").list()
    if not reports:
        raise HTTPException(status_code=404, detail="No validation run yet.")
    latest_report = max(reports, key=lambda r: r.get("created_at", ""))
    try:
        path = validation_pdf(latest_report)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/pdf",
                        filename=path.replace("\\", "/").split("/")[-1])