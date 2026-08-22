"""
Sprint 7 — Detailed Bill of Quantities + Bar Bending Schedule.

Computes trade quantities (concrete, rebar, formwork, excavation, backfill,
waterproofing) directly from the structural plan and geotechnical survey data,
produces a bar bending schedule (BBS), then runs a first-fit-decreasing
cutting-stock optimisation against standard 12 m / 6 m stock bars to keep
waste below the 2 % contractual target.

Quantities follow standard preliminary-design practice; default rates can be
overridden by the regional cost database (Sprint 13).
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData
from app.models.survey_data import SurveyReading

log = logging.getLogger("imad.boq")

# ── Default unit rates (USD) — replaced by CostRecord lookups when present ──
DEFAULT_RATES: Dict[str, Dict[str, Any]] = {
    "CONC-FOUND": {"description": "Reinforced concrete C30 — footings", "unit": "m3", "rate": 195.0},
    "CONC-FRAME": {"description": "Reinforced concrete C30 — columns & beams", "unit": "m3", "rate": 215.0},
    "CONC-SLAB": {"description": "Reinforced concrete C30 — solid slab", "unit": "m3", "rate": 205.0},
    "BLINDING": {"description": "Plain concrete blinding under footings", "unit": "m3", "rate": 140.0},
    "REBAR": {"description": "High-yield deformed bars, supplied & fixed", "unit": "kg", "rate": 1.15},
    "FORM-COL": {"description": "Column formwork", "unit": "m2", "rate": 28.0},
    "FORM-BEAM": {"description": "Beam soffit & sides formwork", "unit": "m2", "rate": 32.0},
    "FORM-SLAB": {"description": "Slab soffit formwork incl. props", "unit": "m2", "rate": 22.0},
    "EXCAV": {"description": "Bulk excavation in ordinary soil", "unit": "m3", "rate": 14.0},
    "BACKFILL": {"description": "Compacted backfill (excavated material)", "unit": "m3", "rate": 9.0},
    "WPROOF": {"description": "Bituminous membrane waterproofing to foundations", "unit": "m2", "rate": 12.0},
}

STOCK_LENGTHS_M = (12.0, 6.0)
WASTE_TARGET_PCT = 2.0

# Rebar unit weights (kg/m) for common diameters — BS 4449 / ACI table.
BAR_KG_PER_M = {8: 0.395, 10: 0.617, 12: 0.888, 14: 1.208, 16: 1.578,
                18: 1.998, 20: 2.466, 22: 2.984, 25: 3.854}


class BOQError(Exception):
    """Raised when a BOQ cannot be produced."""


# ───────────────────────────────────────────────────── quantity take-off ────
def _footing_design(plan: PlanData, survey: Optional[SurveyReading]) -> Dict[str, Any]:
    """Size isolated footings from allowable bearing capacity (survey-driven)."""
    q_allow_kpa = float(getattr(survey, "soil_bearing_kpa", 0) or 0) or 150.0
    stories = max(1, plan.stories)
    floor_load_kpa = 25.0 * 0.15 + 1.5 + 2.5          # self-weight + SDL + live
    n_cols = max(1, len(plan.columns))
    b = plan.bounds()
    area = max((b["max_x"] - b["min_x"]), 1.0) * max((b["max_y"] - b["min_y"]), 1.0)
    axial_per_col_kn = floor_load_kpa * area / n_cols * stories
    footing_area_m2 = axial_per_col_kn / q_allow_kpa
    side = round(math.sqrt(max(footing_area_m2, 0.25)), 2)
    depth = round(min(max(side / 3.2, 0.35), 0.9), 2)   # two-way shear heuristic
    return {
        "q_allow_kpa": q_allow_kpa,
        "axial_per_col_kn": round(axial_per_col_kn, 1),
        "side_m": side,
        "depth_m": depth,
        "count": n_cols,
    }


def compute_quantities(plan: PlanData,
                       survey: Optional[SurveyReading] = None) -> List[Dict[str, Any]]:
    """Return priced BOQ line items for every trade."""
    stories = max(1, plan.stories)
    b = plan.bounds()
    footprint = max((b["max_x"] - b["min_x"]), 1.0) * max((b["max_y"] - b["min_y"]), 1.0)

    footing = _footing_design(plan, survey)
    n_ftg = max(footing["count"], 1)
    ftg_vol = n_ftg * footing["side_m"] ** 2 * footing["depth_m"]

    col_vol = sum((c.size_m ** 2) * c.height for c in plan.columns) * stories
    if col_vol == 0:                                    # ratio fallback estimate
        col_vol = footprint * 0.008 * stories

    beam_vol = 0.0
    for beam in plan.beams:
        length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
        beam_vol += beam.width_m * beam.depth_m * length
    beam_vol *= stories

    slab_area = footprint * stories
    slab_thick = {"flat": 0.18, "ribbed": 0.28, "two-way": 0.22}.get(
        str((plan.materials or {}).get("slab", "flat")), 0.20)
    slab_vol = slab_area * slab_thick

    # Steel ratios per RC practice: 110 kg/m³ frame · 80 kg/m³ slabs/footings
    steel_kg = col_vol * 110 + beam_vol * 115 + slab_vol * 80 + ftg_vol * 75

    # Formwork contact areas
    col_form = sum(4 * c.size_m * c.height for c in plan.columns) * stories
    beam_form = sum(
        (2 * bm.depth_m + bm.width_m) * math.hypot(bm.x2 - bm.x1, bm.y2 - bm.y1)
        for bm in plan.beams) * stories
    slab_form = slab_area

    # Earthworks: pit with working space per footing, blinding pad below.
    pit_plan_area = n_ftg * ((footing["side_m"] + 0.6) ** 2)
    found_depth = 1.5                                   # typical founding level (m)
    excavation = pit_plan_area * found_depth
    backfill = excavation - ftg_vol - n_ftg * footing["side_m"] ** 2 * 0.1
    waterproof = (n_ftg * footing["side_m"] ** 2 +
                  n_ftg * 4 * footing["side_m"] * footing["depth_m"])
    blinding = n_ftg * (footing["side_m"] + 0.2) ** 2 * 0.1

    items = [
        ("CONC-FOUND", round(ftg_vol, 2)),
        ("CONC-FRAME", round(col_vol + beam_vol, 2)),
        ("CONC-SLAB", round(slab_vol, 2)),
        ("BLINDING", round(blinding, 2)),
        ("REBAR", round(steel_kg, 1)),
        ("FORM-COL", round(col_form, 2)),
        ("FORM-BEAM", round(beam_form, 2)),
        ("FORM-SLAB", round(slab_form, 2)),
        ("EXCAV", round(excavation, 2)),
        ("BACKFILL", round(max(backfill, 0), 2)),
        ("WPROOF", round(waterproof, 2)),
    ]
    return [
        {
            "code": code,
            **DEFAULT_RATES[code],
            "quantity": qty,
            "amount_usd": round(qty * DEFAULT_RATES[code]["rate"], 2),
        }
        for code, qty in items
    ]


# ─────────────────────────────────────────────────── bar bending schedule ────
def generate_bbs(plan: PlanData) -> List[Dict[str, Any]]:
    """Build a simplified but dimensioned Bar Bending Schedule.

    Bars follow common RC detailing: beams get 2 top + 2 bottom longitudinal
    bars plus Ø8 stirrups @150 mm; columns get 4 verticals with Ø8 ties
    @200 mm; slabs use a Ø10@200 mesh both ways; footings a Ø12@200 mat.
    Lengths include anchorage/laps (50d) and 25 mm cover.
    """
    bars: List[Dict[str, Any]] = []
    mark = 1

    def add(element: str, shape: str, dia: int, length_m: float, qty: int,
            spacing: str = "") -> None:
        nonlocal mark
        kg = round(length_m * qty * BAR_KG_PER_M.get(dia, 0.617), 1)
        bars.append({
            "mark": f"B{mark:03d}", "element": element, "shape": shape,
            "dia_mm": dia, "cut_length_m": round(length_m, 2), "qty": qty,
            "total_length_m": round(length_m * qty, 2), "weight_kg": kg,
            "spacing": spacing,
        })
        mark += 1

    for beam in plan.beams:
        span = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
        if span < 0.5:
            continue
        eff = span - 0.05 + 50 * 0.016 / 1000 * 2      # clear + anchorages
        for _ in range(max(1, plan.stories)):
            add(f"Beam {beam.id}", "straight", 16, eff, 2)
            add(f"Beam {beam.id}", "straight", 18, eff + 0.06, 2)
            n_stirrups = max(2, int(span / 0.15))
            perimeter = 2 * (beam.width_m - 0.05 + beam.depth_m - 0.05) + 0.15
            add(f"Beam {beam.id}", "stirrup", 8, perimeter, n_stirrups, "Ø8@150")

    for col in plan.columns:
        lap = 50 * 0.018 / 1000
        length = col.height * max(1, plan.stories) + lap
        add(f"Col {col.id}", "straight", 18, length, 4)
        n_ties = max(2, int(col.height / 0.2)) * max(1, plan.stories)
        tie_len = 4 * (col.size_m - 0.05) + 0.12
        add(f"Col {col.id}", "tie", 8, tie_len, n_ties, "Ø8@200")

    b = plan.bounds()
    slab_area = max((b["max_x"] - b["min_x"]), 1.0) * max((b["max_y"] - b["min_y"]), 1.0)
    for level in range(max(1, plan.stories)):
        width_dir_bars = int(slab_area ** 0.5 / 0.2)
        add(f"Slab L{level}", "mesh-X", 10, slab_area ** 0.5, width_dir_bars, "Ø10@200")
        add(f"Slab L{level}", "mesh-Y", 10, slab_area ** 0.5, width_dir_bars, "Ø10@200")

    footing_side = 1.4                                  # conservative default
    try:
        footing_side = _footing_design(plan, None)["side_m"]
    except Exception:  # pragma: no cover
        pass
    per_direction = max(3, int(footing_side / 0.2))
    add("Footings", "mat-X", 12, footing_side - 0.075, per_direction, "Ø12@200")
    add("Footings", "mat-Y", 12, footing_side - 0.075, per_direction, "Ø12@200")
    return bars


def optimize_cutting(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """First-fit-decreasing cutting stock over standard stock lengths.

    Returns per-diameter patterns plus achieved waste % against the 2 % target.
    """
    result: Dict[str, Any] = {"patterns": [], "waste_percent": 0.0,
                              "target_waste_percent": WASTE_TARGET_PCT}
    total_stock = 0.0
    total_waste = 0.0

    by_dia: Dict[int, List[float]] = {}
    for bar in bars:
        by_dia.setdefault(bar["dia_mm"], []).extend(
            [bar["cut_length_m"]] * bar["qty"])

    for dia, cuts in sorted(by_dia.items()):
        cuts = sorted(cuts, reverse=True)
        stock_bars: List[List[float]] = []
        for cut in cuts:
            best_idx, best_left = -1, None
            for i, contents in enumerate(stock_bars):
                left = STOCK_LENGTHS_M[0] - sum(contents) - cut
                if left >= 0 and (best_left is None or left < best_left):
                    best_idx, best_left = i, left
            if best_idx >= 0:
                stock_bars[best_idx].append(cut)
            else:
                stock_bars.append([cut])
        used = len(stock_bars) * STOCK_LENGTHS_M[0]
        offcuts = sum(STOCK_LENGTHS_M[0] - sum(c) for c in stock_bars)
        total_stock += used
        total_waste += offcuts
        result["patterns"].append({
            "dia_mm": dia,
            "stock_length_m": STOCK_LENGTHS_M[0],
            "stock_bars_used": len(stock_bars),
            "offcut_total_m": round(offcuts, 2),
            "utilization_pct": round(100 * (used - offcuts) / used, 2),
        })

    if total_stock > 0:
        result["waste_percent"] = round(100 * total_waste / total_stock, 2)
        result["stock_metres_total"] = round(total_stock, 1)
        result["within_target"] = result["waste_percent"] <= WASTE_TARGET_PCT
    return result


# ────────────────────────────────────────────────────────────── orchestrator ──
ASSUMPTIONS = [
    "Concrete C30 (fc′ = 30 MPa), rebar fy = 460 MPa (B500/Gr60).",
    "Steel ratios: 110 kg/m³ columns · 115 kg/m³ beams · 80 kg/m³ slabs and footings.",
    "Founding level assumed at −1.50 m; pit working space +0.6 m per side.",
    "Footing sizes derived from the survey allowable bearing capacity (default 150 kPa).",
    "Rates are indicative defaults — bind to the regional cost database for tenders.",
]


def generate_boq(plan: PlanData, survey: Optional[SurveyReading] = None,
                 project_name: str = "Imad Project") -> Dict[str, Any]:
    """Full BOQ payload consumed by the API, exports and the carbon module."""
    if not bool(plan):
        raise BOQError("Plan contains no structural elements; nothing to price.")

    items = compute_quantities(plan, survey)
    bars = generate_bbs(plan)
    cutting = optimize_cutting(bars)

    total = round(sum(i["amount_usd"] for i in items), 2)
    gfa_m2 = next((i["quantity"] for i in items if i["code"] == "FORM-SLAB"), 0.0)
    rebar_kg = next((i["quantity"] for i in items if i["code"] == "REBAR"), 0.0)

    b = plan.bounds()
    return {
        "project_name": project_name,
        "currency": "USD",
        "items": items,
        "totals": {
            "amount_usd": total,
            "gfa_m2": gfa_m2,
            "amount_per_m2": round(total / max(gfa_m2, 1.0), 2),
            "rebar_kg": rebar_kg,
        },
        "bbs": {"bars": bars, **cutting,
                "rebar_total_kg": round(sum(bar["weight_kg"] for bar in bars), 1)},
        "footing": _footing_design(plan, survey),
        "envelope": {
            "length_m": round(b["max_x"] - b["min_x"], 2),
            "width_m": round(b["max_y"] - b["min_y"], 2),
            "stories": plan.stories,
            "slab_type": str((plan.materials or {}).get("slab", "flat")),
        },
        "assumptions": ASSUMPTIONS,
        "status": "completed",
    }


# ───────────────────────────────────────────────────────────────── exports ────
def boq_pdf(boq: Dict[str, Any], out_path: Optional[str] = None) -> str:
    """Render the BOQ as a branded PDF with cover KPIs and BBS appendix."""
    from .exporters import build_pdf_report, exports_dir, simple_bar_chart

    path = Path(out_path) if out_path else (
        exports_dir() / f"boq-{datetime.now(timezone.utc):%Y%m%d%H%M%S}.pdf")

    sections: List[tuple[str, List[List[Any]], Optional[str]]] = [
        ("Bill of Quantities",
         [["Code", "Description", "Unit", "Qty", "Rate", "Amount (USD)"]]
         + [[i["code"], i["description"], i["unit"], i["quantity"],
             i["rate"], i["amount_usd"]] for i in boq["items"]]
         + [["TOTAL", "", "", "", "", boq["totals"]["amount_usd"]]],
         None),
        ("Bar Bending Schedule (first 25 marks)",
         [["Mark", "Element", "Shape", "Ø mm", "Cut m", "Qty", "kg"]]
         + [[bar["mark"], bar["element"], bar["shape"], bar["dia_mm"],
             bar["cut_length_m"], bar["qty"], bar["weight_kg"]]
            for bar in boq["bbs"]["bars"][:25]],
         None),
        ("Cutting Optimisation",
         [["Ø mm", "Stock m", "Bars used", "Offcut m", "Utilisation %"]]
         + [[p["dia_mm"], p["stock_length_m"], p["stock_bars_used"],
             p["offcut_total_m"], p["utilization_pct"]]
            for p in boq["bbs"]["patterns"]],
         f"Achieved waste {boq['bbs']['waste_percent']} % vs target "
         f"≤ {boq['bbs']['target_waste_percent']} %."),
    ]
    build_pdf_report(
        path,
        title="Bill of Quantities & Bar Schedule",
        subtitle=boq["project_name"],
        meta_rows=[["Envelope", f"{boq['envelope']['length_m']} × "
                                f"{boq['envelope']['width_m']} m · "
                                f"{boq['envelope']['stories']} storey(s)"],
                   ["Currency", "USD"], ["Generated", now_iso()]],
        summary_box={
            "Total amount (USD)": boq["totals"]["amount_usd"],
            "Cost / m² (USD)": boq["totals"]["amount_per_m2"],
            "Rebar (kg)": boq["bbs"]["rebar_total_kg"],
            "Cutting waste (%)": boq["bbs"]["waste_percent"],
        },
        sections=sections,
    )
    return str(path)


def boq_xlsx(boq: Dict[str, Any], out_path: Optional[str] = None) -> str:
    """Three-sheet workbook: Summary, BOQ, BBS."""
    from .exporters import build_workbook, exports_dir

    path = Path(out_path) if out_path else (
        exports_dir() / f"boq-{datetime.now(timezone.utc):%Y%m%d%H%M%S}.xlsx")

    sheets = [
        ("Summary", boq["project_name"], [
            ["Metric", "Value"],
            ["Total amount (USD)", boq["totals"]["amount_usd"]],
            ["Cost per m² (USD)", boq["totals"]["amount_per_m2"]],
            ["Rebar total (kg)", boq["bbs"]["rebar_total_kg"]],
            ["Cutting waste (%)", boq["bbs"]["waste_percent"]],
            ["Stories", boq["envelope"]["stories"]],
            ["Slab type", boq["envelope"]["slab_type"]],
        ]),
        ("BOQ", "Bill of Quantities", [
            ["Code", "Description", "Unit", "Quantity", "Rate USD", "Amount USD"],
        ] + [[i["code"], i["description"], i["unit"], i["quantity"], i["rate"],
              i["amount_usd"]] for i in boq["items"]]
        + [["TOTAL", "", "", "", "", boq["totals"]["amount_usd"]]]),
        ("BBS", "Bar Bending Schedule", [
            ["Mark", "Element", "Shape", "Ø mm", "Cut length m", "Qty",
             "Total length m", "Weight kg", "Spacing"],
        ] + [[bar["mark"], bar["element"], bar["shape"], bar["dia_mm"],
              bar["cut_length_m"], bar["qty"], bar["total_length_m"],
              bar["weight_kg"], bar["spacing"]] for bar in boq["bbs"]["bars"]]),
    ]
    build_workbook(path, sheets)
    return str(path)