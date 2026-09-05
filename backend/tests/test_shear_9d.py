"""Roadmap #9d — shear design + development length + detailing:

- beam_shear_design() turns the factored Vu (load-combination envelope V)
  into a real stirrup layout (Ø10, spacing from φVc and Av/s) instead of the
  fixed Ø8@150/200;
- development_length_mm() computes ld per ACI 318-19 §25.4.2.4;
- the design pass stamps every beam/column with stirrup/tie spacing + ld;
- the compliance engine proves φVn ≥ Vu and ld ≤ available embedment.
"""
import pytest

from app.models.plan_data import PlanData
from app.services.compliance_engine import ComplianceEngine
from app.services.concrete_design import (
    beam_shear_design,
    development_length_mm,
)
from tests.test_concrete_bars import _SMOKE_PLAN, _analyze


# ── shear design helper ────────────────────────────────────────────────────────
def test_beam_shear_design_min_and_low_vu_spacing():
    # Low Vu (≤ φVc/2) → maximum spacing: min(d/2, 600, 300), buildable to 5 mm.
    low = beam_shear_design(20.0, b_mm=300, d_mm=440, fc_mpa=30)
    assert low["ok"] is True
    assert 0 < low["stirrup_spacing_mm"] <= 300
    assert low["stirrups"] == f"Ø{low['stirrup_dia_mm']}@{low['stirrup_spacing_mm']:.0f} (2-legged)"
    assert low["phi_vn_kn"] >= low["vu_kn"]
    assert low["phi_vc_kn"] >= low["vu_kn"]           # no stirrups needed


def test_beam_shear_design_high_vu_tightens_stirrups():
    # High Vu → steel must carry the excess over φVc; spacing tightens and is
    # limited to d/2, but φVn must still cover Vu (the check is honest).
    high = beam_shear_design(180.0, b_mm=300, d_mm=440, fc_mpa=30)
    assert high["ok"] is True
    assert high["stirrup_spacing_mm"] < 300
    assert high["stirrup_spacing_mm"] >= 40
    assert high["vs_required_kn"] > 0
    assert high["phi_vn_kn"] >= high["vu_kn"]


def test_beam_shear_design_spacing_floor_is_buildable():
    s = beam_shear_design(200.0, b_mm=250, d_mm=400, fc_mpa=30)["stirrup_spacing_mm"]
    assert s % 5 == 0 and s >= 40


# ── development length helper ──────────────────────────────────────────────────
def test_development_length_grows_and_has_floor():
    ld16 = development_length_mm(16, 420.0, 30.0)
    ld25 = development_length_mm(25, 420.0, 30.0)
    assert ld16 == pytest.approx(420.0 * 16 / (2.1 * (30.0 ** 0.5)), abs=0.2)
    assert ld25 > ld16 > 300.0                     # §25.4.2.1 300 mm floor
    # Floor applies when the formula itself is under 300 mm (short, high-strength).
    assert development_length_mm(10, 300.0, 40.0) == pytest.approx(300.0)


# ── design pass stamps shear + development fields ─────────────────────────────
def test_design_beams_carry_shear_and_ld_fields():
    result = _analyze()
    beam = next(b for b in result.design["beams"] if b["element"] == "b1")
    assert isinstance(beam["shear_kN"], (int, float)) and beam["shear_kN"] > 0
    assert 0 < beam["stirrup_spacing_mm"] <= 300
    assert beam["stirrups"].startswith("Ø10@")
    assert beam["phi_vc_kn"] > 0 and beam["phi_vn_kn"] >= beam["shear_kN"]
    assert beam["shear_ok"] is True
    assert beam["ld_mm"] > 300


def test_design_columns_carry_ties_and_ld():
    result = _analyze()
    col = result.design["columns"][0]
    assert 100 <= col["tie_spacing_mm"] <= 300      # §10.7.6.2 cappings
    assert col["ties"].startswith(f"Ø{col.get('tie_dia_mm', 10):.0f}@")
    assert col["ld_mm"] > 300


# ── compliance reads shear + development from the design ──────────────────────
def test_compliance_shear_check_reads_design():
    result = _analyze()
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN),
                              analysis={"design": result.design,
                                        "member_forces": [
                                            f.__dict__ for f in result.member_forces]})
    check = engine.check_shear_design()
    assert check["status"] == "pass"
    assert check["details"]["source"] == "design pass (roadmap #9d)"
    assert check["details"]["governing_beam"] == "b1"
    assert check["details"]["utilization"] <= 1.0
    assert "Ø10@" in check["details"]["stirrups"]


def test_compliance_dev_length_check_reads_design():
    result = _analyze()
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN),
                              analysis={"design": result.design})
    check = engine.check_dev_length()
    assert check["status"] == "pass"
    assert check["details"]["source"] == "design pass (roadmap #9d)"
    assert check["details"]["ld_required_mm"] <= check["details"]["available_mm"]


def test_compliance_shear_and_dev_warn_without_design():
    engine = ComplianceEngine(PlanData(**_SMOKE_PLAN))
    assert engine.check_shear_design()["status"] == "warn"
    assert engine.check_dev_length()["status"] == "warn"


# ── BOQ BBS consumes the designed stirrup/tie spacing ─────────────────────────
def test_bbs_uses_design_stirrup_spacing():
    from app.services.boq_generator import generate_bbs

    plan = PlanData(**_SMOKE_PLAN)
    result = _analyze()
    design_beam = next(b for b in result.design["beams"] if b["element"] == "b1")

    bars = generate_bbs(plan, design=result.design)
    stirrup = next(b for b in bars
                   if b["element"] == f"Beam {plan.beams[0].id}"
                   and b["shape"] == "stirrup")
    assert stirrup["spacing"] == f"Ø8@{design_beam['stirrup_spacing_mm']:.0f}"

    design_col = result.design["columns"][0]
    tie = next(b for b in bars
               if b["element"] == f"Col {plan.columns[0].id}"
               and b["shape"] == "tie")
    assert tie["spacing"] == f"Ø8@{design_col['tie_spacing_mm']:.0f}"