"""Sprint 9 — 3D building scene generation from plans and analysis.

Converts structural geometry + analysis results into Three.js scene format,
with member coloring based on utilization ratios. Supports glTF export.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData

log = logging.getLogger("imad.building_scene")


class BuildingSceneError(Exception):
    """Raised when 3D scene generation fails."""


def build_3d_scene(plan: PlanData, analysis: Optional[Dict[str, Any]] = None,
                   options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a Three.js scene graph from structural geometry + optional analysis.
    
    Args:
        plan: PlanData with walls, columns, beams, grids
        analysis: Optional AnalysisResult with member forces and utilization
        options: Rendering options (show_forces, highlight_failing, etc.)
    
    Returns:
        Scene dict in Three.js format (nodes, materials, colors, bounds)
    """
    if not plan:
        raise BuildingSceneError("Plan is required")
    
    options = options or {}
    analysis = analysis or {}
    
    # Build geometry nodes
    nodes = []
    elements = []
    materials = {}
    
    # Add columns
    for col in plan.columns:
        node = _build_column_node(col, analysis)
        nodes.append(node)
        elements.append({
            "id": f"col-{col.id}",
            "type": "column",
            "node_id": node["id"],
        })
    
    # Add beams
    for beam in plan.beams:
        node = _build_beam_node(beam, analysis)
        nodes.append(node)
        elements.append({
            "id": f"beam-{beam.id}",
            "type": "beam",
            "node_id": node["id"],
        })
    
    # Add walls
    for wall in plan.walls:
        node = _build_wall_node(wall)
        nodes.append(node)
        elements.append({
            "id": f"wall-{wall.id}",
            "type": "wall",
            "node_id": node["id"],
        })
    
    # Add grids (reference lines)
    for grid in plan.grids:
        node = _build_grid_node(grid)
        if node:
            nodes.append(node)
    
    bounds = plan.bounds()
    
    return {
        "version": "1.0",
        "nodes": nodes,
        "elements": elements,
        "bounds": bounds,
        "stories": plan.stories,
        "analysis_present": bool(analysis.get("member_forces")),
        "materials": materials,
        "timestamp": _now_iso(),
    }


