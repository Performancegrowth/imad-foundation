"""Roadmap #9b — punching (two-way) shear check + fixed §22.4 column capacity.

The §22.4 check previously read an orphaned ``column_axials_kn`` key that
nothing populated (always ``warn "run analysis"``). Both checks now consume
the factored column axial demands produced by the #9a strength-combination
envelope in ``analysis.member_forces``.
"""
import math

import pytest

from app.models.plan_data import PlanData
from app.services.compliance_engine import ComplianceEngine

# One interior column (c5) surrounded by four perimeter columns. Only c5 has
# a meaningful demand for the punching pass/fail assertions so the governing
# (max-ratio) joint is never an edge joint.
_PLAN = {
    "source": "compliance-test",
    "label": "compliance-test",
    "stories": 1,
    "columns": [
        {"id": "c1", "cx": 0.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
        {"id": "c2", "cx": 20.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
        {"id": "c3", "cx": 0.0, "cy": 20.0, "size_m": 0.3, "height": 3.0},
        {"id": "c4", "cx": 20.0, "cy": 20.0, "size_m": 0.3, "height": 3.0},
        {"id": "c5", "cx": 10.0, "cy": 10.0, "size_m": 0.3, "height": 3.0},
    ],
    "beams": [],
    "walls": [],
    "grids": [],
    "materials": {"slab": "flat"},
}


def _engine(axial_c5: float, combo: str = "1.2D + 1.6L"):
    mf = [{"element_id": cid, "kind": "column", "axial_kN": 50.0,
           "load_combo": "1.4D"}
          for cid in ("c1", "c2", "c3", "c4")]
    mf.append({"element_id": "c5", "kind": "column", "axial_kN": axial_c5,
               "load_combo": combo})
    return ComplianceEngine(PlanData(**_PLAN),
                            analysis={"member_forces": mf})


def _phi_vc_kN():
    """Replicate the interior-column punching capacity (least of ACI §22.6.5.2)."""
    h, d = 180.0, 155.0                       # flat slab, d = h − 25 mm
    c = 0.3 * 1000.0
    bo = 4.0 * (c + d)
    fc, lam, phi = 30.0, 1.0, 0.75
    sf = math.sqrt(fc)
    beta, alpha_s = 1.0, 40.0
    vc1 = 0.33 * lam * sf * bo * d
    vc2 = (0.17 + 0.33 / beta) * lam * sf * bo * d
    vc3 = (0.17 + 0.083 * alpha_s * d / bo) * lam * sf * bo * d
    return phi * min(vc1, vc2, vc3) / 1000.0   # kN


# ── punching shear (#9b) ─────────────────────────────────────────────────────
def test_punching_shear_isolated_check_passes_low_demand():
    # c5 carries the governing (highest) demand and sits interior — the four
    # perimeter columns share a lower demand so the max-ratio joint is never
    # an edge joint (which would legitimately downgrade to warn).
    check = _engine(axial_c5=80.0).check_punching_shear()
    assert check["status"] == "pass"
    assert check["details"]["clause"].startswith("SBC 304 §22.6")
    assert check["details"]["worst_column"] == "c5"
    assert check["details"]["worst_ratio"] == pytest.approx(80.0 / _phi_vc_kN(),
                                                            rel=0.01)
    assert check["details"]["governing_combo"] == "1.2D + 1.6L"
    assert check["details"]["phi"] == 0.75


def test_punching_shear_warns_when_governing_joint_at_edge():
    # Government side: a corner column carries the highest demand → the
    # governing joint sits near the edge → the reduced-perimeter caution
    # downgrades PASS to WARN (never a silent pass).
    mf = [{"element_id": "c1", "kind": "column", "axial_kN": 200.0,
           "load_combo": "1.4D"}]
    for cid in ("c2", "c3", "c4"):
        mf.append({"element_id": cid, "kind": "column", "axial_kN": 50.0,
                   "load_combo": "1.4D"})
    mf.append({"element_id": "c5", "kind": "column", "axial_kN": 50.0,
               "load_combo": "1.2D + 1.6L"})
    check = ComplianceEngine(PlanData(**_PLAN),
                             analysis={"member_forces": mf}).check_punching_shear()
    assert check["status"] == "warn"
    assert check["details"]["worst_column"] == "c1"
    assert check["details"]["worst_ratio"] < 1.0      # would otherwise pass
    assert "edge" in check["details"]["note"].lower()


def test_punching_shear_fails_when_demand_exceeds_capacity():
    check = _engine(axial_c5=1.5 * _phi_vc_kN()).check_punching_shear()
    assert check["status"] in ("warn", "fail")
    # Ratio > 1.1 → the transition is fail, never a fabricated pass.
    assert check["details"]["worst_ratio"] > 1.0
    assert check["details"]["worst_column"] == "c5"


def test_punching_shear_exposes_all_joint_rows():
    check = _engine(axial_c5=50.0).check_punching_shear()
    rows = check["details"]["joint_rows"]
    assert isinstance(rows, list) and len(rows) == 5
    assert {r["column_id"] for r in rows} == {"c1", "c2", "c3", "c4", "c5"}
    assert all("vu_kN" in r and "ratio" in r and "bo_mm" in r for r in rows)


def test_punching_shear_warns_without_analysis():
    check = ComplianceEngine(PlanData(**_PLAN)).check_punching_shear()
    assert check["status"] == "warn"
    assert "analysis" in check["details"]["note"].lower()


# ── column axial capacity §22.4 (fix: reads #9a factored demands) ────────────
def test_column_capacity_uses_factored_member_forces():
    check = _engine(axial_c5=2000.0, combo="0.9D + 1.0E").check_column_capacity()
    assert check["status"] == "fail"          # 2000 kN >> φPn ≈ 1402 kN
    assert check["details"]["worst_column"] == "c5"
    assert check["details"]["worst_axial_kN"] == pytest.approx(2000.0)
    assert check["details"]["governing_combo"] == "0.9D + 1.0E"


def test_column_capacity_warns_without_analysis():
    check = ComplianceEngine(PlanData(**_PLAN)).check_column_capacity()
    assert check["status"] == "warn"
    assert check["details"]["phi_pn_kn"] == pytest.approx(1402.2, rel=0.05)


def test_column_capacity_legacy_fallback_key():
    engine = ComplianceEngine(PlanData(**_PLAN),
                              analysis={"column_axials_kn": [54.0]})
    check = engine.check_column_capacity()
    assert check["status"] != "warn"          # populated via legacy fallback
    assert check["details"]["worst_axial_kN"] == pytest.approx(54.0)


# ── runner integration ───────────────────────────────────────────────────────
def test_run_all_includes_punching_and_capacity():
    report = _engine(axial_c5=50.0).run_all()
    names = [c["check_name"] for c in report["checks"]]
    assert any("Punching" in n for n in names)
    assert any("§22.4" in n for n in names)
    assert any("shear strength" in n.lower() for n in names)       # roadmap #9d
    assert any("development length" in n.lower() for n in names)   # roadmap #9d
    assert len(report["checks"]) == 9
    assert report["summary"]["passed"] >= 0      # deterministic, no exception


def test_run_all_handles_empty_analysis_gracefully():
    report = ComplianceEngine(PlanData(**_PLAN)).run_all()
    assert report["overall_status"] in ("pass", "warn", "fail")
    assert len(report["checks"]) == 9