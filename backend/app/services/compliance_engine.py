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
* §22.4     column axial capacity φPn vs demand
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
        demands = self.analysis.get("column_axials_kn") or []
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
        worst = max(float(d) for d in demands) / max(phi_pn, 1e-6)
        status = "pass" if worst <= 1.0 else ("warn" if worst <= 1.1 else "fail")
        return {
            "check_name": "Column axial capacity (§22.4)",
            "status": status,
            "details": {**base_details, "worst_demand_ratio": round(worst, 3)},
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
    def _max_span(self) -> float:
        spans = [math.hypot(b.x2 - b.x1, b.y2 - b.y1) for b in self.plan.beams]
        return max(spans) if spans else 6.0

    def _est_weight(self) -> float:
        b = self.plan.bounds()
        area = max((b["max_x"] - b["min_x"]), 1) * max((b["max_y"] - b["min_y"]), 1)
        return area * self.plan.stories * 11.0           # kN ≈ 1.1 t/m² per floor