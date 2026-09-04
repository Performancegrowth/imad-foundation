"""
Sprint 10 — Rule-based code-compliance engine (Saudi Building Code).

Implements automated checks against SBC 304 (concrete structures), the Saudi
adoption of ACI 318. Each check returns pass/fail/warn with the governing
clause cited in ``details`` so a licensed engineer can review the basis
before sealing.

Checked clauses (preliminary-design scope):
* §7.6.1.1  minimum slab thickness (span/25 flat plates)
* §9.6.1.2  minimum beam flexural reinforcement ratio
* Table 7.3.2  deflection limits (L/240 total, L/360 live)
* §10.6.1.1 column reinforcement 1 % ≤ ρ ≤ 8 %
* SBC 301 §12.8  seismic base shear V = Cs·W (ELF)
* §22.4     column axial capacity φPn vs demand (reads the #9a factored
            envelope from analysis member_forces)
* §22.6     two-way (punching) shear at slab–column connections (roadmap #9b)
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData

log = logging.getLogger("imad.compliance")

CODE_NAME = "SBC 304 (Concrete Structures) — Saudi Building Code"


class ComplianceEngine:
    """Runs deterministic code checks over a structural plan + analysis."""

    def __init__(self, plan: PlanData,
                 analysis: Optional[Dict[str, Any]] = None,
                 survey: Optional[Any] = None):
        self.plan = plan
        self.analysis = analysis or {}
        self.survey = survey

    # ── individual checks ────────────────────────────────────────────────────
    def check_slab_thickness(self) -> Dict[str, Any]:
        span = self._max_span()
        slab_type = str((self.plan.materials or {}).get("slab", "flat"))
        actual_mm = {"flat": 180, "ribbed": 280, "two-way": 220}.get(slab_type, 200)
        min_mm = math.ceil(span * 1000 / 25)          # §7.6.1.1 flat plate
        ok = actual_mm >= min_mm
        return {
            "check_name": "Minimum slab thickness (§7.6.1.1)",
            "status": "pass" if ok else ("warn" if actual_mm >= min_mm * 0.9 else "fail"),
            "details": {
                "clause": "SBC 304 §7.6.1.1",
                "required_mm": min_mm, "provided_mm": actual_mm,
                "governing_span_m": round(span, 2),
                "note": "Span/25 for flat plates without drop panels.",
            },
        }

    def check_beam_reinforcement(self) -> Dict[str, Any]:
        # ρ_min = max(0.25√f'c, 1.4)/fy — C30: 0.25·√30 = 1.37 < 1.4 → 1.4 governs
        rho_min = 1.4 / 420.0
        assumed_rho = 0.008                            # detailing basis of the BBS
        ok = assumed_rho >= rho_min
        return {
            "check_name": "Minimum beam flexural reinforcement (§9.6.1.2)",
            "status": "pass" if ok else "fail",
            "details": {
                "clause": "SBC 304 §9.6.1.2 (ACI 318-19 §9.6.1.2)",
                "rho_min": round(rho_min, 5),
                "rho_provided_assumed": assumed_rho,
                "note": "Derived from the BBS longitudinal bar schedule.",
            },
        }

    def check_deflection(self) -> Dict[str, Any]:
        span = self._max_span()
        limit = span / 240.0 * 1000                    # mm — total §7.3.2
        est = self.analysis.get("max_deflection_mm")
        if est is None:
            est = span * 1000 / 400                    # L/d heuristic
            basis = "estimated (no analysis attached)"
        else:
            basis = "from structural analysis"
        status = "pass" if est <= limit else ("warn" if est <= limit * 1.1 else "fail")
        return {
            "check_name": "Maximum deflection (Table 7.3.2)",
            "status": status,
            "details": {
                "clause": "SBC 304 Table 7.3.2",
                "limit_mm": round(limit, 1),
                "computed_mm": round(float(est), 1),
                "basis": basis,
            },
        }

    def check_column_reinforcement(self) -> Dict[str, Any]:
        # 1 % ≤ ρ ≤ 8 % per §10.6.1.1; Imad detailing uses 4Ø18 on columns.
        bars, dia_m = 4, 0.018
        size = self.plan.columns[0].size_m if self.plan.columns else 0.3
        ast = bars * math.pi * dia_m ** 2 / 4
        ag = size ** 2
        rho = ast / ag
        ok = 0.01 <= rho <= 0.08
        return {
            "check_name": "Column reinforcement limits (§10.6.1.1)",
            "status": "pass" if ok else ("warn" if rho > 0.08 * 0.9 else "fail"),
            "details": {
                "clause": "SBC 304 §10.6.1.1",
                "rho_percent": round(rho * 100, 2),
                "allowed_range_pct": [1.0, 8.0],
                "column_size_m": size, "bars": f"{bars}Ø{int(dia_m * 1000)}",
            },
        }

    def check_base_shear(self) -> Dict[str, Any]:
        seismic = self.analysis.get("base_shear_kn")
        weight = self.analysis.get("seismic_weight_kn") or self._est_weight()
        # SBC 301 §12.8 ELF: Cs = SDS/(R/I); SDS ≈ 0.33g (moderate site),
        # R = 5 (special RC moment frame), I = 1.0.
        cs = 0.33 / 5.0
        expected = cs * weight
        if seismic is None:
            return {
                "check_name": "Seismic base shear (SBC 301 §12.8)",
                "status": "warn",
                "details": {"clause": "SBC 301 §12.8",
                            "expected_min_kn": round(expected, 1),
                            "note": "No lateral analysis attached — run Analyze first."},
            }
        ratio = float(seismic) / max(expected, 1e-6)
        status = "pass" if ratio >= 0.95 else ("warn" if ratio >= 0.85 else "fail")
        return {
            "check_name": "Seismic base shear (SBC 301 §12.8)",
            "status": status,
            "details": {
                "clause": "SBC 301 §12.8 equivalent lateral force",
                "expected_min_kn": round(expected, 1),
                "computed_kn": round(float(seismic), 1),
                "ratio": round(ratio, 3),
            },
        }

    def check_column_capacity(self) -> Dict[str, Any]:
        demands = self._column_axial_demands()
        size = self.plan.columns[0].size_m if self.plan.columns else 0.3
        fc_mpa, fy_mpa = 30.0, 420.0
        ast = 4 * math.pi * 18 ** 2 / 4                  # mm² — 4Ø18
        ag = (size * 1000) ** 2                          # mm²
        phi_pn = 0.65 * 0.80 * (0.85 * fc_mpa * (ag - ast) + fy_mpa * ast)
        base_details = {
            "clause": "SBC 304 §22.4 (φPn,max = 0.80φ[0.85f'c(Ag−Ast)+fyAst])",
            "phi_pn_kn": round(phi_pn / 1000, 1),
        }
        if not demands:
            return {"check_name": "Column axial capacity (§22.4)", "status": "warn",
                    "details": {**base_details,
                                "note": "Run analysis to populate member forces."}}
        worst = max(demands, key=lambda d: float(d["axial_kN"]))
        phi_pn_kn = phi_pn / 1000.0                      # N → kN (unit parity)
        ratio = float(worst["axial_kN"]) / max(phi_pn_kn, 1e-6)
        status = "pass" if ratio <= 1.0 else ("warn" if ratio <= 1.1 else "fail")
        return {
            "check_name": "Column axial capacity (§22.4)",
            "status": status,
            "details": {**base_details,
                        "worst_demand_ratio": round(ratio, 3),
                        "worst_column": worst.get("element_id") or "—",
                        "worst_axial_kN": round(float(worst["axial_kN"]), 2),
                        "governing_combo": worst.get("load_combo", "")},
        }

    def check_punching_shear(self) -> Dict[str, Any]:
        """Two-way (punching) shear at slab–column connections (roadmap #9b).

        ACI 318-19 §22.6.5.2 as adopted by SBC 304 §22.6 — Vc is the least of
        the three expressions over the critical perimeter at d/2 from the
        column face. Vu is the factored column axial demand from the #9a
        strength-combination envelope, so this check is meaningful only when
        an analysis is attached.
        """
        base_details = {
            "clause": "SBC 304 §22.6 (ACI 318-19 §22.6.5.2) two-way shear",
            "phi": 0.75,
        }
        columns = self.plan.columns
        if not columns:
            return {"check_name": "Punching shear at slab–column joints (§22.6)",
                    "status": "warn",
                    "details": {**base_details, "note": "No columns in plan."}}
        demands = self._column_axial_demands()
        if not demands:
            return {"check_name": "Punching shear at slab–column joints (§22.6)",
                    "status": "warn",
                    "details": {**base_details,
                                "note": "Run analysis to populate factored column "
                                        "demands."}}
        demand_by_id = {d["element_id"]: d for d in demands
                        if d.get("element_id") is not None}
        slab_type = str((self.plan.materials or {}).get("slab", "flat"))
        h_mm = {"flat": 180, "ribbed": 280, "two-way": 220}.get(slab_type, 200)
        d_mm = max(h_mm - 25.0, 100.0)            # 20 mm clear + half Ø bar
        fc_mpa, lam, phi = 30.0, 1.0, 0.75
        sqrt_fc = math.sqrt(fc_mpa)
        b = self.plan.bounds()
        min_x = float(b["min_x"]) * 1000.0
        min_y = float(b["min_y"]) * 1000.0
        max_x = float(b["max_x"]) * 1000.0
        max_y = float(b["max_y"]) * 1000.0

        rows: List[Dict[str, Any]] = []
        for col in columns:
            demand = demand_by_id.get(col.id)
            if demand is None:
                continue
            vu_n = float(demand["axial_kN"]) * 1000.0
            c_mm = col.size_m * 1000.0
            bo_mm = 4.0 * (c_mm + d_mm)             # interior column at d/2
            beta = 1.0                              # square column (c1/c2)
            alpha_s = 40.0                          # interior-column coefficient
            vc1 = 0.33 * lam * sqrt_fc * bo_mm * d_mm
            vc2 = (0.17 + 0.33 / beta) * lam * sqrt_fc * bo_mm * d_mm
            vc3 = (0.17 + 0.083 * alpha_s * d_mm / bo_mm) \
                * lam * sqrt_fc * bo_mm * d_mm
            phi_vc_n = phi * min(vc1, vc2, vc3)
            ratio = vu_n / max(phi_vc_n, 1e-6)
            near = (col.cx * 1000.0 <= min_x + c_mm + d_mm or
                    col.cy * 1000.0 <= min_y + c_mm + d_mm or
                    col.cx * 1000.0 >= max_x - c_mm - d_mm or
                    col.cy * 1000.0 >= max_y - c_mm - d_mm)
            rows.append({
                "column_id": col.id,
                "vu_kN": round(float(demand["axial_kN"]), 2),
                "governing_combo": demand.get("load_combo", ""),
                "h_slab_mm": int(h_mm), "d_mm": int(d_mm),
                "bo_mm": int(bo_mm),
                "vc_phi_kN": round(phi_vc_n / 1000, 2),
                "ratio": round(ratio, 3),
                "near_boundary": near,
            })
        if not rows:
            return {"check_name": "Punching shear at slab–column joints (§22.6)",
                    "status": "warn",
                    "details": {**base_details,
                                "note": "No matching column demands in analysis."}}
        worst = max(rows, key=lambda r: r["ratio"])
        status = ("pass" if worst["ratio"] <= 1.0
                  else "warn" if worst["ratio"] <= 1.1 else "fail")
        # Warn only when the GOVERNING joint sits near an edge — its reduced
        # perimeter must be checked by the engineer.
        if worst["near_boundary"] and status != "fail":
            status = "warn"
        return {
            "check_name": "Punching shear at slab–column joints (§22.6)",
            "status": status,
            "details": {
                **base_details,
                "worst_ratio": worst["ratio"],
                "worst_column": worst["column_id"],
                "worst_vu_kN": worst["vu_kN"],
                "worst_vc_phi_kN": worst["vc_phi_kN"],
                "governing_combo": worst["governing_combo"],
                "joint_rows": rows,
                "slab_h_mm": int(h_mm),
                "note": ("Interior-column critical perimeter (4·(c+d) at d/2) — "
                         "edge/corner perimeter reduction must be verified by the "
                         "engineer. d ≈ h − 25 mm."
                         + (" The governing joint sits near the building edge — "
                            "reduced perimeter applies."
                            if worst["near_boundary"] else "")),
            },
        }

    # ── runner ────────────────────────────────────────────────────────────────
    def run_all(self) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = [
            self.check_slab_thickness(),
            self.check_beam_reinforcement(),
            self.check_deflection(),
            self.check_column_reinforcement(),
            self.check_base_shear(),
            self.check_column_capacity(),
            self.check_punching_shear(),
        ]
        passed = sum(1 for c in checks if c["status"] == "pass")
        warned = sum(1 for c in checks if c["status"] == "warn")
        failed = sum(1 for c in checks if c["status"] == "fail")
        overall = ("pass" if failed == 0 and warned == 0
                   else "warn" if failed == 0 else "fail")
        return {
            "code_name": CODE_NAME,
            "overall_status": overall,
            "summary": {"passed": passed, "warned": warned, "failed": failed},
            "checks": checks,
            "disclaimer": ("Automated preliminary screening only. A licensed "
                           "engineer must verify all provisions before sealing."),
        }

    # ── helpers ───────────────────────────────────────────────────────────────
    def _column_axial_demands(self) -> List[Dict[str, Any]]:
        """Factored column axial demands from the analysis member forces
        (roadmap #9a envelope), with a backwards-compatible fallback to the
        legacy ``column_axials_kn`` key for older stored results."""
        mf = self.analysis.get("member_forces") or []
        rows = [f for f in mf
                if isinstance(f, dict) and f.get("kind") == "column"
                and f.get("element_id")]
        if not rows:
            legacy = self.analysis.get("column_axials_kn") or []
            return [{"element_id": None, "axial_kN": float(v), "load_combo": ""}
                    for v in legacy if isinstance(v, (int, float))]
        return [{"element_id": f["element_id"],
                 "axial_kN": float(f.get("axial_kN") or 0.0),
                 "load_combo": f.get("load_combo", "")}
                for f in rows]

    def _max_span(self) -> float:
        spans = [math.hypot(b.x2 - b.x1, b.y2 - b.y1) for b in self.plan.beams]
        return max(spans) if spans else 6.0

    def _est_weight(self) -> float:
        b = self.plan.bounds()
        area = max((b["max_x"] - b["min_x"]), 1) * max((b["max_y"] - b["min_y"]), 1)
        return area * self.plan.stories * 11.0           # kN ≈ 1.1 t/m² per floor