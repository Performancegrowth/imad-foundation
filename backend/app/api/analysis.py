"""Sprint 5 — Structural analysis endpoint."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import jobs
from app.core.storage import result_id, save_result
from app.models.plan_data import PlanData
from app.models.survey_data import SurveyReading
from app.services.noncad_processor import PlanGenerationError, PlanGenerator
from app.services.structural_engine import OpenSeesEngine, StructuralError

log = logging.getLogger("imad.api.analysis")
router = APIRouter()

_engine = OpenSeesEngine()


class AnalyzeRequest(BaseModel):
    project_id: int
    plan: Optional[Dict[str, Any]] = None          # inline PlanData
    plan_name: Optional[str] = None                # load a saved plan instead
    survey: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class AnalyzeResponse(BaseModel):
    result_id: str
    status: str
    solver: str
    summary: Dict[str, Any]
    design: Dict[str, Any]
    boq: Dict[str, Any]
    reactions: Dict[str, Any]
    member_forces: list


@router.post("/analyze", summary="Run structural analysis on a plan")
async def analyze(payload: AnalyzeRequest) -> Dict[str, Any]:
    """Run the analysis and return the full result payload.

    Background execution (Redis queue + worker) is available by opting in with
    ``options: {"async": true}``; the response then carries a ``job_id`` that
    can be polled at ``GET /jobs/{job_id}``. Synchronous-by-default keeps the
    workspace UI simple: it renders whatever this call returns.
    """
    data = payload.model_dump()
    if (payload.options or {}).get("async"):
        return {"job_id": jobs.enqueue_job("analysis", data)}
    return run_analysis(data)


def run_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a structural analysis job. Worker-safe (no HTTP context)."""
    request = AnalyzeRequest(**data)
    plan = _resolve_plan(request)
    survey = _resolve_survey(request)

    try:
        result = _engine.analyze(plan, survey, request.options or {})
    except StructuralError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Analysis crashed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    rid = result_id("an")
    save_result(rid, {
        "project_id": request.project_id,
        "status": result.status,
        "solver": result.diagnostics.solver,
        "periods": result.periods_s,
        "reactions": result.reactions,
        "member_forces": [f.__dict__ for f in result.member_forces],
        "design": result.design,
        "boq": result.boq,
        "loads": result.loads,
        "summary": {
            "max_moment_kNm": result.max_moment_kNm,
            "max_shear_kN": result.max_shear_kN,
            "max_axial_kN": result.max_axial_kN,
            "max_deflection_mm": result.max_deflection_mm,
        },
    })

    return {
        "result_id": rid,
        "status": result.status,
        "solver": result.diagnostics.solver,
        "summary": {
            "max_moment_kNm": result.max_moment_kNm,
            "max_shear_kN": result.max_shear_kN,
            "max_axial_kN": result.max_axial_kN,
            "max_deflection_mm": result.max_deflection_mm,
        },
        "design": result.design,
        "boq": result.boq,
        "reactions": result.reactions,
        "member_forces": [f.__dict__ for f in result.member_forces],
    }


def _resolve_plan(payload: AnalyzeRequest) -> PlanData:
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


def _resolve_survey(payload: AnalyzeRequest) -> Optional[SurveyReading]:
    """Explicit survey dict wins; otherwise auto-include the project's
    recorded site survey so geotechnical data drives foundation sizing."""
    if payload.survey:
        try:
            return SurveyReading(**payload.survey)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid survey: {exc}") from exc
    from app.services.survey_processor import load_survey_reading

    return load_survey_reading(payload.project_id) if payload.project_id else None