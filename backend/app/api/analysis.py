"""Sprint 5 — Structural analysis endpoint."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


@router.post("/analyze", response_model=AnalyzeResponse, summary="Run structural analysis on a plan")
async def analyze(payload: AnalyzeRequest):
    plan = _resolve_plan(payload)
    survey = SurveyReading(**payload.survey) if payload.survey else None

    try:
        result = _engine.analyze(plan, survey, payload.options or {})
    except StructuralError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Analysis crashed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    rid = result_id("an")
    save_result(rid, {
        "project_id": payload.project_id,
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

    return AnalyzeResponse(
        result_id=rid,
        status=result.status,
        solver=result.diagnostics.solver,
        summary={
            "max_moment_kNm": result.max_moment_kNm,
            "max_shear_kN": result.max_shear_kN,
            "max_axial_kN": result.max_axial_kN,
            "max_deflection_mm": result.max_deflection_mm,
        },
        design=result.design,
        boq=result.boq,
        reactions=result.reactions,
        member_forces=[f.__dict__ for f in result.member_forces],
    )


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