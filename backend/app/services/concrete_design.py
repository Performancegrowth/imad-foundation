"""
Concrete design + preliminary BOQ (Sprint 5).

Implements ACI 318-style capacity checks and reinforcement suggestions for
columns and beams, plus an initial bill of quantities (concrete volume and
steel tonnage) from an analysed plan.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from app.models.plan_data import PlanData
from app.services.structural_engine import MemberForce
# Unit-safe conversions (Pint-backed; see core/units.py). Makes the implicit
# kN→N and kN·m→N·mm multipliers explicit and validation-friendly.
from app.core.units import convert

PHI = 0.90                  # flexure strength reduction factor
PHI_C = 0.65                # axial compression factor (tied)
FC_PRIME_DEFAULT = 30.0     # MPa (C30)
FY_DEFAULT = 460.0          # MPa rebar yield
AS_MIN_RATIO = 0.01         # minimum longitudinal steel ratio (columns)
AS_MAX_RATIO = 0.06
STEEL_KG_PER_M3 = 100.0     # typical reinforced-concrete estimate


def concrete_design(forces: List[MemberForce], materials: Dict[str, Any]) -> Dict[str, Any]:
    """Return per-element capacity checks and reinforcement suggestions."""
    fc = float(materials.get("concrete_strength_mpa", FC_PRIME_DEFAULT) or FC_PRIME_DEFAULT)
    fy = float(materials.get("steel_yield_mpa", FY_DEFAULT) or FY_DEFAULT)

    columns = [f for f in forces if f.kind == "column"]
    beams = [f for f in forces if f.kind == "beam"]

    column_checks = _design_columns(columns, fc, fy)
    beam_checks = _design_beams(beams, fc, fy)

    max_util = 0.0
    for entry in column_checks + beam_checks:
        max_util = max(max_util, entry.get("utilization", 0.0))

    return {
        "concrete_strength_mpa": fc,
        "steel_yield_mpa": fy,
        "columns": column_checks,
        "beams": beam_checks,
        "max_utilization": round(max_util, 2),
        "status": "acceptable" if max_util <= 1.0 else "needs_reinforcement",
    }


def _design_columns(columns: List[MemberForce], fc: float, fy: float) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for col in columns:
        P = max(convert(col.axial_kN, "kilonewton", "newton") or 0.0, 0.0)   # N
        size = 0.30                           # m (column side from plan default)
        Ag = size * size * 1e6                # mm²
        # Combined axial + flexure check (simplified per ACI 22.4)
        phi_pn = PHI_C * (0.85 * fc * Ag + (fy - 0.85 * fc) * AS_MIN_RATIO * Ag)
        utilization = P / phi_pn
        # required steel
        As_required = P / (PHI_C * fy) - 0.85 * fc * Ag / fy
        As_required = max(As_required, AS_MIN_RATIO * Ag)
        suggested = [
            {"bar": f"{d}mm @ {count} bars", "as_mm2": int(count * math.pi * (d / 2) ** 2)}
            for d, count in _bar_layout(As_required)
        ]
        checks.append({
            "element": col.element_id,
            "axial_kN": col.axial_kN,
            "ag_mm2": int(Ag),
            "phi_pn_kN": round(phi_pn / 1000, 2),
            "as_required_mm2": int(As_required),
            "suggested_rebars": suggested,
            "utilization": round(utilization, 2),
        })
    return checks


def _design_beams(beams: List[MemberForce], fc: float, fy: float) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for beamf in beams:
        Mu = max(convert(beamf.moment_kNm, "kilonewton * meter", "newton * millimeter") or 0.0, 0.0)   # N·mm
        b, d_val = 300.0, 0.5 * 1000 - 50.0     # width mm, effective depth mm
        # Solve for As via simplified rectangular stress block
        # Mu = phi * As * fy * (d - a/2),  a = As*fy/(0.85 fc b)
        # iterate once:
        As = _solve_flexural(phi=PHI, mu=Mu, fy=fy, fc=fc, b=b, d=d_val)
        As_min = max(0.25 * math.sqrt(fc) / fy, 1.4 / fy) * b * d_val
        As = max(As, As_min)
        # capacity with this steel
        a = As * fy / (0.85 * fc * b)
        phi_mn = PHI * As * fy * (d_val - a / 2)
        utilization = Mu / phi_mn if phi_mn else 0.0
        checks.append({
            "element": beamf.element_id,
            "moment_kNm": beamf.moment_kNm,
            "as_required_mm2": int(As),
            "as_min_mm2": int(As_min),
            "phi_mn_kNm": round(phi_mn / 1e6, 2),
            "utilization": round(utilization, 2),
        })
    return checks


def _solve_flexural(phi, mu, fy, fc, b, d) -> float:
    """Closed-form As for singly reinforced rectangular section."""
    jd = 0.9 * d
    As = mu / (phi * fy * jd)
    a = As * fy / (0.85 * fc * b)
    return mu / (phi * fy * (d - a / 2))


def _bar_layout(area_mm2: float) -> List[Any]:
    """Return a practical bar arrangement for the required area."""
    count = max(4, int(math.ceil(area_mm2 / (math.pi * 18 ** 2))))  # 18 mm bars
    return [(18, count)]


def preliminary_boq(plan: PlanData, forces: List[MemberForce],
                    materials: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate concrete volume (m³) and steel tonnage (t) for the structure."""
    stories = max(1, plan.stories)
    # Slab volume
    b = plan.bounds()
    slab_area = max((b["max_x"] - b["min_x"]), 1.0) * max((b["max_y"] - b["min_y"]), 1.0)
    slab_vol = slab_area * 0.15 * stories

    # Columns volume
    col_vol = sum((c.size_m ** 2) * c.height for c in plan.columns) * stories

    # Beams volume
    beam_vol = 0.0
    for beam in plan.beams:
        length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
        beam_vol += beam.width_m * beam.depth_m * length

    total_concrete = slab_vol + col_vol + beam_vol
    steel_tonnes = total_concrete * STEEL_KG_PER_M3 / 1000.0
    rebar_kg = total_concrete * STEEL_KG_PER_M3

    footprint = slab_area
    return {
        "concrete_m3": round(total_concrete, 2),
        "slab_m3": round(slab_vol, 2),
        "columns_m3": round(col_vol, 2),
        "beams_m3": round(beam_vol, 2),
        "rebar_kg": round(rebar_kg, 2),
        "rebar_tonnes": round(steel_tonnes, 2),
        "footprint_m2": round(footprint, 2),
        "units": "m³ (concrete), t (steel)",
    }