"""Roadmap #9c wiring: the designed cages must surface end-to-end —

1. the SBC 304 package member table shows the real sections/arrangements
   and As provided/required (what a reviewer reads first);
2. the full BOQ bar-bending schedule consumes the designed cages;
3. the BOQ REBAR line becomes the real take-off (no ratio estimate).
"""
from app.models.plan_data import PlanData
from app.services.boq_generator import generate_boq, generate_bbs
from app.services.sbc304_report import _build_member_design

from tests.test_concrete_bars import _SMOKE_PLAN, _analyze


def test_package_member_table_shows_real_cages():
    result = _analyze()
    summary, details, max_util = _build_member_design(
        analysis={"design": result.design})

    header = details[0]
    assert "Arrangement" in header and "As prov / req (mm²)" in header

    beam_row = next(r for r in details if r[0] == "Beams")
    assert beam_row[1] == "b1"                    # element id (not N/A)
    assert beam_row[2] == "300×500"               # real plan section
    assert "Ø" in beam_row[3]                     # arrangement e.g. 3Ø16
    prov, req = beam_row[4].split(" / ")
    assert float(prov) >= float(req) > 0

    col_row = next(r for r in details if r[0] == "Columns")
    assert col_row[2] == "300×300"
    assert "Ø" in col_row[3]
    assert max_util is not None and 0 < max_util


def test_bbs_uses_designed_cages_and_legacy_fallback():
    plan = PlanData(**_SMOKE_PLAN)
    result = _analyze()
    design = result.design

    bars = generate_bbs(plan, design=design)
    beam_entry = design["beams"][0]
    beam_main = next(b for b in bars
                     if b["element"] == f"Beam {plan.beams[0].id}"
                     and b["shape"] == "straight")
    assert beam_main["dia_mm"] == beam_entry["bar_diameter_mm"]
    assert beam_main["qty"] == beam_entry["bars"]

    col_entry = design["columns"][0]
    col_main = next(b for b in bars
                    if b["element"] == f"Col {plan.columns[0].id}"
                    and b["shape"] == "straight")
    assert col_main["dia_mm"] == col_entry["bar_diameter_mm"]
    assert col_main["qty"] == col_entry["bars"]

    # No design → legacy detailing (Ø16 beam bottom bars, 4×Ø18 columns).
    legacy = generate_bbs(plan)
    legacy_beam = next(b for b in legacy
                       if b["element"] == f"Beam {plan.beams[0].id}"
                       and b["shape"] == "straight")
    assert legacy_beam["dia_mm"] == 16
    assert all(b["dia_mm"] == 18 for b in legacy
               if b["element"].startswith("Col") and b["shape"] == "straight")


def test_boq_rebar_line_is_the_real_takeoff():
    plan = PlanData(**_SMOKE_PLAN)
    result = _analyze()
    boq = generate_boq(plan, analysis={
        "design": result.design, "member_forces": []})

    rebar = next(i for i in boq["items"] if i["code"] == "REBAR")
    assert rebar["quantity"] == boq["bbs"]["rebar_total_kg"]
    assert any("#9c" in a for a in boq["assumptions"])
    assert rebar["quantity"] > 0