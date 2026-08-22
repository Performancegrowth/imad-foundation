"""Sprint 9A — 3D building visualization endpoints.

Serves render-ready scene JSON (boxes in Z-up metres) and a minimal glTF 2.0
export for the Three.js building viewer. Scenes are generated from a PlanData
payload supplied inline or loaded from a saved plan.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.visualization_service import VisualizationService

log = logging.getLogger("imad.api.viz")
router = APIRouter()
_service = VisualizationService()


class SceneRequest(BaseModel):
    plan: Optional[Dict[str, Any]] = None            # inline PlanData dict
    project_id: int = 1
    plan_name: Optional[str] = None                  # or a saved plan name
    options: Dict[str, Any] = {}                     # story_height_m, window_ratio…


def _resolve_plan(payload: SceneRequest) -> Dict[str, Any]:
    if payload.plan:
        return payload.plan
    if payload.plan_name:
        from app.services.noncad_processor import PlanGenerationError, PlanGenerator

        try:
            plan = PlanGenerator.load_plan(payload.project_id, payload.plan_name)
        except PlanGenerationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)
    raise HTTPException(status_code=422, detail="Provide 'plan' or 'plan_name'.")


@router.post("/building/scene", summary="Build a renderable multi-floor scene")
async def building_scene(payload: SceneRequest) -> Dict[str, Any]:
    plan = _resolve_plan(payload)
    try:
        scene = _service.build_scene(plan, payload.options or None)
    except Exception as exc:
        log.exception("Scene build failed")
        raise HTTPException(status_code=500, detail=f"Scene build failed: {exc}") from exc
    return _service.to_dict(scene)


@router.post("/building/gltf", summary="Export the building as glTF 2.0 JSON",
             response_class=Response)
async def building_gltf(payload: SceneRequest) -> Response:
    plan = _resolve_plan(payload)
    try:
        scene = _service.build_scene(plan, payload.options or None)
        gltf = _service.to_gltf_json(scene)
    except Exception as exc:
        log.exception("glTF export failed")
        raise HTTPException(status_code=500, detail=f"glTF export failed: {exc}") from exc
    body = json.dumps(gltf, separators=(",", ":"))
    return Response(
        content=body,
        media_type="model/gltf+json",
        headers={"Content-Disposition": 'attachment; filename="imad-building.gltf"'},
    )