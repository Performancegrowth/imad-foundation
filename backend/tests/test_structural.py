"""Sprint 5 — Structural engine (analytic fallback) tests."""
from __future__ import annotations

import pytest

from app.models.plan_data import Beam, Column, GridLine, PlanData, Wall
from app.services.structural_engine import OpenSeesEngine, StructuralError


def _simple_frame() -> PlanData:
    """A 2-bay × 1-bay single-storey moment frame."""
    plan = PlanData(source="test", label="2-bay frame")
    plan.columns = [
        Column(id="c1", cx=0.0, cy=0.0, size_m=0.3, height=3.0),
        Column(id="c2", cx=6.0, cy=0.0, size_m=0.3, height=3.0),
        Column(id="c3", cx=12.0, cy=0.0, size_m=0.3, height=3.0),
    ]
    plan.beams = [
        Beam(id="b1", x1=0.0, y1=0.0, x2=6.0, y2=0.0, width_m=0.3, depth_m=0.5),
        Beam(id="b2", x1=6.0, y1=0.0, x2=12.0, y2=0.0, width_m=0.3, depth_m=0.5),
    ]
    plan.walls = [
        Wall(id="w1", x1=0.0, y1=0.0, x2=12.0, y2=0.0),
    ]
    plan.grids = [
        GridLine(id="v1", orientation="vertical", position=0.0, label="1"),
        GridLine(id="v2", orientation="vertical", position=6.0, label="2"),
        GridLine(id="v3", orientation="vertical", position=12.0, label="3"),
    ]
    plan.stories = 1
    return plan


def test_analyze_completes_with_analytic_solver():
    engine = OpenSeesEngine()
    result = engine.analyze(_simple_frame())

    assert result.status == "completed"
    assert result.diagnostics.solver == "analytic"
    # beams carry positive moment
    assert result.max_moment_kNm > 0
    # columns carry axial load
    assert result.max_axial_kN > 0
    # concrete design + BOQ are populated
    assert result.design["max_utilization"] >= 0
    assert result.boq["concrete_m3"] > 0


def test_analyze_survey_can_be_optional():
    from app.models.survey_data import SurveyReading

    engine = OpenSeesEngine()
    survey = SurveyReading(soil_bearing_capacity_kpa=200, groundwater_depth_m=2.0)
    result = engine.analyze(_simple_frame(), survey=survey)
    assert result.status == "completed"


def test_empty_plan_raises():
    with pytest.raises(StructuralError):
        OpenSeesEngine().analyze(PlanData(source="test"))


def test_periods_are_positive():
    result = OpenSeesEngine().analyze(_simple_frame())
    assert all(p > 0 for p in result.periods_s)