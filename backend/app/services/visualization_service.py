"""
Sprint 9A — Building visualisation service.

Turns a structural plan into a render-ready architectural scene:

* floor slabs and roof per level,
* structural skeleton (columns + beams),
* extruded perimeter/partition walls with punched window ribbons,
* explicit floor-level table for the viewer's floor selector.

Scenes are delivered as lightweight parametric boxes (``kind: "box"`` +
size/position) that Three.js renders directly, and can be serialised to a
valid minimal glTF 2.0 document (positions + indices in one base64 buffer)
for interchange into other DCC/BIM tools.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import struct
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger("imad.viz")

# Palette — matches the product design system.
COLORS = {
    "slab": "#8A94A6",
    "column": "#0A5C36",
    "beam": "#3E7C54",
    "wall": "#D8DEE9",
    "glass": "#9CC7DE",
    "roof": "#5B6472",
}
STORY_HEIGHT_M = 3.0
PARAPET_M = 0.9


def _hex_to_rgb(hex_color: str) -> List[float]:
    """'#0A5C36' → linear-ish [r, g, b] floats in 0–1 for glTF baseColorFactor."""
    h = (hex_color or "#888888").lstrip("#")
    if len(h) != 6:
        h = "888888"
    return [round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4)]


@dataclass
class ViewportMesh:
    """One renderable primitive (box today, extensible to cylinders etc.)."""

    component: str                       # 'slab' | 'column' | 'beam' | 'wall' | 'window' | 'roof'
    geometry_kind: str                    # 'box'
    size: List[float] = field(default_factory=lambda: [1, 1, 1])       # sx, sy, sz
    position: List[float] = field(default_factory=lambda: [0, 0, 0])   # centre, z-up
    color: str = "#0A5C36"
    level: int = 0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ViewportScene:
    """Complete renderable building (units, levels, meshes, metadata)."""

    units: str = "meter"
    up_axis: str = "Z"
    levels: List[Dict[str, Any]] = field(default_factory=list)         # [{level, elev_m}]
    meshes: List[ViewportMesh] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisualizationService:
    """Builds architectural scenes from PlanData payloads."""

    def build_scene(self, plan_data: Dict[str, Any],
                    options: Optional[Dict[str, Any]] = None) -> ViewportScene:
        opts = options or {}
        story_h = float(opts.get("story_height_m", STORY_HEIGHT_M))
        stories = max(1, int(plan_data.get("stories", 1)))
        walls_in = plan_data.get("walls") or []
        columns_in = plan_data.get("columns") or []
        beams_in = plan_data.get("beams") or []
        window_ratio = float(opts.get("window_ratio", 0.35))     # façade openness

        # Envelope from element bounds (fallback: 12 × 9 m demo envelope).
        xs, ys = [0.0], [0.0]
        for c in columns_in:
            xs.append(float(c.get("cx", 0))); ys.append(float(c.get("cy", 0)))
        for w in walls_in:
            for k in ("x1", "x2"):
                if k in w: xs.append(float(w[k]))
            for k in ("y1", "y2"):
                if k in w: ys.append(float(w[k]))
        min_x, max_x = (min(xs), max(xs)) if len(xs) > 1 else (0, 12)
        min_y, max_y = (min(ys), max(ys)) if len(ys) > 1 else (0, 9)
        env_l = max(max_x - min_x, 4.0)
        env_w = max(max_y - min_y, 4.0)
        cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0

        scene = ViewportScene(metadata={
            "stories": stories,
            "story_height_m": story_h,
            "envelope_m": {"length": round(env_l, 2), "width": round(env_w, 2)},
            "generator": "imad-visualization-service/1.0",
        })

        for level in range(stories):
            z0 = level * story_h
            scene.levels.append({"level": level, "elev_m": round(z0, 2)})
            # ── floor slab ────────────────────────────────────────────────
            scene.meshes.append(ViewportMesh(
                component="slab", geometry_kind="box",
                size=[round(env_l, 3), round(env_w, 3), 0.2],
                position=[cx, cy, round(z0 - 0.1, 3)],
                color=COLORS["slab"], level=level))
            # ── structural skeleton ────────────────────────────────────────
            for c in columns_in:
                s = float(c.get("size_m", 0.4))
                scene.meshes.append(ViewportMesh(
                    component="column", geometry_kind="box",
                    size=[s, s, story_h],
                    position=[float(c.get("cx", 0)), float(c.get("cy", 0)),
                              round(z0 + story_h / 2.0, 3)],
                    color=COLORS["column"], level=level))
            for b in beams_in:
                length = math.hypot(float(b.get("x2", 0)) - float(b.get("x1", 0)),
                                    float(b.get("y2", 0)) - float(b.get("y1", 0)))
                if length < 0.3:
                    continue
                along_x = abs(float(b.get("y2", 0)) - float(b.get("y1", 0))) < 1e-6
                bw = float(b.get("width_m", 0.25))
                bd = float(b.get("depth_m", 0.55))
                scene.meshes.append(ViewportMesh(
                    component="beam", geometry_kind="box",
                    size=[round(length, 3) if along_x else bw,
                          bw if along_x else round(length, 3), bd],
                    position=[round((float(b.get("x1", 0)) + float(b.get("x2", 0))) / 2, 3),
                              round((float(b.get("y1", 0)) + float(b.get("y2", 0))) / 2, 3),
                              round(z0 + story_h - bd / 2.0, 3)],
                    color=COLORS["beam"], level=level))

            # ── perimeter/partition walls with punched window ribbons ────
            for w in walls_in:
                x1, y1 = float(w.get("x1", 0)), float(w.get("y1", 0))
                x2, y2 = float(w.get("x2", 0)), float(w.get("y2", 0))
                length = math.hypot(x2 - x1, y2 - y1)
                if length < 0.3:
                    continue
                thickness = float(w.get("thickness_m", 0.2))
                along_x = abs(y2 - y1) < 1e-6
                wall_z = z0 + story_h / 2.0
                # solid wall body
                scene.meshes.append(ViewportMesh(
                    component="wall", geometry_kind="box",
                    size=[round(length, 3) if along_x else thickness,
                          thickness if along_x else round(length, 3), story_h],
                    position=[(x1 + x2) / 2, (y1 + y2) / 2, round(wall_z, 3)],
                    color=COLORS["wall"], level=level))
                # window ribbon punched into exterior walls only
                is_exterior = (
                    abs(x1 - min_x) < 0.05 or abs(x1 - max_x) < 0.05 or
                    abs(y1 - min_y) < 0.05 or abs(y1 - max_y) < 0.05 or
                    abs(x2 - min_x) < 0.05 or abs(x2 - max_x) < 0.05 or
                    abs(y2 - min_y) < 0.05 or abs(y2 - max_y) < 0.05)
                if is_exterior and length > 1.2:
                    ribbon_h = story_h * window_ratio
                    sill_h = story_h * 0.35
                    scene.meshes.append(ViewportMesh(
                        component="window", geometry_kind="box",
                        size=[round(length * 0.8, 3) if along_x else thickness + 0.04,
                              thickness + 0.04 if along_x else round(length * 0.8, 3),
                              round(ribbon_h, 3)],
                        position=[(x1 + x2) / 2, (y1 + y2) / 2,
                                  round(z0 + sill_h + ribbon_h / 2.0, 3)],
                        color=COLORS["glass"], level=level,
                        properties={"glazing": "double", "openness": window_ratio}))

        # ── roof slab + parapet capping the top level ────────────────────
        top_z = stories * story_h
        scene.meshes.append(ViewportMesh(
            component="roof", geometry_kind="box",
            size=[round(env_l, 3), round(env_w, 3), 0.15],
            position=[cx, cy, round(top_z + 0.075, 3)],
            color=COLORS["roof"], level=stories - 1))
        for (px, py, sx, sy) in (
            (min_x + env_l / 2, min_y, env_l, 0.15),
            (min_x + env_l / 2, max_y, env_l, 0.15),
            (min_x, min_y + env_w / 2, 0.15, env_w),
            (max_x, min_y + env_w / 2, 0.15, env_w),
        ):
            scene.meshes.append(ViewportMesh(
                component="wall", geometry_kind="box",
                size=[round(sx, 3), round(sy, 3), PARAPET_M],
                position=[round(px, 3), round(py, 3), round(top_z + PARAPET_M / 2, 3)],
                color=COLORS["wall"], level=stories - 1))
        log.info("Scene built: %d levels, %d meshes", len(scene.levels), len(scene.meshes))
        return scene

    def to_dict(self, scene: ViewportScene) -> Dict[str, Any]:
        """JSON payload consumed by the frontend Three.js viewer."""
        return {
            "units": scene.units,
            "up_axis": scene.up_axis,
            "levels": scene.levels,
            "metadata": scene.metadata,
            "meshes": [asdict(m) for m in scene.meshes],
        }

    def to_gltf_json(self, scene: ViewportScene) -> Dict[str, Any]:
        """Minimal valid glTF 2.0 document: baked world-space unit cubes,
        one primitive + material per colour, single base64 data-URI buffer."""
        # 36 vertices (12 triangles) of a unit cube centred on the origin.
        CUBE = [
            (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5),
            (-.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5),
            (.5, -.5, -.5), (-.5, -.5, -.5), (-.5, .5, -.5),
            (.5, -.5, -.5), (-.5, .5, -.5), (.5, .5, -.5),
            (-.5, .5, .5), (.5, .5, .5), (.5, .5, -.5),
            (-.5, .5, .5), (.5, .5, -.5), (-.5, .5, -.5),
            (-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5),
            (-.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5),
            (.5, -.5, .5), (.5, -.5, -.5), (.5, .5, -.5),
            (.5, -.5, .5), (.5, .5, -.5), (.5, .5, .5),
            (-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5),
            (-.5, -.5, -.5), (-.5, .5, .5), (-.5, .5, -.5),
        ]

        by_color: Dict[str, List[ViewportMesh]] = {}
        for m in scene.meshes:
            by_color.setdefault(m.color, []).append(m)

        materials: List[Dict[str, Any]] = []
        primitives: List[Dict[str, Any]] = []
        buffer_views: List[Dict[str, Any]] = []
        accessors: List[Dict[str, Any]] = []
        binary = b""

        for color, group in by_color.items():
            positions: List[float] = []
            lo = [1e9, 1e9, 1e9]
            hi = [-1e9, -1e9, -1e9]
            for m in group:
                sx, sy, sz = m.size
                px, py, pz = m.position
                for vx, vy, vz in CUBE:
                    x, y, z = vx * sx + px, vy * sy + py, vz * sz + pz
                    positions.extend((x, y, z))
                    lo = [min(lo[0], x), min(lo[1], y), min(lo[2], z)]
                    hi = [max(hi[0], x), max(hi[1], y), max(hi[2], z)]
            view = {
                "buffer": 0,
                "byteOffset": len(binary),
                "byteLength": len(positions) * 4,
                "target": 34962,
            }
            binary += struct.pack(f"<{len(positions)}f", *positions)
            idx = len(accessors)
            buffer_views.append(view)
            accessors.append({
                "bufferView": idx, "componentType": 5126,
                "count": len(positions) // 3, "type": "VEC3",
                "min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi],
            })
            materials.append({
                "name": color, "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": _hex_to_rgb(color),
                    "metallicFactor": 0.1, "roughnessFactor": 0.85,
                },
            })
            primitives.append({
                "attributes": {"POSITION": idx}, "material": len(materials) - 1,
                "mode": 4,
            })

        return {
            "asset": {
                "version": "2.0",
                "generator": "imad-visualization-service/1.0",
            },
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"name": scene.metadata.get("generator", "imad"), "mesh": 0}],
            "meshes": [{"primitives": primitives,
                        "extras": {"levels": scene.levels,
                                   "metadata": scene.metadata}}],
            "materials": materials,
            "bufferViews": buffer_views,
            "accessors": accessors,
            "buffers": [{
                "byteLength": len(binary),
                "uri": "data:application/octet-stream;base64,"
                       + base64.b64encode(binary).decode("ascii"),
            }],
        }