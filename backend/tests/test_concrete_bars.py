"""Roadmap #9c — real bar selection: design selects actual cages (Ø/count),
compliance verifies them (kills rho_provided_assumed), and the BOQ rebar
take-off uses the real layouts instead of a blanket 100 kg/m³ ratio."""
import math

import pytest

from app.models.plan_data import PlanData
from app.services.compliance_engine import ComplianceEngine
from app.services.concrete_design import (
    BAR_AREA_MM2,
    ConcreteDesigner,
    preliminary_boq,
    round_up_to_bar_layout,
)

_SMOKE_PLAN = {
    "source": "bars-test",
    "label": "bars-test",
    "stories": 1,
    "columns": [
        {"id": "c1", "cx": 0.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
        {"id": "c2", "cx": 5.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
        {"id": "c3", "cx": 10.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
    ],
    "beams": [{"id": "b1", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 0.0,
               "width_m": 0.3, "depth_m": 0.5}],
    "walls": [],
    "grids": [],
}


def _analyze():
    from app.services.structural_engine import OpenSeesEngine

    return OpenSeesEngine().analyze(PlanData(**_SMOKE_PLAN))


# ── bar layout selector ──────────────────────────────────────────────────────
def test_bar_layout_provides_at_least_required_area():
    need = 800.0
    layout = round_up_to_bar_layout(need, b_mm=300.0, kind="beam")
    assert layout["as_provided_mm2"] >= need
    assert layout["bars"] * BAR_AREA_MM2[layout["bar_diameter_mm"]] == \
        pytest.approx(layout["as_provided_mm2"])
    assert layout["arrangement"] == f"{layout['bars']}Ø{layout['bar_diameter_mm']}"


def test_bar_layout_respects_beam_width():
    # A very wide demand in a narrow beam must fall back to a double layer
    # rather than claim an impossible single-layer fit.
    need = 6 * BAR_AREA_MM2[25]
    layout = round_up_to_bar_layout(need, b_mm=150.0, kind="beam")
    assert layout["fits_one_layer"] is False
    assert "double layer" in layout["arrangement"]


def test_bar_layout_deterministic():
    a = round_up_to_bar_layout(900.0, b_mm=300.0, kind="column")
    b = round_up_to_bar_layout(900.0, b_mm=300.0, kind="column")
    assert a == b
    assert a["bars"] in (4, 6, 8, 12, 16)      # even, corner-symmetric


# ── design uses real plan sections + real bars ───────────────────────────────
def test_design_uses_real_plan_sections():
    plan = PlanData(**_SMOKE_PLAN)
    forces = _analyze().member_forces
    design = ConcreteDesigner().design(forces, plan=plan)

    beam = next(b for b in design["beams"] if b["element"] == "b1")
    assert beam["width_mm"] == 300 and beam["depth_mm"] == 500   # from plan
    col = design["columns"][0]
    assert col["section_mm"] == 300                              # from plan
    for entry in design["beams"] + design["columns"]:
        assert entry["bars"] >= 2 and entry["bar_diameter_mm"] >= 16
        assert entry["as_provided_mm2"] >= entry["as_required_mm2"]
        assert 0 < entry["rho_provided"] <= 0.08


def test_column_min_steel_is_one_percent():
    # A lightly-loaded column must still get ≥ 1 % steel (§10.6.1.1).
    plan = PlanData(**_SMOKE_PLAN)
    forces = _analyze().member_forces
    design = ConcreteDesigner().design(forces, plan=plan)
    col = design["columns"][0]
    assert col["as_provided_mm2"] >= 0.01 * col["ag_mm2"]
    assert 0.01 <= col["rho_provided"] <= 0.08


# ── compliance reads the real cages ──────────────────────────────────────────
def test_compliance_verifies_real_bars_from_design():
    result = _analyze()
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN),
                              analysis={"design": result.design,
                                        "member_forces": [
                                            f.__dict__ for f in result.member_forces]})
    beam_check = engine.check_beam_reinforcement()
    assert beam_check["details"]["source"] == "design pass (roadmap #9c)"
    assert beam_check["details"]["governing_beam"] == "b1"
    assert "Ø" in beam_check["details"]["bar_layout"]
    assert beam_check["details"]["rho_provided"] >= beam_check["details"]["rho_min"]

    col_check = engine.check_column_reinforcement()
    assert col_check["details"]["source"] == "design pass (roadmap #9c)"
    assert "Ø" in col_check["details"]["bar_layout"]
    assert 1.0 <= col_check["details"]["rho_min_percent"] <= \
        col_check["details"]["rho_max_percent"] <= 8.0


def test_compliance_falls_back_to_assumed_without_design():
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN))
    assert engine.check_beam_reinforcement()["details"]["source"] == \
        "assumed (no design attached)"
    assert engine.check_column_reinforcement()["details"]["source"] == \
        "assumed (no design attached)"


# ── BOQ rebar take-off from real bars ────────────────────────────────────────
def test_preliminary_boq_uses_real_bar_layouts():
    plan = PlanData(**_SMOKE_PLAN)
    result = _analyze()
    boq = preliminary_boq(plan, result.member_forces,
                          materials=plan.materials, design=result.design)
    assert boq["rebar_source"] == "real bar layouts (roadmap #9c)"
    assert boq["rebar_kg"] > 0


def test_preliminary_boq_discloses_assumed_fallback():
    plan = PlanData(**_SMOKE_PLAN)
    forces = _analyze().member_forces
    boq = preliminary_boq(plan, forces, materials=plan.materials)
    assert "assumed" in boq["rebar_source"]


# ── end-to-end: engine wires bars → design → boq ─────────────────────────────
def test_engine_wires_bars_through_design_and_boq():
    result = _analyze()
    beam = result.design["beams"][0]
    assert beam["width_mm"] == 300 and beam["depth_mm"] == 500
    assert beam["bars"] >= 2
    assert result.boq["rebar_source"] == "real bar layouts (roadmap #9c)"

    # The compliance engine, fed the same analysis payload the API stores,
    # verifies the real cages (no assumed rho anywhere in the design path).
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN),
                              analysis={"design": result.design})
    assert engine.check_beam_reinforcement()["details"]["source"].startswith(
        "design pass")