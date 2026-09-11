"""Sprint 3 â€” Plan generation from non-CAD inputs (authenticated).

Every plan route requires a valid bearer token; project-scoped routes also
verify that the caller owns the project (404 otherwise) so users cannot read
or modify another user's plans.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user, require_owner
from app.core.security import TokenPayload
from app.models.plan_data import PlanData
from app.services.noncad_processor import (
    PlanGenerationError,
    PlanGenerator,
    TEMPLATE_LIBRARY,
)

log = logging.getLogger("imad.api.plans")
# NOTE: no router-level auth dependency — /templates is intentionally public
# (templates are not user-specific); every data-bearing route below declares
# its own ``Depends(require_owner)`` guard.
router = APIRouter()

_generator = PlanGenerator()


class QuestionnaireRequest(BaseModel):
    answers: Dict[str, Any]


class TemplateRequest(BaseModel):
    template_id: str
    floors: int = 1


class DescriptionRequest(BaseModel):
    text: str = Field(min_length=5, max_length=4000)
    floors: int = 1


class SavePlanRequest(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=120)
    plan: Dict[str, Any]


@router.get("/templates", summary="List available plan templates")
async def list_templates():
    return [
        {"id": tid, "name": tpl["name"], "kind": tpl["kind"]}
        for tid, tpl in TEMPLATE_LIBRARY.items()
    ]


@router.post("/questionnaire", summary="Generate a plan from a questionnaire")
async def questionnaire(payload: QuestionnaireRequest, user: TokenPayload = Depends(get_current_user)):
    try:
        plan = _generator.generate_from_questionnaire(payload.answers)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return plan.model_dump(mode="json")


@router.post("/template", summary="Instantiate a plan from the template library")
async def template(payload: TemplateRequest, user: TokenPayload = Depends(get_current_user)):
    try:
        plan = _generator.generate_from_template(payload.template_id, payload.floors)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return plan.model_dump(mode="json")


@router.post("/description", summary="Generate a layout from a natural-language description")
async def description(payload: DescriptionRequest, user: TokenPayload = Depends(get_current_user)):
    try:
        plan = await _generator.generate_from_description(payload.text, payload.floors)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        log.error("AI description failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Layout service is unavailable (is Ollama running?).",
        ) from exc
    return plan.model_dump(mode="json")


@router.post("/save", summary="Persist a plan for a project")
async def save(payload: SavePlanRequest, user: TokenPayload = Depends(require_owner)):
    try:
        plan = PlanData(**payload.plan)
    except Exception as exc:
        raise HTTPException(status_code=422,
                            detail=f"Invalid plan payload: {exc}") from exc
    return _generator.save_plan(payload.project_id, payload.name, plan)


@router.get("/{project_id}", summary="List saved plans for a project")
async def list_plans(project_id: int, user: TokenPayload = Depends(require_owner)):
    return _generator.list_plans(project_id)


@router.get("/{project_id}/{name}", summary="Fetch a specific saved plan")
async def get_plan(project_id: int, name: str, user: TokenPayload = Depends(require_owner)):
    try:
        plan = PlanGenerator.load_plan(project_id, name)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return plan.model_dump(mode="json")


