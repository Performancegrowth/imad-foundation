"""Stair design tests — ACI 318-19 §7.4 / SBC 304."""
import pytest
from app.services.concrete_design import stair_design, stair_geometry


def test_stair_geometry_3m():
    geo = stair_geometry(3.0, flight_angle_deg=33.0)
    assert geo["n_risers"] >= 2
    assert geo["n_treads"] == geo["n_risers"] - 1
    assert 150 < geo["riser_mm"] < 200       # typical riser range
    assert 250 < geo["tread_mm"] < 300       # typical tread range
    assert geo["flight_angle_deg"] == 33.0


def test_stair_geometry_deterministic():
    a = stair_geometry(3.0, 33.0)
    b = stair_geometry(3.0, 33.0)
    assert a == b


def test_stair_design_passes_residential():
    d = stair_design(3.0, width_m=1.2, live_kpa=2.0)
    assert d["ok"] is True
    assert d["shear"]["ok"] is True
    assert d["deflection"]["ok"] is True
    assert d["utilization"] <= 1.05


def test_stair_design_passes_corridor():
    d = stair_design(3.0, width_m=1.2, live_kpa=4.0)
    assert d["ok"] is True
    assert d["shear"]["ratio"] < 1.0


def test_stair_bars_selected():
    d = stair_design(3.0, width_m=1.2, live_kpa=4.0)
    bars = d["flexure"]["bars"]
    assert bars["bar_diameter_mm"] in (16, 18, 20, 22, 25)
    assert bars["spacing_mm"] in (100, 125, 150, 175, 200)
    assert bars["as_provided_mm2"] >= d["flexure"]["req_as_mm2"]


def test_stair_boq_positive():
    d = stair_design(3.0, width_m=1.2, live_kpa=4.0)
    assert d["boq"]["concrete_m3"] > 0
    assert d["boq"]["rebar_kg"] > 0


def test_stair_3d_nodes_generated():
    d = stair_design(3.0, width_m=1.2, live_kpa=4.0)
    assert len(d["nodes"]) > 0
    # Should have steps + 1 landing
    assert len(d["nodes"]) == d["geometry"]["n_treads"] + 1


def test_stair_development_length():
    d = stair_design(3.0, width_m=1.2, live_kpa=4.0)
    assert d["ld_mm"] > 0


def test_stair_higher_load_more_steel():
    d_low = stair_design(3.0, width_m=1.2, live_kpa=2.0)
    d_high = stair_design(3.0, width_m=1.2, live_kpa=6.0)
    assert d_high["flexure"]["prov_as_mm2"] >= d_low["flexure"]["prov_as_mm2"]


def test_stair_slab_auto_sizing():
    """Slab thickness should increase with span to satisfy deflection."""
    d_short = stair_design(2.5, width_m=1.2, live_kpa=4.0)
    d_tall = stair_design(4.0, width_m=1.2, live_kpa=4.0)
    assert d_tall["d_mm"] >= d_short["d_mm"]


def test_compliance_engine_includes_stair_check():
    """The compliance engine should run a stair design check."""
    from app.models.plan_data import PlanData, Column
    from app.services.compliance_engine import ComplianceEngine
    plan = PlanData(stories=1, columns=[Column(id="c0", cx=0, cy=0, size_m=0.3, height=3.0)])
    engine = ComplianceEngine(plan)
    report = engine.run_all()
    names = [c["check_name"] for c in report["checks"]]
    assert any("stair" in n.lower() for n in names)