"""Sprint 6 — Generative design endpoints.

POST /generate-designs             → enqueue a background NSGA-II run (job id)
GET  /generate-designs/status/{id} → job status + progress + top-3 options
POST /generate-designs/select      → persist the chosen option as a saved plan
GET  /generate-designs/{id}/recommendation → AI narration (best-effort)

Results are cached per envelope (length × width × stories) so repeated runs on
simple buildings return instantly (the <60 s budget applies to cold runs only).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.jobs import get_job, new_job, run_in_background, update_job
from app.services.ai_provider import (
    AIProviderError,
    BaseMessage,
    OllamaLocalProvider,
    Role,
)
from app.services.generative_design import (
    DesignOption,
    GenerativeDesignEngine,
)
from app.services.noncad_processor import PlanGenerator

log = logging.getLogger("imad.api.generative")
router = APIRouter()

_engine = GenerativeDesignEngine(population=50, generations=100)


class GenerateRequest(BaseModel):
    length_m: float = Field(gt=0, le=300, description="Building envelope length (m)")
    width_m: float = Field(gt=0, le=300, description="Building envelope width (m)")
    stories: int = Field(default=1, ge=1, le=40)
    population: int = Field(default=50, ge=10, le=200)
    generations: int = Field(default=100, ge=5, le=200)
    seed: int = 42


class SelectRequest(BaseModel):
    job_id: str
    option_id: str
    project_id: int = 1
    name: Optional[str] = None


@router.post("/generate-designs", summary="Generate structural design alternatives (NSGA-II)")
async def generate_designs(payload: GenerateRequest) -> Dict[str, Any]:
    """Kick off a generative run in a background worker thread."""
    # Fast path: serve a cached Pareto set for an identical envelope.
    cached = _engine.load_cached(payload.length_m, payload.width_m, payload.stories)
    if cached:
        job_id = new_job("generative")
        update_job(job_id, status="completed", progress=1.0, result={
            "cached": True, "options": cached, "envelope": payload.model_dump()})
        audit.log_action("generate_design_cached", details={
            "length_m": payload.length_m, "width_m": payload.width_m})
        return {"job_id": job_id, "cached": True}

    engine = GenerativeDesignEngine(
        population=payload.population, generations=payload.generations,
        seed=payload.seed)

    def _run(job_id: str) -> Dict[str, Any]:
        def _progress(fraction: float) -> None:
            update_job(job_id, progress=round(min(max(fraction, 0.0), 1.0), 3))

        options: List[DesignOption] = engine.generate(
            payload.length_m, payload.width_m, payload.stories, progress=_progress)
        engine.store_cache(payload.length_m, payload.width_m, payload.stories, options)
        return {
            "cached": False,
            "envelope": payload.model_dump(),
            "options": [{
                "option_id": o.option_id, "genes": o.genes, "fitness": o.fitness,
                "plan": o.plan, "rank": o.rank, "summary": o.summary,
            } for o in options],
        }

    job_id = new_job("generative")
    run_in_background(job_id, _run, job_id)
    audit.log_action("generate_design_started", details={
        "length_m": payload.length_m, "width_m": payload.width_m,
        "stories": payload.stories})
    return {"job_id": job_id, "cached": False}


@router.get("/generate-designs/status/{job_id}", summary="Poll generative job status")


@router.get("/generate-designs/{job_id}/recommendation",
            summary="AI recommendation narrative for the ranked options")
async def recommendation(job_id: str) -> Dict[str, Any]:
    """Ask the local LLM for a short engineering narrative.

    Falls back to deterministic rule-based text whenever Ollama is unreachable —
    the optimisation numbers themselves never come from the model.
    """
    job = get_job(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed yet.")
    options = (job.get("result") or {}).get("options") or []
    if not options:
        raise HTTPException(status_code=404, detail="No options in this job.")

    prompt = (
        "You are a senior structural engineer. In max 120 words compare these "
        f"design options and recommend one. Data: {options}. "
        "Mention trade-offs between cost, carbon, flexibility and safety."
    )
    try:
        provider = OllamaLocalProvider()
        reply = await provider.chat_json([
            BaseMessage(Role.SYSTEM, 'Reply as strict JSON {"recommendation": "..."}'),
            BaseMessage(Role.USER, prompt),
        ])
        text = str(reply.get("recommendation", "")).strip()
        if not text:
            raise AIProviderError("Empty recommendation.")
        return {"source": "ollama", "recommendation": text}
    except Exception as exc:  # noqa: BLE001 — graceful fallback keeps UI alive
        log.info("AI recommendation fallback: %s", exc)
        return {"source": "rule-based", "recommendation": _rule_based(options)}


def _rule_based(options: List[Dict[str, Any]]) -> str:
    """Deterministic comparison used when no LLM is reachable."""
    if not options:
        return ""
    best_cost = min(options, key=lambda o: o["fitness"].get("cost", 9e9))
    best_carbon = min(options, key=lambda o: o["fitness"].get("carbon", 9e9))
    best_flex = min(options, key=lambda o: o["fitness"].get("flexibility", 9e9))
    pick = best_cost if best_cost is best_carbon else best_flex
    return (
        f"Option {best_cost['option_id']} minimises cost "
        f"(≈{best_cost['fitness']['cost']:.0f}/m²); option {best_carbon['option_id']} "
        f"minimises embodied carbon (≈{best_carbon['fitness']['carbon']:.0f} kgCO₂e/m²); "
        f"option {best_flex['option_id']} offers the most flexible bays. "
        f"Preliminary recommendation: option {pick['option_id']} as the balanced scheme. "
        "Confirm with full member design before issuing."
    )


@router.post("/generate-designs/select", summary="Persist a chosen option as a saved plan")
async def select_option(payload: SelectRequest) -> Dict[str, Any]:
    job = get_job(payload.job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed yet.")
    options = (job.get("result") or {}).get("options") or []
    chosen = next((o for o in options if o["option_id"] == payload.option_id), None)
    if not chosen:
        raise HTTPException(status_code=404, detail="Option not found in this job.")

    from app.models.plan_data import PlanData

    try:
        plan = PlanData(**chosen["plan"])
    except Exception as exc:  # pragma: no cover — defensive
        raise HTTPException(status_code=500, detail=f"Corrupt option payload: {exc}") from exc

    name = payload.name or f"Generative {payload.option_id}"
    saved = PlanGenerator.save_plan(payload.project_id, name, plan)
    audit.log_action("generative_option_selected", project_id=payload.project_id,
                     details={"option_id": payload.option_id, "plan": name})
    return {"saved": saved, "fitness": chosen["fitness"]}
async def generation_status(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'.")
    return job