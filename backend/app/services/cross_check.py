"""Roadmap #9f — arm's-length cross-check of the Imad section formulas.

``structuralcodes`` (fib International, Apache-2.0) implements Eurocode 2
(2004/2023) and fib Model Code 2010 — it deliberately does NOT implement
ACI 318 / SBC 304, so this is not a line-for-line verification. It is an
independent-implementation VALIDATION: the same physical section — dimensions,
As, f'c ≈ fck, fy ≈ fyk — computed under two independent code formulations must
give moment capacities of the same order of magnitude.

The pass band (±20 %) is the honest code-difference envelope: ACI φ-factors vs
EC2 partial factors (φ=0.90 flexure vs fcd = αcc·fck/γc, fyd = fyk/γs),
rectangular-stress-block vs parabola-rectangle constitutive laws, and different
ultimate concrete/steel strain limits.

Units: structuralcodes works in N/mm. fck = f'c and fyk = fy (cylinder
strength is the same physical property); the EC2 design materials derive
fcd/fyd internally from the partial factors.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.services.concrete_design import (
    COVER_MM,
    TIE_MM,
    BAR_AREA_MM2,
    beam_flexural_moment_capacity_knm,
)

# Honest tolerances (documented code-difference envelope, see module docstring).
PASS_RATIO_LOW, PASS_RATIO_HIGH = 0.80, 1.20       # φMn(ACI) / MRd(EC2)

# Case matrix: (label, b_mm, h_mm, bars, dia_mm, fc_mpa, fy_mpa)
_BEAM_MATRIX: List[Tuple[str, float, float, int, int, float, float]] = [
    ("beam 300x500 3O16", 300, 500, 3, 16, 30.0, 420.0),
    ("beam 300x500 4O20", 300, 500, 4, 20, 30.0, 420.0),
    ("beam 250x450 3O18", 250, 450, 3, 18, 30.0, 420.0),
    ("beam 300x600 5O25", 300, 600, 5, 25, 35.0, 420.0),
    ("col 300x300 4O16", 300, 300, 4, 16, 30.0, 420.0),
]

LIBRARY = {
    "name": "structuralcodes",
    "version": "0.7.1",
    "license": "Apache-2.0",
    "maintainer": "fib International",
    "installed": False,
}


def _structuralcodes_available() -> bool:
    try:
        import structuralcodes  # noqa: F401
        return True
    except Exception:
        return False
def _build_ec2_section(
    b_mm: float, h_mm: float, bars: int, dia_mm: int,
    fc_mpa: float, fy_mpa: float,
):
    """Build an EC2-2004 singly-reinforced BeamSection matching our geometry.

    Tension bars are placed in one layer at d = h − cover − tie − dia/2 from
    the top fibre (matching the Imad design pass), spread across a 3·diameter
    band so the section integrates cleanly.
    """
    from structuralcodes.codes import set_design_code
    from structuralcodes.geometry import RectangularGeometry
    from structuralcodes.geometry._reinforcement import add_reinforcement
    from structuralcodes.materials.concrete import create_concrete
    from structuralcodes.materials.reinforcement import create_reinforcement
    from structuralcodes.sections import BeamSection

    set_design_code("ec2_2004")
    concrete = create_concrete(fc_mpa, design_code="ec2_2004")
    steel = create_reinforcement(fyk=fy_mpa, Es=200000.0,
                                 ftk=min(fy_mpa * 1.1, 550.0), epsuk=0.05,
                                 design_code="ec2_2004")
    rect = RectangularGeometry(width=b_mm, height=h_mm,
                               material=concrete, concrete=True)
    y_steel = -(h_mm / 2.0 - COVER_MM - TIE_MM - dia_mm / 2.0)   # N/mm units
    geo = rect
    x_spacing = min(max(3.0 * dia_mm, dia_mm + 25.0),
                    (b_mm - 2.0 * COVER_MM) / max(bars, 1))
    for i in range(bars):
        bx = (i - (bars - 1) / 2.0) * x_spacing
        geo = add_reinforcement(geo, (bx, y_steel), float(dia_mm), steel)
    return BeamSection(geo, integrator="marin", tol=1e-3)


def structuralcodes_mrd_knm(
    b_mm: float, h_mm: float, bars: int, dia_mm: int,
    fc_mpa: float = 30.0, fy_mpa: float = 420.0,
) -> float:
    """Ultimate bending capacity MRd (kN·m) from structuralcodes (EC2-2004)."""
    if not _structuralcodes_available():
        raise ImportError("structuralcodes is not installed")
    sec = _build_ec2_section(b_mm, h_mm, bars, dia_mm, fc_mpa, fy_mpa)
    res = sec.section_calculator.calculate_bending_strength(theta=0.0, n=0.0)
    return abs(float(res.m_y)) / 1e6


def cross_check_section(
    label: str, b_mm: float, h_mm: float, bars: int, dia_mm: int,
    fc_mpa: float = 30.0, fy_mpa: float = 420.0,
) -> Dict[str, Any]:
    """Compare our ACI φMn against the structuralcodes EC2 MRd for one section."""
    as_mm2 = bars * BAR_AREA_MM2[dia_mm]
    d_mm = h_mm - COVER_MM - TIE_MM - dia_mm / 2.0
    aci_phi_mn = beam_flexural_moment_capacity_knm(
        as_mm2, fy_mpa, fc_mpa, b_mm, d_mm)
    if not _structuralcodes_available():
        return {"label": label, "ok": False,
                "note": "structuralcodes not installed — cross-check skipped.",
                "aci_phi_mn_knm": None, "ec2_mrd_knm": None, "ratio": None}
    try:
        ec2_mrd = structuralcodes_mrd_knm(b_mm, h_mm, bars, dia_mm, fc_mpa, fy_mpa)
    except Exception as exc:                       # pragma: no cover - lib edge
        return {"label": label, "ok": False, "note": f"error: {exc}",
                "aci_phi_mn_knm": round(aci_phi_mn, 2),
                "ec2_mrd_knm": None, "ratio": None}
    ratio = aci_phi_mn / max(ec2_mrd, 1e-9)
    ok = PASS_RATIO_LOW <= ratio <= PASS_RATIO_HIGH
    return {
        "label": label,
        "aci_phi_mn_knm": round(aci_phi_mn, 2),
        "ec2_mrd_knm": round(ec2_mrd, 2),
        "ratio": round(ratio, 3),
        "ok": ok,
        "basis": ("ACI 318-19 §22.3 (Imad) vs EC2-2004 §6.1 (structuralcodes); "
                  "same section, independent code formulations."),
    }
def run_cross_check(
    sections: List[Tuple[str, float, float, int, int, float, float]] = None,
) -> Dict[str, Any]:
    """Run the full section-matrix cross-check.

    By default the documented matrix is used; callers may pass their own list of
    (label, b_mm, h_mm, bars, dia_mm, fc_mpa, fy_mpa) tuples — e.g. the real
    cages from a design pass.
    """
    available = _structuralcodes_available()
    rows = [
        cross_check_section(*args)
        for args in (sections or _BEAM_MATRIX)
    ]
    if not available:
        status = "warn"
        note = ("structuralcodes not installed — independent cross-check "
                "skipped. Install structuralcodes on a Python ≤ 3.12 env.")
    else:
        failed = [r for r in rows if not r["ok"]]
        status = "pass" if not failed else "warn"
        note = ("All sections within the documented ±20% code-difference band."
                if status == "pass"
                else "Some sections outside the band — review required.")
    LIBRARY["installed"] = available
    return {
        "library": LIBRARY,
        "status": status,
        "note": note,
        "method": ("Independent-implementation validation: ACI 318-19 §22.3 "
                   "flexure (Imad) vs EC2-2004 §6.1 MRd (structuralcodes)."),
        "band": {"ratio_min": PASS_RATIO_LOW, "ratio_max": PASS_RATIO_HIGH},
        "sections": rows,
    }