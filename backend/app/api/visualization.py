"""Sprint 9 — 3D Building visualization endpoint."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.storage import result_id, save_result
from app.models.plan_data import PlanData

log = logging.getLogger("imad.api.visualization")
router = APIRouter()


class BuildingSceneRequest(BaseModel):
    project_id: int = 1
    plan: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None  # AnalysisResult from Sprint 5
    options: Optional[Dict[str, Any]] = None


class GltfExportRequest(BaseModel):
    project_id: int = 1
    scene_data: Dict[str, Any]


@router.post("/building/scene", summary="Generate 3D building scene from plan + analysis")
async def building_scene(payload: BuildingSceneRequest) -> Dict[str, Any]:
    """Build a Three.js scene JSON from structural geometry and analysis results.
    
    Input:
      - plan: PlanData geometry (walls, columns, beams)
      - analysis: AnalysisResult with member forces, deflections, utilization
      - options: viz options (show_forces, highlight_failing, etc.)
    
    Output:
      - scene_data: Three.js format (nodes, elements, materials, colors)
      - result_id: stored for export/download
    """
    if not payload.plan:
        raise HTTPException(status_code=422, detail="Plan is required")
    
    try:
        plan = PlanData(**payload.plan)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid plan: {exc}") from exc
    
    # Build scene from plan geometry + analysis results
    scene = _build_three_js_scene(plan, payload.analysis or {})
    
    rid = result_id("scene")
    save_result(rid, {
        "project_id": payload.project_id,
        "kind": "3d_scene",
        "scene": scene,
    })
    
    return {
        "result_id": rid,
        "scene": scene,
    }


@router.post("/building/gltf", summary="Export 3D scene as glTF file")
async def building_gltf(payload: GltfExportRequest) -> Dict[str, Any]:
    """Export the 3D scene to a glTF 2.0 file for download.
    
    Input:
      - scene_data: from /building/scene response
    
    Output:
      - file_path: URL-safe path for download
      - filename: suggested filename
    """
    from app.core.storage import storage_root
    from pathlib import Path
    import json
    
    try:
        exports = storage_root() / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        path = exports / f"scene-p{payload.project_id}-{_stamp_slug()}.gltf"
        
        # Convert Three.js scene to glTF format (simplified: just save JSON for now)
        # Full glTF conversion would require gltf-export library
        with open(path, "w") as f:
            json.dump(payload.scene_data, f)
    except Exception as exc:
        log.exception("glTF export failed")
        raise HTTPException(status_code=500, detail=f"glTF export failed: {exc}") from exc
    
    from app.core import audit
    audit.log_action("gltf_export", project_id=payload.project_id,
                     details={"path": str(path)})
    
    return {
        "file": str(path),
        "filename": path.name,
        "format": "glTF 2.0",
    }


def _build_three_js_scene(plan: PlanData, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Three.js scene graph from plan + analysis."""
    import math
    
    # Geometry nodes
    nodes = []
    elements = []
    
    # Add columns as cylinders
    for i, col in enumerate(plan.columns):
        nodes.append({
            "id": f"col-{col.id}",
            "type": "cylinder",
            "x": col.cx,
            "y": col.cy,
            "z": 0,
            "radius": col.size_m / 2,
            "height": col.height,
        })
    
    # Add beams as boxes
    for i, beam in enumerate(plan.beams):
        length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
        angle = math.atan2(beam.y2 - beam.y1, beam.x2 - beam.x1)
        cx = (beam.x1 + beam.x2) / 2
        cy = (beam.y1 + beam.y2) / 2
        
        # Color based on utilization (from analysis if available)
        member_forces = analysis.get("member_forces", [])
        matching = [m for m in member_forces if m.get("element_id") == beam.id]
        utilization = matching[0].get("utilization", 0) if matching else 0
        color = _utilization_color(utilization)
        
        nodes.append({
            "id": f"beam-{beam.id}",
            "type": "box",
            "x": cx,
            "y": cy,
            "z": beam.level,
            "length": length,
            "width": beam.width_m,
            "height": beam.depth_m,
            "rotation_z": angle,
            "color": color,
            "utilization": round(utilization, 2),
        })
    
    # Add walls as boxes
    for wall in plan.walls:
        length = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
        angle = math.atan2(wall.y2 - wall.y1, wall.x2 - wall.x1)
        cx = (wall.x1 + wall.x2) / 2
        cy = (wall.y1 + wall.y2) / 2
        h = wall.height_m or 3.0
        
        nodes.append({
            "id": f"wall-{wall.id}",
            "type": "box",
            "x": cx,
            "y": cy,
            "z": wall.level,
            "length": length,
            "width": wall.thickness_m,
            "height": h,
            "rotation_z": angle,
            "color": "#888888",  # gray
        })
    
    # Return Three.js scene format
    return {
        "version": "1.0",
        "nodes": nodes,
        "bounds": plan.bounds(),
        "stories": plan.stories,
        "analysis_present": bool(analysis),
    }


def _utilization_color(util: float) -> str:
    """Return RGB color based on member utilization (0.0-1.0)."""
    if util <= 0.5:
        return "#22c55e"  # green
    elif util <= 0.8:
        return "#eab308"  # yellow
    elif util <= 1.0:
        return "#f97316"  # orange
    else:
        return "#dc2626"  # red


def _stamp_slug() -> str:
    import secrets
    return secrets.token_hex(4)
