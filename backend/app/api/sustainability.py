"""Sprint 8 — Sustainability endpoints: carbon report, alternatives, LCA PDF."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import jobs
from app.core.storage import result_id, save_result
from app.services.boq_generator import BOQError, generate_boq
from app.services.carbon_calculator import (
    CarbonError,
    ai_recommendations,
    combined_scenarios,
    compliance_matrix,
    compute_embodied_carbon,
    evaluate_green_alternatives,
    lca_pdf,
)
from app.models.plan_data import PlanData
from app.models.survey_data import SurveyReading
from app.services.noncad_processor import PlanGenerationError, PlanGenerator

log = logging.getLogger("imad.api.carbon")
router = APIRouter()


class CarbonReportRequest(BaseModel):
    project_id: int = 1
    project_name: str = "Imad Project"
    plan: Optional[Dict[str, Any]] = None
    plan_name: Optional[str] = None
    survey: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None         # opt-in async via options.async


async def _build(boq: Dict[str, Any]) -> Dict[str, Any]:
    """Shared pipeline: carbon → alternatives → compliance → AI narrative."""
    try:
        carbon = compute_embodied_carbon(boq)
        alternatives = evaluate_green_alternatives(boq, carbon)
        # attach for rating-scheme rules that inspect the alternative set
        carbon["_alternatives"] = alternatives
        compliance = compliance_matrix(carbon)
        narrative = await ai_recommendations(carbon, alternatives)
        carbon.pop("_alternatives", None)
    except CarbonError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "carbon": carbon,
        "alternatives": alternatives,
        "compliance": compliance,
        "scenario_best_case": combined_scenarios(boq),
        "recommendations": narrative,
    }


@router.post("/carbon-report", summary="Full embodied-carbon report from a plan or BOQ")
async def carbon_report(payload: CarbonReportRequest) -> Dict[str, Any]:
    """Run synchronously by default so callers get the full report payload (same
    contract as /analyze and /generate-boq). Background execution is an explicit
    opt-in via ``options: {"async": true}`` — response then carries a job_id."""
    data = payload.model_dump()
    if (payload.options or {}).get("async"):
        return {"job_id": jobs.enqueue_job("carbon", data)}
    return await run_carbon(data)


async def run_carbon(data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a carbon-report job. Worker-safe (usable with asyncio.run)."""
    from app.core import audit

    request = CarbonReportRequest(**data)
    if request.plan:
        try:
            plan = PlanData(**request.plan)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid plan: {exc}") from exc
        survey = SurveyReading(**request.survey) if request.survey else None
        try:
            boq = generate_boq(plan, survey, project_name=request.project_name)
        except BOQError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif request.plan_name:
        try:
            saved = PlanGenerator.load_plan(request.project_id, request.plan_name)
        except PlanGenerationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raw_plan = saved.get("plan") or saved.get("plan_data") or {}
        try:
            plan = PlanData(**raw_plan)
            boq = generate_boq(
                plan,
                SurveyReading(**(saved.get("survey") or {})) or None,
                project_name=request.project_name,
            )
        except (BOQError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=f"Saved plan unusable: {exc}") from exc
    else:
        raise HTTPException(status_code=422, detail="Provide 'plan' or 'plan_name'.")

    report = await _build(boq)
    rid = result_id("carbon")
    save_result(rid, {"project_id": request.project_id, "kind": "carbon",
                      "payload": {"boq_ref": boq["totals"], **report}})
    audit.log_action("carbon_report", project_id=request.project_id,
                     details={"result_id": rid,
                              "total_t": report["carbon"]["total_co2e_tonnes"]})
    return {"result_id": rid, "boq_totals": boq["totals"], **report}


@router.post("/carbon-report/lca-pdf", summary="Render the LCA report as PDF")
async def export_lca(report: Dict[str, Any]) -> Dict[str, Any]:
    """Accepts the payload returned by ``/carbon-report`` plus boq_totals."""
    boq_totals = report.get("boq_totals") or {}
    fake_boq = {"project_name": report.get("project_name", "Imad Project"),
                "totals": {**boq_totals}}
    try:
        path = lca_pdf(fake_boq, report["carbon"], report["alternatives"],
                       report["compliance"],
                       (report.get("recommendations") or {}).get("recommendations", ""))
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422,
                            detail="Malformed report payload.") from exc
    except Exception as exc:
        log.exception("LCA export failed")
        raise HTTPException(status_code=500, detail=f"LCA export failed: {exc}") from exc
    from app.core import audit

    audit.log_action("export_lca_pdf", details={"path": path})
    return {"file": path, "filename": path.replace("\\\\", "/").split("/")[-1]}