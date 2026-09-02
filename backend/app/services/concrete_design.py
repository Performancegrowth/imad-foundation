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
    
    def design(self, forces: List[MemberForce]) -> Dict[str, Any]:
        """Run design checks for all members."""
        columns = [f for f in forces if f.kind == "column"]
        beams = [f for f in forces if f.kind == "beam"]
        
        column_checks = self._design_columns(columns)
        beam_checks = self._design_beams(beams)
        
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
    
    def _design_columns(self, columns: List[MemberForce]) -> List[Dict[str, Any]]:
        """Design columns per code."""
        phi = self.code_params["phi_axial"]
        checks: List[Dict[str, Any]] = []
        
        for col in columns:
            P = max(col.axial_kN * 1000 or 0.0, 0.0)  # kN → N
            size = 0.30  # default column size (from plan)
            Ag = (size * 1000) ** 2  # mm²
            
            # Per ACI/SBC §10.6: φPn = φ · [0.85f'c(Ag - Ast) + fy·Ast]
            rho_min = self.code_params["rho_min_formula"](self.fc)
            As_min = rho_min * Ag
            
            phi_pn = phi * (0.85 * self.fc * (Ag - As_min) + self.fy * As_min)
            utilization = P / max(phi_pn, 1e-6)
            
            checks.append({
                "element": col.element_id,
                "axial_kN": col.axial_kN,
                "ag_mm2": int(Ag),
                "phi_pn_kN": round(phi_pn / 1000, 2),
                "as_required_mm2": int(As_min),
                "utilization": round(utilization, 2),
                "code": self.code_standard,
            })
        
        return checks
    
    def _design_beams(self, beams: List[MemberForce]) -> List[Dict[str, Any]]:
        """Design beams per code."""
        phi = self.code_params["phi_flexure"]
        checks: List[Dict[str, Any]] = []
        
        for beam in beams:
            Mu = max(beam.moment_kNm * 1e6 or 0.0, 0.0)  # kNm → Nmm
            b, d = 300.0, 450.0  # width & effective depth (mm)
            
            # Iteratively solve for As
            rho_min = self.code_params["rho_min_formula"](self.fc)
            As_min = rho_min * b * d
            
            # Simplified: Mu = phi * As * fy * (d - a/2), a = As*fy/(0.85*fc*b)
            As = self._solve_beam_steel(phi, Mu, b, d)
            As = max(As, As_min)
            
            a = As * self.fy / (0.85 * self.fc * b)
            phi_mn = phi * As * self.fy * (d - a / 2)
            utilization = Mu / max(phi_mn, 1e-6)
            
            checks.append({
                "element": beam.element_id,
                "moment_kNm": beam.moment_kNm,
                "as_required_mm2": int(As),
                "as_min_mm2": int(As_min),
                "phi_mn_kNm": round(phi_mn / 1e6, 2),
                "utilization": round(utilization, 2),
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
                   code_standard: str = "ACI 318-19") -> Dict[str, Any]:
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
    return designer.design(forces)


def preliminary_boq(plan: PlanData, forces: List[MemberForce],
                   materials: Dict[str, Any]) -> Dict[str, Any]:
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
    steel_kg_per_m3 = 100.0  # typical reinforcement ratio
    steel_tonnes = total_concrete * steel_kg_per_m3 / 1000.0
    rebar_kg = total_concrete * steel_kg_per_m3
    
    return {
        "concrete_m3": round(total_concrete, 2),
        "slab_m3": round(slab_vol, 2),
        "columns_m3": round(col_vol, 2),
        "beams_m3": round(beam_vol, 2),
        "rebar_kg": round(rebar_kg, 2),
        "rebar_tonnes": round(steel_tonnes, 2),
        "footprint_m2": round(slab_area, 2),
        "units": "m³ (concrete), t (steel)",
    }
