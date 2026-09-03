"""Roadmap #9a — SBC 301 §5.3 strength load combinations + engine envelope."""
import math

import pytest

from app.models.plan_data import PlanData
from app.services.load_combinations import (
    CODE_SOURCE,
    combine,
    envelope,
    strength_combinations,
)

# ── combination catalogue ────────────────────────────────────────────────────
def test_basic_catalogue_gravity_only():
    combos = strength_combinations(include_seismic=False)
    assert [c["name"] for c in combos] == ["1.4D", "1.2D + 1.6L"]
    assert all(c["source"] == CODE_SOURCE for c in combos)


def test_catalogue_with_seismic_and_wind():
    seismic = strength_combinations(include_seismic=True)
    assert len(seismic) == 4
    assert "0.9D + 1.0E" in [c["name"] for c in seismic]
    # No wind case is produced by the engine yet — wind combos stay opt-in.
    assert strength_combinations(include_seismic=False) != seismic
    assert all("W" not in c["factors"] for c in seismic)


# ── linear superposition ─────────────────────────────────────────────────────
def test_combine_is_linear_superposition():
    cases = {"D": 10.0, "L": 4.0}
    assert combine({"D": 1.4}, cases) == pytest.approx(14.0)
    assert combine({"D": 1.2, "L": 1.6}, cases) == pytest.approx(18.4)
    # Missing load cases contribute zero; extra ones are ignored.
    assert combine({"D": 1.2, "L": 1.6}, {}) == 0.0
    assert combine({"D": 1.4}, {"D": 10.0, "L": 4.0, "E": 5.0}) == pytest.approx(14.0)


# ── envelope behaviour ───────────────────────────────────────────────────────
def test_envelope_picks_governing_combo():
    actions = {"D": {"M": 10.0, "V": 5.0, "N": 0.0},
               "L": {"M": 5.0, "V": 2.5, "N": 0.0}}
    env = envelope(actions, strength_combinations(include_seismic=True))
    # LC2: 1.2×10 + 1.6×5 = 20 governs over LC1 (14) and LC3 (17).
    assert env["M"]["value"] == pytest.approx(20.0)
    assert env["M"]["combo_id"] == "LC2"
    assert env["V"]["value"] == pytest.approx(10.0)
    assert env["V"]["combo_id"] == "LC2"


def test_envelope_tracks_tension_and_compression_separately():
    actions = {"D": {"N": 100.0}, "L": {"N": 0.0}, "E": {"N": -300.0}}
    env = envelope(actions, strength_combinations(include_seismic=True))
    # LC1: 140 · LC2: 120 · LC3: 1.2×100 − 300 = −180 · LC4: 0.9×100 − 300 = −210
    assert env["N_max"]["value"] == pytest.approx(140.0)
    assert env["N_max"]["combo_id"] == "LC1"
    assert env["N_min"]["value"] == pytest.approx(-210.0)
    assert env["N_min"]["combo_id"] == "LC4"


# ── engine integration ───────────────────────────────────────────────────────
_SMOKE_PLAN = {
    "source": "combo-test",
    "label": "combo-test",
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


def test_engine_designs_at_strength_level_not_service():
    result = _analyze()
    beam = next(f for f in result.member_forces if f.kind == "beam")

    # Reproduce the engine's dead/live split and the LC2 factored moment.
    # dead = 0.15 m slab × 25 + 1.5 SDL + 0.5 tiles = 5.75 kPa; live = 2.5 kPa.
    dead_kpa, live_kpa = 5.75, 2.5
    trib = 0.5                                   # _tributary_width for this plan
    span = 10.0
    w_d = dead_kpa * trib + 25.0 * 0.3 * 0.5     # + beam self-weight
    w_l = live_kpa * trib
    m_lc2 = 1.2 * (w_d * span ** 2 / 8) + 1.6 * (w_l * span ** 2 / 8)
    m_service = (w_d + w_l) * span ** 2 / 8

    assert beam.moment_kNm == pytest.approx(m_lc2, abs=0.05)
    assert beam.moment_kNm > m_service           # factored, not service demand
    assert beam.load_combo == "1.2D + 1.6L"
    # Deflection stays a service-level (unfactored) quantity.
    assert beam.deflection_mm == pytest.approx(
        5 * (w_d + w_l) * span ** 4 / 384 / (30e6 * (0.3 * 0.5 ** 3) / 12) * 1000,
        rel=0.01)


def test_engine_records_combinations_and_traceability():
    result = _analyze()
    combos = result.loads["load_combinations"]
    assert {"LC1", "LC2", "LC3", "LC4"} <= {c["id"] for c in combos}
    assert all(c["source"] == CODE_SOURCE for c in combos)
    assert result.loads["load_cases"]["live_kpa"] > 0
    assert result.loads["combination_notes"]     # honest omissions disclosed
    for f in result.member_forces:
        assert f.load_combo in {c["name"] for c in combos}
    assert result.diagnostics.stats["load_combinations"] == 4


def test_engine_analysis_is_deterministic():
    a = _analyze()
    b = _analyze()
    key = lambda r: [(f.element_id, f.moment_kNm, f.shear_kN, f.axial_kN,
                      f.deflection_mm, f.load_combo)
                     for f in r.member_forces]
    assert key(a) == key(b)
