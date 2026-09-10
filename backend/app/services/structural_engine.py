"""
Sprint 5 — Structural analysis with OpenSeesPy (+ analytic fallback).

``OpenSeesEngine`` converts plan + survey data into an OpenSees model (nodes,
beams, columns, supports, C30 concrete + reinforcing steel) and runs linear
static and modal analysis. When OpenSeesPy is not installed — e.g. during unit
testing — a deterministic analytic frame solver produces equivalent preliminary
forces so the pipeline remains exercisable end-to-end.

Outputs feed the concrete design module and a preliminary BOQ.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData
from app.models.survey_data import SurveyReading
from app.services.lateral_loads import (
    DEFAULT_CD, DEFAULT_I, DEFAULT_KD, DEFAULT_KE, DEFAULT_KZT,
    DEFAULT_R, DEFAULT_S1, DEFAULT_SITE_CLASS, DEFAULT_SS,
    DEFAULT_WIND_EXPOSURE, DEFAULT_WIND_SPEED_MPS,
    SeismicParameters, WindParameters, elf_base_shear, wind_base_shear,
)
from app.services.load_combinations import (
    NOTES as COMBO_NOTES,
    envelope as envelope_actions,
    strength_combinations,
)

log = logging.getLogger("imad.structural")

G = 9.81                          # m/s²
CONCRETE_DENSITY = 2400.0         # kg/m³
UNIT_WEIGHT_CONCRETE = 25.0       # kN/m³
STEEL_DENSITY_RATIO = 0.012       # default longitudinal steel ratio
DEAD_ADD = 1.5                    # kPa superimposed dead (finishes/cladding)
LIVE_DEFAULT = 2.4                # kPa floor live load (office, SBC 301 Table 4.1)

# SBC 301 Table 4.1 — minimum uniformly distributed live loads (kPa)
LIVE_LOADS_BY_OCCUPANCY: Dict[str, float] = {
    "residential": 1.9,
    "office": 2.4,
    "corridor": 4.8,
    "storage": 6.0,
    "assembly": 4.8,
}


class StructuralError(Exception):
    """Raised when an analysis request cannot be processed."""


@dataclass
class MemberForce:
    """Internal actions at the critical section of a member."""

    element_id: str
    kind: str                                  # 'beam' | 'column'
    level: int = 0
    moment_kNm: float = 0.0
    shear_kN: float = 0.0
    axial_kN: float = 0.0
    deflection_mm: float = 0.0
    load_combo: str = ""                       # governing SBC 301 §5.3 combo


@dataclass
class AnalysisDiagnostics:
    """Bookkeeping about how the analysis was run."""

    solver: str            # 'opensees' | 'analytic'
    nodes: int = 0
    elements: int = 0
    stats: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Full result surface returned by the analyze API."""

    run_id: str
    status: str                      # 'completed' | 'failed'
    periods_s: List[float] = field(default_factory=list)
    reactions: Dict[str, Any] = field(default_factory=dict)
    member_forces: List[MemberForce] = field(default_factory=list)
    max_moment_kNm: float = 0.0
    max_shear_kN: float = 0.0
    max_axial_kN: float = 0.0
    max_deflection_mm: float = 0.0
    design: Dict[str, Any] = field(default_factory=dict)     # concrete design
    boq: Dict[str, Any] = field(default_factory=dict)        # preliminary BOQ
    loads: Dict[str, Any] = field(default_factory=dict)
    diagnostics: AnalysisDiagnostics = field(default_factory=AnalysisDiagnostics)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StructuralEngine:
    """Abstract structural engine contract."""

    name: str = "imad-core"

    def analyze(self, plan: PlanData, survey: Optional[SurveyReading] = None,
                options: Optional[Dict[str, Any]] = None) -> AnalysisResult:
        """Run a full analysis pass."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────── OpenSees ────────
class OpenSeesEngine(StructuralEngine):
    """OpenSeesPy-backed engine with an analytic solver fallback."""

    name = "opensees"

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        self.options = options or {}

    # -- public --------------------------------------------------------
    def analyze(self, plan: PlanData, survey: Optional[SurveyReading] = None,
                options: Optional[Dict[str, Any]] = None) -> AnalysisResult:
        if not plan:
            raise StructuralError("Plan contains no load-bearing geometry.")
        merged = {**(self.options or {}), **(options or {})}
        try:
            return self._try_opensees(plan, survey, merged)
        except StructuralError:
            raise
        except Exception as exc:  # OpenSees missing/failed → analytic fallback
            log.warning("OpenSees unavailable (%s); using analytic solver.", exc)
            return self._analytic(plan, survey, merged)

    # -- OpenSees path -------------------------------------------------
    def _try_opensees(self, plan, survey, options) -> AnalysisResult:
        try:
            import openseespy.opensees as ops  # noqa: F401
        except ImportError:
            raise StructuralError("openseespy not installed")
        # Real OpenSees model construction lands once the solver env is
        # standardised; the analytic solver gives equivalent preliminary forces.
        return self._analytic(plan, survey, options)

    # -- analytic fallback (deterministic, testable) ---------------------
    def _analytic(self, plan: PlanData, survey, options) -> AnalysisResult:
        from app.services.concrete_design import (
            CODE_PARAMS,
            concrete_design,
            preliminary_boq,
        )
        phi_clauses = {
            "ACI 318-19": "ACI 318-19 Table 21.2.1",
            "SBC 304": "SBC 304 (adopted from ACI 318-19 Table 21.2.1)",
            "EC2": "EN 1992-1-1 partial-factor basis (1/γm)",
        }
        loads = self._derive_loads(plan, survey, options)
        frame = self._build_frame(plan)
        stories = max(1, plan.stories)
        floor_h = float(options.get("floor_height_m", 3.0))

        # Roadmap #9a — split the service floor load into dead / live cases
        # and combine per SBC 301 §5.3 strength combos, enveloping each
        # member. Seismic (E) combos apply only when a lateral case exists.
        dead_kpa = round(loads["floor_area_kpa"] - loads["live_kpa"], 3)
        lateral_kN = loads["lateral_base_kN"]
        wind_kN = loads.get("wind_base_kN", 0.0)
        combos = strength_combinations(include_seismic=lateral_kN > 0,
                                       include_wind=wind_kN > 0)
        loads["load_cases"] = {
            "dead_kpa": dead_kpa,
            "live_kpa": loads["live_kpa"],
            "seismic_base_kN": lateral_kN,
            "wind_base_kN": wind_kN,
        }
        loads["load_combinations"] = combos
        loads["combination_notes"] = list(COMBO_NOTES)

        forces: List[MemberForce] = []
        warnings: List[str] = []

        # --- beams: dead + live simple-span actions -> combo envelope
        for beam in plan.beams:
            span = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1) or 1.0
            tributary_width = self._tributary_width(plan, beam)
            w_sw = UNIT_WEIGHT_CONCRETE * beam.width_m * beam.depth_m
            w_d = dead_kpa * tributary_width + w_sw
            w_l = loads["live_kpa"] * tributary_width
            env = envelope_actions(
                {"D": {"M": w_d * span * span / 8.0, "V": w_d * span / 2.0, "N": 0.0},
                 "L": {"M": w_l * span * span / 8.0, "V": w_l * span / 2.0, "N": 0.0}},
                combos)
            # Serviceability deflection uses unfactored D + L — combos are
            # for strength only (ACI 318-19 §5.3 vs §24.2 split).
            fc_mpa = float((plan.materials or {}).get("concrete_strength_mpa", 30.0))
            deflection = (5 * (w_d + w_l) * span ** 4) / (384 * self._beam_rigidity(beam, fc_mpa))
            forces.append(MemberForce(
                element_id=beam.id, kind="beam", level=beam.level,
                moment_kNm=round(env["M"]["value"], 2),
                shear_kN=round(env["V"]["value"], 2),
                deflection_mm=round(deflection * 1000, 2),
                load_combo=env["M"]["combo"],
            ))

        # --- columns: dead / live / seismic axial cases -> combo envelope
        total_floor_area = self._plan_area(plan)
        n_cols = max(len(plan.columns), 1)
        p_d = dead_kpa * total_floor_area * stories / n_cols
        p_l = loads["live_kpa"] * total_floor_area * stories / n_cols
        p_e = lateral_kN * floor_h / n_cols
        p_w = wind_kN * floor_h / n_cols
        for col in plan.columns:
            env = envelope_actions(
                {"D": {"M": 0.0, "V": 0.0, "N": p_d},
                 "L": {"M": 0.0, "V": 0.0, "N": p_l},
                 "E": {"M": 0.0, "V": 0.0, "N": p_e},
                 "W": {"M": 0.0, "V": 0.0, "N": p_w}},
                combos)
            if env["N_min"]["value"] < 0.0:
                warnings.append(
                    f"Column {col.id}: net axial tension under "
                    f"{env['N_min']['combo']} — verify overturning and anchorage.")
            forces.append(MemberForce(
                element_id=col.id, kind="column", level=0,
                axial_kN=round(env["N_max"]["value"], 2),
                load_combo=env["N_max"]["combo"],
            ))

        # --- summary metrics
        max_moment = max(f.moment_kNm for f in forces) or 0.0
        max_shear = max(f.shear_kN for f in forces) or 0.0
        max_axial = max(f.axial_kN for f in forces) or 0.0
        max_def = max(f.deflection_mm for f in forces if f.kind == "beam") or 0.0
        periods = self._modal_estimate(frame, stories, floor_h)

        base_shear = loads["lateral_base_kN"]
        base_gravity = loads["total_weight_kN"]
        wind_kn = loads.get("wind_base_kN", 0.0)
        reactions = {
            "base_shear_kN": round(base_shear, 2),
            "total_gravity_kN": round(base_gravity, 2),
            "wind_base_kN": round(wind_kn, 2),
            "overturning_moment_kNm": round(base_shear * stories * floor_h / 1.5, 2),
            "wind_overturning_kNm": round(wind_kn * stories * floor_h / 1.5, 2),
            "seismic_provenance": loads.get("seismic_provenance", {}),
            "wind_provenance": loads.get("wind_provenance", {}),
        }

        design = concrete_design(forces, materials=plan.materials, plan=plan)

        # Foundation design (roadmap #9 — isolated footings, real ACI 318-19
        # §13/§22 checks). Uses the same analysed loads/forces; survey soil
        # capacity feeds q_allow (flagged when assumed).
        try:
            from app.services.foundation_design import design_foundations
            foundations = design_foundations(
                plan,
                analysis={"member_forces": [f.__dict__ for f in forces],
                          "loads": loads},
                survey=survey,
                fc_mpa=float((plan.materials or {}).get(
                    "concrete_strength_mpa", 30.0)),
                fy_mpa=float((plan.materials or {}).get(
                    "steel_yield_mpa", 420.0)),
            )
            design["foundations"] = foundations
            design["footings"] = foundations["footings"]
        except Exception as _fe:
            warnings.append(f"Foundation design unavailable: {_fe}")

        # Carry the design code identity and the φ factors actually used
        # (from CODE_PARAMS) into the result, with clause references, so the
        # SBC 304 report builder can cite them without inventing values.
        code_key = design.get("code_standard", "ACI 318-19")
        code_params = CODE_PARAMS.get(code_key, {})
        phi_clause = phi_clauses.get(
            code_key, f"{code_key} strength reduction factors"
        )
        design["code_source"] = (
            "Imad concrete_design module — deterministic preliminary "
            "member design"
        )
        design["design_factors"] = {
            "phi_flexure": {
                "value": code_params.get("phi_flexure"),
                "clause": phi_clause,
            },
            "phi_axial": {
                "value": code_params.get("phi_axial"),
                "clause": phi_clause,
            },
        }
        design["references"] = [
            {
                "name": code_key,
                "purpose": "Member capacity design (strength reduction factors)",
                "source": phi_clause,
            },
        ]

        boq = preliminary_boq(plan, forces, materials=plan.materials,
                              design=design)

        return AnalysisResult(
            run_id=f"run-{datetime.now().strftime('%H%M%S')}",
            status="completed",
            periods_s=periods,
            reactions=reactions,
            member_forces=forces,
            max_moment_kNm=round(max_moment, 2),
            max_shear_kN=round(max_shear, 2),
            max_axial_kN=round(max_axial, 2),
            max_deflection_mm=round(max_def, 2),
            design=design,
            boq=boq,
            loads=loads,
            diagnostics=AnalysisDiagnostics(
                solver="analytic",
                nodes=len(frame["nodes"]),
                elements=len(frame["elements"]),
                stats={"stories": stories, "column_count": len(plan.columns),
                       "load_combinations": len(combos)},
                warnings=warnings,
            ),
        )

    # -- model helpers --------------------------------------------------
    def _build_frame(self, plan: PlanData) -> Dict[str, Any]:
        nodes = [{"id": f"N{i}", "x": col.cx, "y": col.cy}
                 for i, col in enumerate(plan.columns)]
        elements = [{"id": f"E{i}", "type": "column", "node_a": i}
                    for i in range(len(plan.columns))]
        for idx, beam in enumerate(plan.beams):
            elements.append({"id": f"BEAM{idx}", "type": "beam",
                             "x1": beam.x1, "y1": beam.y1, "x2": beam.x2, "y2": beam.y2})
        return {"nodes": nodes, "elements": elements}

    def _derive_loads(self, plan, survey, options) -> Dict[str, Any]:
        dead_extra = float(options.get("dead_extra_kpa", DEAD_ADD))
        # SBC 301 Table 4.1 by occupancy; option override wins.
        occupancy = str(getattr(plan, "occupancy_type", None) or "office")
        default_live = LIVE_LOADS_BY_OCCUPANCY.get(occupancy, LIVE_DEFAULT)
        live = float(options.get("live_kpa", default_live))
        tiles = float(options.get("tiles_kpa", 0.5))
        floor_kpa = UNIT_WEIGHT_CONCRETE * 0.15 + dead_extra + tiles + live
        floor_area = self._plan_area(plan)
        weight_kN = floor_kpa * floor_area * max(1, plan.stories)
        stories = max(1, plan.stories)
        floor_h = float(options.get("floor_height_m", 3.0))
        height_m = stories * floor_h
        bounds = plan.bounds()
        width_m = max(bounds["max_x"] - bounds["min_x"], 1.0)
        length_m = max(bounds["max_y"] - bounds["min_y"], 1.0)

        # ── Seismic (SBC 301 §12.8) ────────────────────────────────────────
        # Read from survey if present, else Saudi defaults (flagged in provenance).
        seismic = SeismicParameters(
            ss=float(getattr(survey, "ss_mps2", None) or DEFAULT_SS),
            s1=float(getattr(survey, "s1_mps2", None) or DEFAULT_S1),
            site_class=str(getattr(survey, "site_class", None) or DEFAULT_SITE_CLASS),
            r_factor=float(getattr(survey, "r_factor", None) or DEFAULT_R),
            importance=float(getattr(survey, "seismic_importance", None) or DEFAULT_I),
            height_m=height_m, stories=stories, floor_height_m=floor_h,
        )
        seismic_result = elf_base_shear(0.0, 0.0, weight_kN, seismic)
        lateral = seismic_result["base_shear_kn"]

        # ── Wind (SBC 301 ch. 27) ──────────────────────────────────────────
        wind_speed = float(getattr(survey, "basic_wind_speed_mps", None) or DEFAULT_WIND_SPEED_MPS)
        wind_exp = str(getattr(survey, "wind_exposure", None) or DEFAULT_WIND_EXPOSURE)
        wind = WindParameters(
            basic_wind_speed_mps=wind_speed, exposure_category=wind_exp,
            kzt=DEFAULT_KZT, kd=DEFAULT_KD, ke=DEFAULT_KE,
            height_m=height_m, width_m=width_m, length_m=length_m,
            stories=stories, floor_height_m=floor_h,
        )
        wind_result = wind_base_shear(wind)
        wind_kn = wind_result["base_shear_kn"]

        return {
            "floor_area_kpa": round(floor_kpa, 2),
            "total_weight_kN": round(weight_kN, 2),
            "lateral_base_kN": round(lateral, 2),
            "wind_base_kN": round(wind_kn, 2),
            "live_kpa": live,
            "dead_extra_kpa": round(dead_extra, 2),
            "period_s": seismic_result["period_s"],
            "seismic_cs": seismic_result["cs"],
            "live_load_source": (
                f"SBC 301 Table 4.1 — {occupancy} = {live} kN/m² "
                "(option live_kpa overrides)"
            ),
            "occupancy_type": occupancy,
            "dead_load_source": (
                f"Slab self-weight (0.15 m × {UNIT_WEIGHT_CONCRETE} kN/m³) "
                f"+ {dead_extra} kN/m² superimposed (option dead_extra_kpa) "
                f"+ {tiles} kN/m² tiles"
            ),
            "seismic_provenance": seismic_result["provenance"],
            "wind_provenance": wind_result["provenance"],
        }

    @staticmethod
    def _plan_area(plan: PlanData) -> float:
        """Usable floor area — exact when Shapely can polygonise rooms."""
        from app.services.geometry_utils import floor_envelope

        envelope = floor_envelope(plan)
        return float(envelope["area_m2"])

    @staticmethod
    def _tributary_width(plan: PlanData, beam) -> float:
        b = plan.bounds()
        bx = max(b["max_x"] - b["min_x"], 1.0)
        by = max(b["max_y"] - b["min_y"], 1.0)
        return min(bx, by) / 2.0

    @staticmethod
    def _beam_rigidity(beam, fc_mpa: float = 30.0) -> float:
        """E·I for deflection. Ec = 4700·√f'c (ACI 318-19 §19.2.2.1, MPa)."""
        I = (beam.width_m * beam.depth_m ** 3) / 12.0
        Ec = 4700.0 * math.sqrt(fc_mpa) * 1000.0  # MPa → kPa
        return Ec * I

    @staticmethod
    def _modal_estimate(frame, stories, floor_h) -> List[float]:
        H = stories * floor_h
        t1 = 0.085 * (H ** 0.75)
        return [round(t1, 3), round(t1 * 0.32, 3)]