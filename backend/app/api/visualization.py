"""Sprint 9 — 3D Building visualization endpoint.

Resolves the plan + latest analysis server-side from project_id (like
governance does), so the frontend only needs to send a project id. Returns a
Three.js scene whose nodes carry REAL geometry (positions, dimensions,
utilization) from the designed structure — not a generic placeholder.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.storage import result_id, save_result, list_results, load_result
from app.models.plan_data import PlanData
from app.services.noncad_processor import PlanGenerationError, PlanGenerator

log = logging.getLogger("imad.api.visualization")
router = APIRouter()


class BuildingSceneRequest(BaseModel):
    project_id: int = 1
    plan_name: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class GltfExportRequest(BaseModel):
    project_id: int = 1
    scene_data: Dict[str, Any]


def _latest_plan_name(project_id: int) -> Optional[str]:
    """Find the most recent saved plan name for a project."""
    try:
        names = PlanGenerator.list_plans(project_id)
    except Exception:
        names = []
    return names[-1] if names else None


def _latest_analysis(project_id: int) -> Dict[str, Any]:
    """Find the most recent completed analysis result for a project."""
    results = list_results(prefix="an") or []
    for rid in reversed(results):
        try:
            r = load_result(rid) or {}
        except Exception:
            continue
        if r.get("project_id") == project_id and r.get("status") == "completed":
            return {
                "member_forces": [f.__dict__ if hasattr(f, "__dict__") else f
                                  for f in r.get("member_forces", [])],
                "design": r.get("design", {}),
                "reactions": r.get("reactions", {}),
                "loads": r.get("loads", {}),
            }
    return {}


@router.post("/building/scene", summary="Generate 3D building scene from plan + analysis")
async def building_scene(payload: BuildingSceneRequest) -> Dict[str, Any]:
    """Build a Three.js scene JSON from structural geometry + analysis."""
    plan = None
    if payload.plan:
        try:
            plan = PlanData(**payload.plan)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid plan: {exc}") from exc
    else:
        name = payload.plan_name or _latest_plan_name(payload.project_id)
        if name:
            try:
                plan = PlanGenerator.load_plan(payload.project_id, name)
            except PlanGenerationError:
                plan = None

    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this project.")

    analysis = payload.analysis or _latest_analysis(payload.project_id)
    scene = _build_three_js_scene(plan, analysis or {})
    rid = result_id("scene")
    save_result(rid, {"project_id": payload.project_id, "kind": "3d_scene", "scene": scene})
    return {"result_id": rid, "scene": scene}


@router.post("/building/gltf", summary="Export 3D scene as glTF file")
async def building_gltf(payload: GltfExportRequest) -> Dict[str, Any]:
    """Export the 3D scene to a glTF 2.0 file for download."""
    from app.core.storage import storage_root
    from pathlib import Path
    import json
    try:
        exports = storage_root() / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        path = exports / f"scene-p{payload.project_id}-{_stamp_slug()}.gltf"
        with open(path, "w") as f:
            json.dump(payload.scene_data, f)
    except Exception as exc:
        log.exception("glTF export failed")
        raise HTTPException(status_code=500, detail=f"glTF export failed: {exc}") from exc
    from app.core import audit
    audit.log_action("gltf_export", project_id=payload.project_id, details={"path": str(path)})
    return {"file": str(path), "filename": path.name, "format": "glTF 2.0"}


def _build_three_js_scene(plan: PlanData, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Three.js scene graph from plan + analysis (Y-up)."""
    import math
    nodes = []
    member_forces = analysis.get("member_forces", [])
    floor_height = 3.0  # m per storey

    def _utilization(element_id: str) -> float:
        for m in member_forces:
            if m.get("element_id") == element_id:
                return float(m.get("utilization", 0.0) or 0.0)
        design = analysis.get("design") or {}
        for group in ("beams", "columns"):
            for entry in design.get(group, []):
                if entry.get("element") == element_id:
                    return float(entry.get("utilization", 0.0) or 0.0)
        return 0.0

    for col in plan.columns:
        util = _utilization(col.id)
        nodes.append({"id": f"col-{col.id}", "type": "cylinder",
                      "x": col.cx, "y": col.height / 2, "z": col.cy,
                      "radius": col.size_m / 2, "height": col.height,
                      "color": _utilization_color(util), "utilization": round(util, 2)})

    for beam in plan.beams:
        length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
        angle = math.atan2(beam.y2 - beam.y1, beam.x2 - beam.x1)
        cx, cy = (beam.x1 + beam.x2) / 2, (beam.y1 + beam.y2) / 2
        y = (beam.level + 1) * floor_height
        util = _utilization(beam.id)
        nodes.append({"id": f"beam-{beam.id}", "type": "box",
                      "x": cx, "y": y, "z": cy,
                      "length": length, "width": beam.depth_m, "height": beam.width_m,
                      "rotation_z": angle,
                      "color": _utilization_color(util), "utilization": round(util, 2)})

    for wall in plan.walls:
        length = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
        angle = math.atan2(wall.y2 - wall.y1, wall.x2 - wall.x1)
        cx, cy = (wall.x1 + wall.x2) / 2, (wall.y1 + wall.y2) / 2
        h = wall.height_m or floor_height
        y = (wall.level + 1) * floor_height - h / 2
        nodes.append({"id": f"wall-{wall.id}", "type": "box",
                      "x": cx, "y": y, "z": cy,
                      "length": length, "width": h, "height": wall.thickness_m,
                      "rotation_z": angle, "color": "#888888"})

    return {"version": "1.0", "nodes": nodes, "bounds": plan.bounds(),
            "stories": plan.stories, "floor_height": floor_height,
            "analysis_present": bool(analysis.get("member_forces") or analysis.get("design"))}

def _utilization_color(util: float) -> str:
    if util <= 0.5:
        return "#22c55e"
    elif util <= 0.7:
        return "#84cc16"
    elif util <= 0.85:
        return "#eab308"
    elif util <= 1.0:
        return "#f97316"
    else:
        return "#dc2626"


def _stamp_slug() -> str:
    import secrets
    return secrets.token_hex(4)
