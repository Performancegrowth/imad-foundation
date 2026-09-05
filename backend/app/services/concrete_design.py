"""Sprint 5 — Code-agnostic concrete design + preliminary BOQ.

Implements capacity checks for multiple codes (ACI 318, SBC 304, EC2) and
reinforcement suggestions. Code selection is configurable per project.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData
from app.services.structural_engine import MemberForce

log = logging.getLogger("imad.concrete_design")

# Default material properties (can be overridden per project)
DEFAULT_FC_MPA = 30.0  # C30 concrete
DEFAULT_FY_MPA = 420.0  # A615 rebar (Saudi standard)

# ---- rebar catalogue (roadmap #9c) -----------------------------------------
# Nominal areas and unit weights per BS 4449 / ACI — same diameters used by the
# BBS generator (boq_generator.BAR_KG_PER_M), so bars selected here can feed
# compliance AND the rebar take-off directly (no more assumed 0.8 % / 100 kg/m³).
BAR_AREA_MM2 = {
    8: 50.3, 10: 78.5, 12: 113.1, 14: 153.9, 16: 201.1, 18: 254.5,
    20: 314.2, 22: 380.1, 25: 490.9, 28: 615.8,
}
BAR_KG_PER_M = {
    8: 0.395, 10: 0.617, 12: 0.888, 14: 1.208, 16: 1.578, 18: 1.998,
    20: 2.466, 22: 2.984, 25: 3.854, 28: 4.834,
}
_BEAM_DIA = (16, 18, 20, 22, 25)        # longitudinal beam bars
_COLUMN_DIA = (16, 18, 20, 22, 25)     # longitudinal column bars
COLUMN_COUNTS = (4, 6, 8, 12, 16)      # even, corner-symmetric layouts
COVER_MM = 40.0                        # clear cover (beams/columns)
TIE_MM = 10.0                          # stirrup/hoop Ø


def round_up_to_bar_layout(as_required_mm2: float, *, b_mm: float,
                           min_dia: int = 16, max_dia: int = 25,
                           kind: str = "beam",
                           min_gap_mm: float = 25.0) -> Dict[str, Any]:
    """Select a deterministic bar layout whose As ≥ As_required.

    Beams: single layer, minimum bar Ø and count / spacing depth-first —
    the first (dia, n) that satisfies both area and fit-in-width wins, so the
    output is reproducible and economical. Columns: even, corner-symmetric
    counts (4–16) so the selection is a real distributable cage.
    """
    if kind == "beam":
        diameters = [d for d in _BEAM_DIA if min_dia <= d <= max_dia]
    else:
        diameters = [d for d in _COLUMN_DIA if min_dia <= d <= max_dia]
    cover = COVER_MM + (TIE_MM if kind == "beam" else 0.0)
    for dia in diameters:
        a_bar = BAR_AREA_MM2[dia]
        n_min = max(2, math.ceil(as_required_mm2 / a_bar)) if as_required_mm2 > 0 else 2
        if kind == "column":
            # Clamp to a valid even symmetric count.
            n = next((c for c in COLUMN_COUNTS
                      if c * a_bar >= as_required_mm2), COLUMN_COUNTS[-1])
            return {
                "bars": n, "bar_diameter_mm": dia,
                "as_provided_mm2": round(n * a_bar, 2),
                "arrangement": f"{n}Ø{dia}",
                "kind": "column",
            }
        # beams: try n bars on one layer until they fit with 25 mm gaps.
        cover = COVER_MM + TIE_MM
        for n in range(n_min, 9):
            need_width = 2 * cover + (n * dia) + (n - 1) * min_gap_mm
            if need_width <= b_mm:
                return {"bars": n, "bar_diameter_mm": dia,
                        "as_provided_mm2": round(n * a_bar, 2),
                        "arrangement": f"{n}Ø{dia}",
                        "kind": "beam",
                        "fits_one_layer": True}
    # No single-layer fit — two-layer fallback (common real-world outcome).
    dia = diameters[-1]
    n = max(2, math.ceil(as_required_mm2 / BAR_AREA_MM2[dia]))
    return {"bars": n, "bar_diameter_mm": dia,
            "as_provided_mm2": round(n * BAR_AREA_MM2[dia], 2),
            "arrangement": f"{n}Ø{dia} (double layer)",
            "kind": "beam",
            "fits_one_layer": False}


def development_length_mm(db_mm: int, fy_mpa: float, fc_mpa: float, *,
                          psi_t: float = 1.0, lam: float = 1.0) -> float:
    """Tension development length (mm) — ACI 318-19 §25.4.2.4 (SI units).

    ld = fy·ψt·db / (2.1·λ·√f'c·((cb+Ktr)/db)), taking (cb+Ktr)/db = 1.0 —
    no transverse-steel credit (conservative; the engineer may refine with
    the actual cover/bar spacing). 300 mm floor per §25.4.2.1.
    """
    ld = fy_mpa * psi_t * db_mm / (2.1 * lam * math.sqrt(max(fc_mpa, 1.0)))
    return max(300.0, round(ld, 1))


def beam_shear_design(vu_kn: float, b_mm: float, d_mm: float, fc_mpa: float, *,
                      fyv_mpa: float = 420.0, stirrup_dia_mm: int = 10,
                      legs: int = 2) -> Dict[str, Any]:
    """One-way shear design (strength level) — SBC 304 ch. 9 / ACI 318-19 §22.5.

    φVc = φ·0.17·λ·√f'c·bw·d (SI). Stirrups: Ø10 two-legged verticals;
    required Av/s = (Vu/φ − Vc)/(fyv·d) with the §9.6.3.4 minimum; spacing
    capped at d/2 and 600 mm (300 mm where Vu ≤ φVc/2) per §9.7.6.4, rounded
    down to a buildable 5 mm increment.
    """
    phi = 0.75
    vu_n = max(float(vu_kn) * 1000.0, 0.0)
    vc = 0.17 * math.sqrt(max(fc_mpa, 1.0)) * b_mm * d_mm          # N
    phi_vc = phi * vc
    av = legs * BAR_AREA_MM2.get(stirrup_dia_mm, 78.5)
    av_s_min = 0.062 * math.sqrt(max(fc_mpa, 1.0)) / fyv_mpa * b_mm

    if vu_n <= 0.5 * phi_vc:
        s = min(300.0, d_mm / 2.0, 600.0)
    else:
        vs_req = max(vu_n / phi - vc, 0.0)
        av_s_req = max(vs_req / (fyv_mpa * d_mm), av_s_min)
        s = min(av / av_s_req, d_mm / 2.0, 600.0)
    s = max(math.floor(s / 5.0) * 5.0, 40.0)
    vs_provided = av * fyv_mpa * d_mm / s
    phi_vn = phi * (vc + vs_provided)
    return {
        "vu_kn": round(vu_n / 1000.0, 1),
        "phi_vc_kn": round(phi_vc / 1000.0, 1),
        "vs_required_kn": round(max(vu_n / phi - vc, 0.0) / 1000.0, 1),
        "stirrup_dia_mm": stirrup_dia_mm,
        "stirrup_spacing_mm": s,
        "stirrups": f"Ø{stirrup_dia_mm}@{s:.0f} ({legs}-legged)",
        "phi_vn_kn": round(phi_vn / 1000.0, 1),
        "ok": vu_n <= phi_vn,
    }

# Code-specific factors
CODE_PARAMS = {
    "ACI 318-19": {
        "phi_flexure": 0.90,
        "phi_axial": 0.65,
        "rho_min_formula": lambda fc: max(0.25 * math.sqrt(fc) / DEFAULT_FY_MPA, 1.4 / DEFAULT_FY_MPA),
        "deflection_limit": 240,  # L/240
        "name": "ACI 318-19 Building Code",
    },
    "SBC 304": {
        "phi_flexure": 0.90,
        "phi_axial": 0.65,
        "rho_min_formula": lambda fc: max(0.25 * math.sqrt(fc) / DEFAULT_FY_MPA, 1.4 / DEFAULT_FY_MPA),
        "deflection_limit": 240,  # L/240 (adopted from ACI)
        "name": "SBC 304 (Saudi Building Code)",
    },
    "EC2": {
        "phi_flexure": 1.0 / 1.5,  # 1/γm
        "phi_axial": 1.0 / 1.5,
        "rho_min_formula": lambda fc: 0.26 * math.sqrt(fc) / 500.0,  # Eurocode 2
        "deflection_limit": 250,  # L/250
        "name": "EN 1992-1-1 (Eurocode 2)",
    },
}


class ConcreteDesigner:
    """Unified concrete design interface supporting multiple codes."""
    
    def __init__(self, code_standard: str = "ACI 318-19",
                 fc_mpa: Optional[float] = None,
                 fy_mpa: Optional[float] = None):
        """Initialize designer for a specific code.
        
        Args:
            code_standard: "ACI 318-19", "SBC 304", or "EC2"
            fc_mpa: concrete strength (default 30 MPa)
            fy_mpa: steel yield strength (default 420 MPa)
        """
        if code_standard not in CODE_PARAMS:
            raise ValueError(
                f"Unknown code: {code_standard}. "
                f"Supported: {list(CODE_PARAMS.keys())}"
            )
        
        self.code_standard = code_standard
        self.code_params = CODE_PARAMS[code_standard]
        self.fc = fc_mpa or DEFAULT_FC_MPA
        self.fy = fy_mpa or DEFAULT_FY_MPA
    
    def design(self, forces: List[MemberForce],
               plan: Optional[PlanData] = None) -> Dict[str, Any]:
        """Run design checks for all members.

        ``plan`` supplies real section geometry (column size_m, beam
        width_m/depth_m); without it, code-neutral defaults are used so the
        direct call remains deterministic and backward-compatible.
        """
        column_checks = self._design_columns(
            [f for f in forces if f.kind == "column"], plan=plan)
        beam_checks = self._design_beams(
            [f for f in forces if f.kind == "beam"], plan=plan)

        max_util = 0.0
        for entry in column_checks + beam_checks:
            max_util = max(max_util, entry.get("utilization", 0.0))

        return {
            "code_standard": self.code_standard,
            "code_name": self.code_params["name"],
            "concrete_strength_mpa": self.fc,
            "steel_yield_mpa": self.fy,
            "columns": column_checks,
            "beams": beam_checks,
            "max_utilization": round(max_util, 2),
            "status": "acceptable" if max_util <= 1.0 else "needs_reinforcement",
        }
    

    def _design_columns(self, columns: List[MemberForce],
                        plan: Optional[PlanData] = None) -> List[Dict[str, Any]]:
        """Design columns per code - real section size + real bar cage (#9c)."""
        phi = self.code_params["phi_axial"]
        plan_cols = {c.id: c for c in (plan.columns if plan else [])}
        checks: List[Dict[str, Any]] = []

        for col in columns:
            pu_n = max(float(col.axial_kN or 0.0) * 1000.0, 0.0)
            pc = plan_cols.get(col.element_id)
            size_mm = (pc.size_m * 1000) if pc else 300.0
            Ag = size_mm ** 2

            # SBC 304 10.6.1.1: 1% <= rho_col <= 8%
            rho_min_col = max(self.code_params["rho_min_formula"](self.fc), 0.01)
            As_min = rho_min_col * Ag
            ast_req = (pu_n / max(phi * 0.80, 1e-6) - 0.85 * self.fc * Ag) / \
                max(self.fy - 0.85 * self.fc, 1e-6)
            ast_req = min(max(ast_req, As_min), 0.08 * Ag)

            layout = round_up_to_bar_layout(ast_req, b_mm=size_mm, kind="column")
            ast = layout["as_provided_mm2"]
            phi_pn = phi * 0.80 * (0.85 * self.fc * (Ag - ast) + self.fy * ast)
            utilization = pu_n / max(phi_pn, 1e-6)

            # Detailing (#9d): tie spacing per §10.7.6.2 (least of 48·dt,
            # 16·db, least column dimension) + tension development length.
            tie_s = min(48.0 * TIE_MM, 16.0 * layout["bar_diameter_mm"], size_mm)
            ld = development_length_mm(layout["bar_diameter_mm"], self.fy, self.fc)

            checks.append({
                "element": col.element_id,
                "axial_kN": round(float(col.axial_kN or 0.0), 2),
                "section_mm": int(size_mm), "ag_mm2": int(Ag),
                "phi_pn_kN": round(phi_pn / 1000, 2),
                "as_required_mm2": int(round(ast_req)),
                "as_min_mm2": int(round(As_min)),
                "bars": layout["bars"],
                "bar_diameter_mm": layout["bar_diameter_mm"],
                "as_provided_mm2": layout["as_provided_mm2"],
                "arrangement": layout["arrangement"],
                "rho_provided": round(ast / Ag, 5),
                "utilization": round(utilization, 2),
                "ties": f"Ø{TIE_MM:.0f}@{tie_s:.0f}",
                "tie_spacing_mm": round(tie_s, 1),
                "ld_mm": ld,
                "code": self.code_standard,
            })

        return checks

    def _design_beams(self, beams: List[MemberForce],
                      plan: Optional[PlanData] = None) -> List[Dict[str, Any]]:
        """Design beams using real plan sections and a real bar layout (#9c)."""
        phi = self.code_params["phi_flexure"]
        plan_beams = {bm.id: bm for bm in (plan.beams if plan else [])}
        checks: List[Dict[str, Any]] = []

        for beam in beams:
            Mu = max(float(beam.moment_kNm or 0.0) * 1e6, 0.0)
            pb = plan_beams.get(beam.element_id)
            b_mm = (pb.width_m * 1000) if pb else 300.0
            h_mm = (pb.depth_m * 1000) if pb else 450.0
            d_guess = h_mm - COVER_MM - TIE_MM - 10.0
            as_req = self._solve_beam_steel(phi, Mu, b_mm, d_guess)
            rho_min = self.code_params["rho_min_formula"](self.fc)
            as_min = rho_min * b_mm * d_guess
            as_req = max(as_req, as_min)

            layout = round_up_to_bar_layout(as_req, b_mm=b_mm, kind="beam")
            d_act = h_mm - COVER_MM - TIE_MM - layout["bar_diameter_mm"] / 2.0
            a = layout["as_provided_mm2"] * self.fy / (0.85 * self.fc * b_mm)
            phi_mn = phi * layout["as_provided_mm2"] * self.fy * (d_act - a / 2.0)
            utilization = Mu / max(phi_mn, 1e-6)

            # Shear design + development length (#9d): stirrup spacing from
            # the factored Vu (load-combination envelope V), not the fixed
            # Ø8@150/200; ld per ACI 318-19 §25.4.2.
            sd = beam_shear_design(float(beam.shear_kN or 0.0), b_mm, d_act, self.fc)
            ld = development_length_mm(layout["bar_diameter_mm"], self.fy, self.fc)

            checks.append({
                "element": beam.element_id,
                "moment_kNm": round(float(beam.moment_kNm or 0.0), 2),
                "shear_kN": round(float(beam.shear_kN or 0.0), 2),
                "width_mm": int(b_mm), "depth_mm": int(h_mm),
                "d_eff_mm": round(d_act, 1),
                "as_required_mm2": int(round(as_req)),
                "as_min_mm2": int(round(as_min)),
                "bars": layout["bars"],
                "bar_diameter_mm": layout["bar_diameter_mm"],
                "as_provided_mm2": layout["as_provided_mm2"],
                "arrangement": layout["arrangement"],
                "fits_one_layer": layout.get("fits_one_layer", True),
                "rho_provided": round(layout["as_provided_mm2"] / (b_mm * d_act), 5),
                "phi_mn_kNm": round(phi_mn / 1e6, 2),
                "utilization": round(utilization, 2),
                "stirrup_dia_mm": sd["stirrup_dia_mm"],
                "stirrup_spacing_mm": sd["stirrup_spacing_mm"],
                "stirrups": sd["stirrups"],
                "phi_vc_kn": sd["phi_vc_kn"],
                "vs_required_kn": sd["vs_required_kn"],
                "phi_vn_kn": sd["phi_vn_kn"],
                "shear_ok": sd["ok"],
                "ld_mm": ld,
                "code": self.code_standard,
            })

        return checks

    def _solve_beam_steel(self, phi: float, mu: float, b: float, d: float) -> float:
        """Solve for required steel area via closed-form solution."""
        jd = 0.9 * d
        As = mu / (phi * self.fy * jd)
        a = As * self.fy / (0.85 * self.fc * b)
        return mu / (phi * self.fy * (d - a / 2))


def concrete_design(forces: List[MemberForce], materials: Dict[str, Any],
                   code_standard: str = "ACI 318-19",
                   plan: Optional[PlanData] = None) -> Dict[str, Any]:
    """Legacy interface: design with code selection.
    
    Args:
        forces: Member forces from structural analysis
        materials: Material properties (concrete_strength_mpa, steel_yield_mpa, slab type)
        code_standard: Design code (ACI 318-19, SBC 304, EC2)
    
    Returns:
        Design results with utilization ratios per member
    """
    fc = float(materials.get("concrete_strength_mpa", DEFAULT_FC_MPA) or DEFAULT_FC_MPA)
    fy = float(materials.get("steel_yield_mpa", DEFAULT_FY_MPA) or DEFAULT_FY_MPA)
    
    designer = ConcreteDesigner(code_standard=code_standard, fc_mpa=fc, fy_mpa=fy)
    return designer.design(forces, plan=plan)


def preliminary_boq(plan: PlanData, forces: List[MemberForce],
                   materials: Dict[str, Any],
                   design: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Estimate quantities for a preliminary BOQ (no detailed sizing)."""
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

    # Rebar take-off (roadmap #9c): when the design pass supplied real bar
    # layouts, weight = bars x member length x unit weight; otherwise fall
    # back to the historical 100 kg/m3 ratio and say so.
    rebar_kg = 0.0
    rebar_source = "assumed 100 kg/m3 ratio (no design attached)"
    if design:
        lengths: Dict[str, float] = {}
        for c in plan.columns:
            lengths[c.id] = c.height * stories
        for bm in plan.beams:
            lengths[bm.id] = math.hypot(bm.x2 - bm.x1, bm.y2 - bm.y1) * stories
        for group in ("columns", "beams"):
            for entry in design.get(group, []) or []:
                ln = lengths.get(entry.get("element"))
                if ln:
                    rebar_kg += entry.get("bars", 0) * ln * BAR_KG_PER_M.get(
                        entry.get("bar_diameter_mm", 20), 2.466)
        if rebar_kg > 0:
            rebar_source = "real bar layouts (roadmap #9c)"
    if rebar_kg <= 0:
        rebar_kg = total_concrete * 100.0
    steel_tonnes = rebar_kg / 1000.0
    
    return {
        "concrete_m3": round(total_concrete, 2),
        "slab_m3": round(slab_vol, 2),
        "columns_m3": round(col_vol, 2),
        "beams_m3": round(beam_vol, 2),
        "rebar_kg": round(rebar_kg, 2),
        "rebar_tonnes": round(steel_tonnes, 2),
        "rebar_source": rebar_source,
        "footprint_m2": round(slab_area, 2),
        "units": "m³ (concrete), t (steel)",
    }
