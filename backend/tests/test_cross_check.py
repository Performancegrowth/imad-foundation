"""Roadmap #9f — cross-check of the Imad ACI flexure formula against an
independent implementation (structuralcodes, EC2-2004 MRd).

These tests run on BOTH Python 3.14 (no structuralcodes → graceful warn/skip)
and Python 3.12 (library present → sections must fall inside the documented
±20% code-difference band, and in practice they land within a few percent).
"""
import pytest

from app.models.plan_data import PlanData
from app.services.compliance_engine import ComplianceEngine
from app.services.concrete_design import beam_flexural_moment_capacity_knm
from app.services.cross_check import (
    PASS_RATIO_HIGH,
    PASS_RATIO_LOW,
    _structuralcodes_available,
    cross_check_section,
    run_cross_check,
)
from tests.test_concrete_bars import _SMOKE_PLAN, _analyze

_AVAILABLE = _structuralcodes_available()


# ── formula under test is single-sourced ──────────────────────────────────────
def test_flexure_helper_matches_aci_rectangular_block():
    # 3Ø16 in a 300×500 beam, d = 442 mm (40 cover + 10 tie + Ø/2).
    as_, b, d, fc, fy, phi = 3 * 201.1, 300.0, 442.0, 30.0, 420.0, 0.90
    a = as_ * fy / (0.85 * fc * b)
    expected = phi * as_ * fy * (d - a / 2.0) / 1e6
    assert beam_flexural_moment_capacity_knm(as_, fy, fc, b, d) == \
        pytest.approx(expected)


# ── library presence / graceful degradation ───────────────────────────────────
def test_cross_check_graceful_without_library():
    rep = run_cross_check()
    assert rep["library"]["name"] == "structuralcodes"
    assert rep["band"] == {"ratio_min": PASS_RATIO_LOW,
                           "ratio_max": PASS_RATIO_HIGH}
    if _AVAILABLE:
        assert rep["library"]["installed"] is True
        assert rep["status"] == "pass"
        assert all(r["ok"] for r in rep["sections"])
        assert len(rep["sections"]) >= 4
    else:
        assert rep["status"] == "warn"
        assert all(r["ok"] is False for r in rep["sections"])


@pytest.mark.skipif(not _AVAILABLE, reason="structuralcodes not installed")
def test_cross_check_sections_inside_band():
    for row in run_cross_check()["sections"]:
        assert PASS_RATIO_LOW <= row["ratio"] <= PASS_RATIO_HIGH
        assert row["ec2_mrd_knm"] > 0
        assert row["aci_phi_mn_knm"] > 0


@pytest.mark.skipif(not _AVAILABLE, reason="structuralcodes not installed")
def test_cross_check_ratio_is_tight_for_typical_beam():
    # Same physical section under two codes should agree to a few percent.
    row = cross_check_section("b300x500-3O16", 300, 500, 3, 16, 30.0, 420.0)
    assert row["ok"] is True
    assert 0.9 <= row["ratio"] <= 1.1


# ── compliance reads the REAL cages from the design pass ──────────────────────
def test_compliance_cross_check_reads_design_cages():
    result = _analyze()
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN),
                              analysis={"design": result.design,
                                        "member_forces": [
                                            f.__dict__ for f in result.member_forces]})
    check = engine.check_cross_validation()
    assert check["status"] in ("pass", "warn")
    assert check["details"]["clause"].startswith("Cross-check:")
    if _AVAILABLE:
        assert check["details"]["library"]["name"] == "structuralcodes"
        # Sections must be the design's real cages (label encodes size/bars).
        assert any("beam 300x500 " in s["label"] and "O16" in s["label"]
                   for s in check["details"]["sections"])