def _build_column_node(col, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Three.js geometry node for a column."""
    # Look up utilization from analysis
    utilization = 0.0
    if analysis:
        member_forces = analysis.get("member_forces", [])
        design = analysis.get("design", {})
        col_checks = design.get("columns", [])
        matching = [c for c in col_checks if c.get("element") == col.id]
        if matching:
            utilization = matching[0].get("utilization", 0.0)
    
    color = _utilization_color(utilization)
    
    return {
        "id": f"col-{col.id}",
        "type": "cylinder",
        "geometry": {
            "center": [col.cx, col.cy, col.height / 2],
            "radius": col.size_m / 2,
            "height": col.height,
        },
        "material": {
            "color": color,
            "opacity": 0.85,
        },
        "properties": {
            "utilization": round(utilization, 2),
            "size_m": col.size_m,
            "height_m": col.height,
        },
    }


def _build_beam_node(beam, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Three.js geometry node for a beam."""
    length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
    angle = math.atan2(beam.y2 - beam.y1, beam.x2 - beam.x1)
    cx = (beam.x1 + beam.x2) / 2
    cy = (beam.y1 + beam.y2) / 2
    
    # Look up utilization from analysis
    utilization = 0.0
    if analysis:
        design = analysis.get("design", {})
        beam_checks = design.get("beams", [])
        matching = [b for b in beam_checks if b.get("element") == beam.id]
        if matching:
            utilization = matching[0].get("utilization", 0.0)
    
    color = _utilization_color(utilization)
    
    return {
        "id": f"beam-{beam.id}",
        "type": "box",
        "geometry": {
            "center": [cx, cy, beam.level],
            "width": length,  # along beam axis
            "height": beam.depth_m,  # vertical depth
            "depth": beam.width_m,  # perpendicular width
        },
        "rotation": [0, 0, angle],
        "material": {
            "color": color,
            "opacity": 0.8,
        },
        "properties": {
            "utilization": round(utilization, 2),
            "moment_kNm": beam.span if hasattr(beam, 'span') else None,
            "width_m": beam.width_m,
            "depth_m": beam.depth_m,
            "level": beam.level,
        },
    }


def _build_wall_node(wall) -> Dict[str, Any]:
    """Create a Three.js geometry node for a wall."""
    length = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
    angle = math.atan2(wall.y2 - wall.y1, wall.x2 - wall.x1)
    cx = (wall.x1 + wall.x2) / 2
    cy = (wall.y1 + wall.y2) / 2
    height = wall.height_m or 3.0
    
    return {
        "id": f"wall-{wall.id}",
        "type": "box",
        "geometry": {
            "center": [cx, cy, height / 2],
            "width": length,
            "height": height,
            "depth": wall.thickness_m,
        },
        "rotation": [0, 0, angle],
        "material": {
            "color": "#888888",  # gray
            "opacity": 0.6,
        },
        "properties": {
            "type": "wall",
            "thickness_m": wall.thickness_m,
            "height_m": height,
        },
    }


def _build_grid_node(grid) -> Optional[Dict[str, Any]]:
    """Create a Three.js geometry node for a grid line."""
    if not grid:
        return None
    
    # Grid lines are typically infinite reference axes; render as thin lines
    return {
        "id": f"grid-{grid.id if hasattr(grid, 'id') else id(grid)}",
        "type": "line",
        "geometry": {
            "start": getattr(grid, "start", [0, 0, 0]),
            "end": getattr(grid, "end", [10, 0, 0]),
        },
        "material": {
            "color": "#cccccc",
            "opacity": 0.3,
        },
    }


def _utilization_color(util: float) -> str:
    """Return RGB hex color based on member utilization (0.0-1.0+).
    
    Green → Yellow → Orange → Red gradient for increasing stress.
    """
    if util <= 0.5:
        return "#22c55e"  # green (safe)
    elif util <= 0.7:
        return "#84cc16"  # lime (normal)
    elif util <= 0.85:
        return "#eab308"  # yellow (caution)
    elif util <= 1.0:
        return "#f97316"  # orange (near limit)
    else:
        return "#dc2626"  # red (over limit)


def export_gltf(scene_data: Dict[str, Any], project_id: int) -> str:
    """Export 3D scene to glTF 2.0 format.
    
    This is a simplified implementation that stores the scene as JSON.
    A full glTF exporter would require additional geometry serialization.
    
    Args:
        scene_data: Three.js scene dict from build_3d_scene()
        project_id: Project identifier
    
    Returns:
        Path to the exported .gltf file
    """
    from app.core.storage import storage_root
    from pathlib import Path
    import json
    
    exports = storage_root() / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    
    filename = f"scene-p{project_id}-{_stamp_slug()}.gltf"
    path = exports / filename
    
    # Write glTF JSON (full format would include binary geometry buffers)
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{
            "nodes": list(range(len(scene_data.get("nodes", [])))),
        }],
        "nodes": [
            {
                "name": node["id"],
                "mesh": i,
                **({
                    "translation": node["geometry"]["center"]
                } if "geometry" in node else {}),
            }
            for i, node in enumerate(scene_data.get("nodes", []))
        ],
        "meshes": [
            {
                "name": node["id"],
                "primitives": [{
                    "material": 0,
                    "attributes": {"POSITION": 0},
                }],
            }
            for node in scene_data.get("nodes", [])
        ],
        "materials": [{
            "name": "default",
            "pbrMetallicRoughness": {"baseColorFactor": [0.8, 0.8, 0.8, 1.0]},
        }],
        "extensions": {},
        "extensionsUsed": [],
        "extensionsRequired": [],
    }
    
    with open(path, "w") as f:
        json.dump(gltf, f, indent=2)
    
    log.info("glTF scene exported: %s", path)
    return str(path)


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _stamp_slug() -> str:
    """Generate a random slug for file naming."""
    import secrets
    return secrets.token_hex(4)
