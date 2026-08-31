"""Sprint 6 — Shapely-backed 2D geometry processing tests."""
from __future__ import annotations

import pytest

from app.models.plan_data import Column, PlanData, Wall
from app.services import geometry_utils as geo


def _rect_plan(lx: float = 8.0, ly: float = 6.0) -> PlanData:
    """Closed 4-wall room so polygonisation / envelope have a real area."""
    plan = PlanData(source="test")
    plan.walls = [
        Wall(id="w1", x1=0, y1=0, x2=lx, y2=0, thickness_m=0.2),
        Wall(id="w2", x1=lx, y1=0, x2=lx, y2=ly, thickness_m=0.2),
        Wall(id="w3", x1=lx, y1=ly, x2=0, y2=ly, thickness_m=0.2),
        Wall(id="w4", x1=0, y1=ly, x2=0, y2=0, thickness_m=0.2),
    ]
    return plan


def test_floor_envelope_exact_for_closed_room():
    if not geo.SHAPELY_AVAILABLE:
        pytest.skip("shapely not installed")
    plan = _rect_plan(lx=8.0, ly=6.0)
    env = geo.floor_envelope(plan)
    assert env["approximate"] is False
    assert env["area_m2"] == 48.0
    assert env["perimeter_m"] == 28.0


def test_floor_envelope_bbox_fallback_without_shapely(monkeypatch):
    plan = _rect_plan(lx=8.0, ly=6.0)
    monkeypatch.setattr(geo, "SHAPELY_AVAILABLE", False)
    env = geo.floor_envelope(plan)
    assert env["approximate"] is True
    assert env["area_m2"] == 48.0  # bbox of an 8×6 room == its interior


def test_floor_envelope_open_plan_falls_back_to_bbox():
    if not geo.SHAPELY_AVAILABLE:
        pytest.skip("shapely not installed")
    plan = PlanData(source="test")
    plan.walls = [Wall(id="w1", x1=0, y1=0, x2=10, y2=0)]  # single open run
    env = geo.floor_envelope(plan)
    assert env["approximate"] is True
    assert env["area_m2"] == 10.0  # bbox: 10 × max(depth, 1.0)


def test_derive_rooms_polygonises_closed_loops():
    if not geo.SHAPELY_AVAILABLE:
        pytest.skip("shapely not installed")
    plan = _rect_plan(lx=6.0, ly=4.0)
    rooms = geo.derive_rooms(plan)
    assert len(rooms) == 1
    assert rooms[0].area_m2 == 24.0
    assert len(rooms[0].boundary) >= 4  # closed polygon


def test_derive_rooms_empty_for_open_network():
    if not geo.SHAPELY_AVAILABLE:
        pytest.skip("shapely not installed")
    plan = PlanData(source="test")
    plan.walls = [
        Wall(id="w1", x1=0, y1=0, x2=8, y2=0),
        Wall(id="w2", x1=8, y1=0, x2=8, y2=6),
    ]  # no closed loop
    assert geo.derive_rooms(plan) == []


def test_merge_collinear_walls_joins_touching_runs():
    plan = PlanData(source="test")
    plan.walls = [
        Wall(id="a", x1=0, y1=2, x2=4, y2=2),
        Wall(id="b", x1=4, y1=2, x2=10, y2=2),
        Wall(id="c", x1=0, y1=5, x2=10, y2=5),
    ]
    merged = geo.merge_collinear_walls(plan)
    # top run (y=2) collapses from 2 walls to 1; the parallel y=5 stays separate
    runs_at_y2 = [w for w in merged if abs(w.y1 - 2.0) < 1e-9 and abs(w.y2 - 2.0) < 1e-9]
    assert len(runs_at_y2) == 1
    assert abs(runs_at_y2[0].x1 - 0.0) < 1e-6
    assert abs(runs_at_y2[0].x2 - 10.0) < 1e-6


def test_validation_flags_outside_columns_and_zero_walls():
    if not geo.SHAPELY_AVAILABLE:
        pytest.skip("shapely not installed")
    plan = _rect_plan()
    plan.columns = [
        Column(id="c1", cx=3, cy=2),     # inside footprint
        Column(id="c2", cx=50, cy=50),   # far outside
    ]
    plan.walls.append(Wall(id="w5", x1=2, y1=2, x2=2, y2=2))  # degenerate
    issues = geo.validation_warnings(plan)
    assert any("c2" in i for i in issues)
    assert any("w5" in i for i in issues)
    assert not any("c1" in i for i in issues)


def test_enrich_plan_fills_rooms_and_metadata():
    if not geo.SHAPELY_AVAILABLE:
        pytest.skip("shapely not installed")
    plan = _rect_plan(lx=8.0, ly=6.0)
    geo.enrich_plan(plan)
    assert len(plan.rooms) == 1
    geom = plan.original["geometry"]
    assert geom["floor_area_m2"] == 48.0
    assert geom["shapely"] is True
    assert geom["approx"] is False