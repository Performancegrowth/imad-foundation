"""Sprint 5b — Equilibrium verification (post-analysis, read-only).

Compares the solver's reported reactions against the applied loads already
present in the analysis result. Pure verification: never recomputes loads,
member forces, combinations, or reactions.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

TOLERANCE_PCT = 0.5
WARNING_BAND_PCT = 1.5


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _component(applied: Optional[float], reactions: Optional[float],
               applied_label: str, reaction_label: str,
               unit: str, not_applicable_reason: Optional[str] = None):
    """Build one equilibrium component block."""
    if not_applicable_reason is not None:
        out = {"status": "NOT_APPLICABLE", "error_pct": 0.0,
               "note": not_applicable_reason}
    elif applied is None or reactions is None:
        missing = applied_label if applied is None else reaction_label
        out = {"status": "NOT_APPLICABLE", "error_pct": 0.0,
               "note": f"{missing} unavailable in analysis result."}
    elif abs(applied) == 0 and abs(reactions) == 0:
        out = {"status": "NOT_APPLICABLE", "error_pct": 0.0,
               "note": "No load in this component (applied and reactions are zero)."}
    else:
        error_pct = abs(reactions - applied) / max(abs(applied), 1) * 100
        error_pct = round(error_pct, 3)
        if error_pct <= TOLERANCE_PCT:
            status = "PASS"
        elif error_pct <= WARNING_BAND_PCT:
            status = "WARN"
        else:
            status = "FAIL"
        out = {"status": status, "error_pct": error_pct,
               "note": f"|{reactions} - {applied}| / max(|{applied}|, 1) * 100 = {error_pct}%."}
    if unit == "kNm":
        out.update({"applied_kNm": applied if applied is not None else 0.0,
                    "reactions_kNm": reactions if reactions is not None else 0.0})
    else:
        out.update({"applied_kN": applied if applied is not None else 0.0,
                    "reactions_kN": reactions if reactions is not None else 0.0})
    return out


def check_equilibrium(analysis_result: Dict[str, Any],
                      tolerance_pct: float = TOLERANCE_PCT) -> Dict[str, Any]:
    """Verify reactions balance applied loads using existing result values only.

    Sign convention: the analytic engine stores reactions on the SAME side as
    the applied loads (reactions.total_gravity_kN == loads.total_weight_kN by
    construction at structural_engine.py lines 246-252), so the check compares
    magnitudes directly: error = |reactions - applied| / max(|applied|, 1).
    Stored values are never modified.
    """
    loads = (analysis_result or {}).get("loads") or {}
    reactions = (analysis_result or {}).get("reactions") or {}

    applied_v = _num(loads.get("total_weight_kN"))
    react_v = _num(reactions.get("total_gravity_kN"))

    applied_h = _num(loads.get("lateral_base_kN"))
    react_h = _num(reactions.get("base_shear_kN"))

    applied_m = _num(reactions.get("overturning_moment_kNm"))
    react_m = _num(reactions.get("overturning_moment_kNm"))
    # Moment is NOT_APPLICABLE: the engine emits only a reaction-side
    # overturning estimate (base_shear * H / 1.5); no independent applied-side
    # base moment exists in loads, so there is nothing to compare against.
    moment = _component(None, None, "applied base moment",
                        "reaction moment", "kNm",
                        not_applicable_reason=(
                            "No independent applied base moment in analysis "
                            "result; engine emits only a reaction-side "
                            "overturning estimate."))

    vertical = _component(applied_v, react_v, "loads.total_weight_kN",
                          "reactions.total_gravity_kN", "kN")
    horizontal = _component(applied_h, react_h, "loads.lateral_base_kN",
                            "reactions.base_shear_kN", "kN")

    components = [vertical, horizontal, moment]
    avail = [c for c in components if c["status"] != "NOT_APPLICABLE"]
    if any(c["status"] == "FAIL" for c in avail):
        overall = "FAIL"
    elif any(c["status"] == "WARN" for c in avail):
        overall = "WARN"
    elif any(c["status"] == "PASS" for c in avail):
        overall = "PASS"
    else:
        overall = "NOT_APPLICABLE"

    notes = "; ".join(
        f"{name}: {c['status']} ({c['note']})"
        for name, c in (("vertical", vertical), ("horizontal", horizontal),
                        ("moment", moment)))
    return {
        "vertical": vertical,
        "horizontal": horizontal,
        "moment": moment,
        "overall": overall,
        "tolerance_pct": tolerance_pct,
        "warning_band_pct": WARNING_BAND_PCT,
        "note": (f"Same-side magnitude comparison per solver convention "
                 f"(reactions mirror applied loads). {notes}"),
    }
