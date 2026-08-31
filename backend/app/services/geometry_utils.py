"""
Sprint 6 — 2D geometry processing with Shapely (optional dependency).

Wraps Shapely for the spatial operations the engineering pipeline needs —
accurate floor-footprint envelopes, room polygonisation from wall
centre-lines, collinear wall merging and geometric QA. Degrades to the
older bounding-box heuristics when Shapely is not installed, so the API and
test suite keep working in a lean environment (same pattern as
``app/core/units.py``'s Pint wrapper).
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from app.models.plan_data import GeoPoint, PlanData, Room, Wall

log = logging.getLogger("imad.geometry")

try:
    from shapely.geometry import LineString, Point, Polygon, box
    from shapely.ops import polygonize, unary_union

    SHAPELY_AVAILABLE = True
except Exception:  # pragma: no cover - Shapely is optional
    SHAPELY_AVAILABLE = False


class GeometryError(Exception):
    """Raised when a geometric operation cannot be performed."""


# ─────────────────────────────────────────────── floor footprint ───────────
def floor_envelope(plan: PlanData) -> Dict[str, Any]:
    """Accurate usable floor footprint from wall centre-lines.

    Returns ``{"area_m2", "perimeter_m", "approximate"}`` plus (when rooms
    are polygonisable) a ``"polygon"`` key. With Shapely the footprint is the
    unary union of the rooms polygonised from the closed wall centre-line
    loops — a true usable floor area (e.g. 48 m² for an 8×6 m room), not a
    bounding box. Open networks / no Shapely fall back to the bounding-box,
    marked ``approximate=True``.
    """
    if not SHAPELY_AVAILABLE or not plan.walls:
        return _bbox_envelope(plan)

    rooms = derive_rooms(plan, min_area_m2=0.0)
    if rooms:
        polys = [Polygon([(p.x, p.y) for p in r.boundary]) for r in rooms]
        union = unary_union(polys)
        if union is not None and not union.is_empty:
            return {"area_m2": round(float(union.area), 2),
                    "perimeter_m": round(float(union.length), 2),
                    "approximate": False, "polygon": union}

    # Open network / no closed rooms → bounding box (as before Shapely).
    return _bbox_envelope(plan)


def _bbox_envelope(plan: PlanData) -> Dict[str, Any]:
    """Bounding-box fallback used when Shapely is unavailable or empty."""
    b = plan.bounds()
    w = max((b["max_x"] - b["min_x"]), 1.0)
    h = max((b["max_y"] - b["min_y"]), 1.0)
    return {"area_m2": round(w * h, 2), "perimeter_m": round(2 * (w + h), 2),
            "approximate": True}
# ─────────────────────────────────────────────────────── room detection ─────
def derive_rooms(plan: PlanData, min_area_m2: float = 0.5) -> List[Room]:
    """Polygonise wall centre-lines into enclosed rooms.

    Each closed loop of wall centre-lines becomes a :class:`Room` with its
    boundary coordinates and an accurate ``area_m2`` (Shapely polygon area).
    Returns an empty list when Shapely is unavailable or the wall network
    is not closed.
    """
    if not SHAPELY_AVAILABLE or len(plan.walls) < 3:
        return []
    lines = [LineString([(w.x1, w.y1), (w.x2, w.y2)]) for w in plan.walls]
    rooms: List[Room] = []
    for idx, poly in enumerate(polygonize(lines)):
        area = float(getattr(poly, "area", 0.0))
        if area < min_area_m2:
            continue
        boundary = [GeoPoint(x=round(float(p[0]), 3), y=round(float(p[1]), 3))
                    for p in poly.exterior.coords]
        rooms.append(Room(id=f"r{idx}", label=f"Room {idx + 1}",
                          boundary=boundary, area_m2=round(area, 2), level=0))
    return rooms


# ─────────────────────────────────────────────── collinear wall merging ─────
def _wall_axis(wall: Wall) -> str:
    return "x" if abs(wall.x2 - wall.x1) >= abs(wall.y2 - wall.y1) else "y"


def merge_collinear_walls(plan: PlanData, tolerance: float = 0.15) -> List[Wall]:
    """Merge touching/near-collinear wall runs into single walls.

    Buckets walls by dominant axis + perpendicular line position + storey,
    then stitches overlapping or gap-tolerant neighbours into one run.
    Pure-Python (no Shapely needed) so CAD/IFC output is always clean.
    """
    if len(plan.walls) < 2:
        return list(plan.walls)

    buckets: Dict[Any, List[Wall]] = {}
    for w in plan.walls:
        axis = _wall_axis(w)
        pos = round(w.y1, 3) if axis == "x" else round(w.x1, 3)
        buckets.setdefault((axis, pos, w.level), []).append(w)

    merged: List[Wall] = []
    for (axis, pos, level), walls in buckets.items():
        run = sorted(walls, key=lambda w: (min(w.x1, w.x2) if axis == "x"
                                           else min(w.y1, w.y2)))
        cur_lo, cur_hi = None, None
        rep = run[0]
        for w in run:
            lo = min(w.x1, w.x2) if axis == "x" else min(w.y1, w.y2)
            hi = max(w.x1, w.x2) if axis == "x" else max(w.y1, w.y2)
            if cur_lo is None:
                cur_lo, cur_hi, rep = lo, hi, w
            elif lo <= cur_hi + tolerance:
                cur_hi = max(cur_hi, hi)
            else:
                merged.append(_span_wall(rep, axis, cur_lo, cur_hi))
                cur_lo, cur_hi, rep = lo, hi, w
        if cur_lo is not None:
            merged.append(_span_wall(rep, axis, cur_lo, cur_hi))
    return merged


def _span_wall(rep: Wall, axis: str, lo: float, hi: float) -> Wall:
    if axis == "x":
        return Wall(id=rep.id, x1=lo, y1=rep.y1, x2=hi, y2=rep.y1,
                    thickness_m=rep.thickness_m, level=rep.level,
                    height_m=rep.height_m, kind=rep.kind)
    return Wall(id=rep.id, x1=rep.x1, y1=lo, x2=rep.x1, y2=hi,
                thickness_m=rep.thickness_m, level=rep.level,
                height_m=rep.height_m, kind=rep.kind)
# ─────────────────────────────────────────────────── geometric QA ───────────
def validation_warnings(plan: PlanData) -> List[str]:
    """Return human-readable geometry issues found in a plan.

    Checks (with Shapely): columns sitting outside the floor footprint;
    always: zero-length walls and non-finite coordinates.
    """
    issues: List[str] = []
    for i, w in enumerate(plan.walls):
        length = math.hypot(w.x2 - w.x1, w.y2 - w.y1)
        if length < 1e-9:
            issues.append(f"Wall {w.id or i} has zero length.")
    for c in plan.columns:
        if not (math.isfinite(c.cx) and math.isfinite(c.cy)):
            issues.append(f"Column {c.id} has non-finite coordinates.")

    if SHAPELY_AVAILABLE:
        env = floor_envelope(plan)
        poly = env.get("polygon") if not env.get("approximate") else None
        if poly is not None:
            for c in plan.columns:
                pt = Point(c.cx, c.cy)
                if not poly.contains(pt) and poly.distance(pt) > 0.25:
                    issues.append(f"Column {c.id} sits outside the floor envelope.")
    return issues


# ─────────────────────────────────────────────── plan enrichment ────────────
def enrich_plan(plan: PlanData) -> PlanData:
    """Fill rooms + footprint metadata from wall geometry.

    Call at the end of a CAD/image/IFC parse so downstream analysis and BOQ
    can use real room areas and occupied footprint instead of bounding boxes.
    """
    plan.rooms = derive_rooms(plan)
    try:
        env = floor_envelope(plan)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("floor_envelope failed for %s: %s", plan.source, exc)
        env = {"area_m2": 0.0, "perimeter_m": 0.0, "approximate": True}
    plan.original.setdefault("geometry", {})
    plan.original["geometry"]["floor_area_m2"] = env["area_m2"]
    plan.original["geometry"]["perimeter_m"] = env["perimeter_m"]
    plan.original["geometry"]["approx"] = env["approximate"]
    plan.original["geometry"]["shapely"] = SHAPELY_AVAILABLE
    return plan