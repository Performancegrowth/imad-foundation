"""Sprint 7 — BOQ generation and export endpoints."""
from __future__ import annotations

import logging
import mimetypes
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core import jobs
from app.core.storage import load_result, result_id, save_result
from app.models.plan_data import PlanData
from app.models.survey_data import SurveyReading
from app.services.boq_generator import BOQError, boq_pdf, boq_xlsx, generate_boq
from app.services.noncad_processor import PlanGenerationError, PlanGenerator

log = logging.getLogger("imad.api.boq")
router = APIRouter()


class GenerateBOQRequest(BaseModel):
    project_id: int = 1
    project_name: str = "Imad Project"
    plan: Optional[Dict[str, Any]] = None            # inline PlanData dict
    plan_name: Optional[str] = None                  # or a saved plan name
    survey: Optional[Dict[str, Any]] = None          # SurveyReading dict
    options: Optional[Dict[str, Any]] = None         # opt-in async via options.async


def _resolve_plan(payload: GenerateBOQRequest) -> PlanData:
    if payload.plan:
        try:
            return PlanData(**payload.plan)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid plan: {exc}") from exc
    if payload.plan_name:
        try:
            return PlanGenerator.load_plan(payload.project_id, payload.plan_name)
        except PlanGenerationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail="Provide 'plan' or 'plan_name'.")


def _resolve_survey(payload: GenerateBOQRequest) -> Optional[SurveyReading]:
    """Explicit survey dict wins; otherwise auto-include the project's
    recorded site survey so footing sizing and earthworks use real data."""
    if payload.survey:
        try:
            return SurveyReading(**payload.survey)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid survey: {exc}") from exc
    from app.services.survey_processor import load_survey_reading

    return load_survey_reading(payload.project_id) if payload.project_id else None


@router.post("/generate-boq", summary="Generate a detailed BOQ + BBS")
async def generate(payload: GenerateBOQRequest) -> Dict[str, Any]:
    """Run synchronously by default so callers get the full BOQ payload (same
    contract as /analyze). Background execution (Redis + worker) is an explicit
    opt-in via ``options: {"async": true}`` — the response then carries a job_id."""
    data = payload.model_dump()
    if (payload.options or {}).get("async"):
        return {"job_id": jobs.enqueue_job("boq", data)}
    return run_boq(data)


def run_boq(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a BOQ generation job. Worker-safe."""
    from app.core import audit

    request = GenerateBOQRequest(**data)
    plan = _resolve_plan(request)
    survey = _resolve_survey(request)
    try:
        boq = generate_boq(plan, survey, project_name=request.project_name)
    except BOQError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("BOQ generation failed")
        raise HTTPException(status_code=500, detail=f"BOQ failed: {exc}") from exc

    rid = result_id("boq")
    save_result(rid, {"project_id": request.project_id,
                      "kind": "boq", "payload": boq})
    audit.log_action("generate_boq", project_id=request.project_id,
                     details={"result_id": rid, "total_usd": boq["totals"]["amount_usd"]})
    return {"result_id": rid, **boq}


@router.get("/generate-boq/{result_id}", summary="Fetch a previously generated BOQ")
async def fetch(result_id: str) -> Dict[str, Any]:
    record = load_result(result_id)
    if not record:
        raise HTTPException(status_code=404, detail="BOQ not found.")
    payload = record.get("payload", {})
    if isinstance(payload.get("items"), list) and "kind" not in payload:
        pass  # legacy shape tolerated
    inner = payload.get("payload", payload)             # unwrap saved envelope
    if not inner:
        raise HTTPException(status_code=404, detail="BOQ payload empty.")
    return {"result_id": result_id, **inner}


@router.post("/generate-boq/{result_id}/export/pdf",
             summary="Export a stored BOQ as a branded PDF report")
async def export_pdf(result_id: str) -> Dict[str, Any]:
    record = _load_boq(result_id)
    try:
        path = boq_pdf(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}") from exc
    from app.core import audit

    audit.log_action("export_pdf", details={"result_id": result_id, "path": path})
    return {"file": path, "filename": path.replace("\\\\", "/").split("/")[-1]}


@router.post("/generate-boq/{result_id}/export/xlsx",
             summary="Export a stored BOQ as an Excel workbook (Summary/BOQ/BBS)")
async def export_xlsx(result_id: str) -> Dict[str, Any]:
    record = _load_boq(result_id)
    try:
        path = boq_xlsx(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel export failed: {exc}") from exc
    from app.core import audit

    audit.log_action("export_excel", details={"result_id": result_id, "path": path})
    return {"file": path, "filename": path.replace("\\\\", "/").split("/")[-1]}


@router.get("/exports/download", include_in_schema=False,
            summary="Download a generated export file by absolute path token")
async def download(path: str):
    """Serve files produced inside the exports directory only."""
    from pathlib import Path as _P

    from app.services.exporters import exports_dir

    target = _P(path)
    root = exports_dir().resolve()
    try:
        target_resolved = target.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Bad path.") from exc
    if root not in target_resolved.parents or not target_resolved.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")
    media = mimetypes.guess_type(str(target_resolved))[0] or "application/octet-stream"
    return FileResponse(target_resolved, media_type=media,
                        filename=target_resolved.name)


def _load_boq(result_id: str) -> Dict[str, Any]:
    record = load_result(result_id)
    if not record:
        raise HTTPException(status_code=404, detail="BOQ not found.")
    payload = record.get("payload") or {}
    inner = payload.get("payload", payload)
    if not isinstance(inner, dict) or "items" not in inner:
        raise HTTPException(status_code=422, detail="Result is not a BOQ.")
    return inner