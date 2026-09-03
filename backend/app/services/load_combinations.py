"""SBC 301 / ACI 318-19 §5.3 strength load combinations (roadmap #9a).

The structural engine previously designed members at service-level demand
(D + L at 1.0). This module provides the code strength combinations and the
envelope math so every member demand carries its governing combination.

Design notes
------------
* Combinations follow ACI 318-19 §5.3 (SBC 301/304 adopt the ACI basis).
  Roof live/snow/rain terms (``Lr``, ``S``, ``R``) are intentionally absent —
  the plan model does not yet carry separate roof loads; this is flagged in
  ``NOTES`` so reports can disclose it honestly.
* Linear-elastic superposition: each load case's member actions are computed
  independently, then combined per combo. Valid for the linear static engine.
* Enveloping: moment and shear envelope on |max| (both senses matter);
  axial envelopes on both max (compression) and min (tension/uplift) so the
  0.9D + 1.0E case can govern columns.
* Serviceability (deflection) is NEVER factored — combos are for strength;
  the engine reports service deflections separately.
"""
from __future__ import annotations

from typing import Any, Dict, List

CODE_SOURCE = "SBC 301 (adopted from ACI 318-19 §5.3) strength load combinations"

NOTES = [
    "Roof live (Lr), snow (S) and rain (R) terms are omitted — the plan model "
    "does not carry separate roof loads yet.",
    "Live-load reduction (ACI 318-19 §5.3.3 exception / ASCE 7 §4.7) is not "
    "applied — conservative for preliminary design.",
]

# Load-case identifiers: D = dead, L = live, E = seismic (ELF), W = wind.
_BASIC_STRENGTH: List[Dict[str, Any]] = [
    {"id": "LC1", "name": "1.4D", "factors": {"D": 1.4}},
    {"id": "LC2", "name": "1.2D + 1.6L", "factors": {"D": 1.2, "L": 1.6}},
    {"id": "LC3", "name": "1.2D + 1.0E + 1.0L",
     "factors": {"D": 1.2, "E": 1.0, "L": 1.0}},
    {"id": "LC4", "name": "0.9D + 1.0E", "factors": {"D": 0.9, "E": 1.0}},
]

_WIND_COMBOS: List[Dict[str, Any]] = [
    {"id": "LC5", "name": "1.2D + 1.0W + 1.0L",
     "factors": {"D": 1.2, "W": 1.0, "L": 1.0}},
    {"id": "LC6", "name": "0.9D + 1.0W", "factors": {"D": 0.9, "W": 1.0}},
]


def strength_combinations(include_seismic: bool = True,
                          include_wind: bool = False) -> List[Dict[str, Any]]:
    """The applied strength combinations as data (id, name, factors).

    ``E``/``W`` cases are only meaningful when the engine produced those load
    cases; callers pass flags so the applied set is always truthful.
    """
    combos: List[Dict[str, Any]] = []
    for combo in _BASIC_STRENGTH:
        uses_e = "E" in combo["factors"]
        if uses_e and not include_seismic:
            continue
        combos.append(combo)
    if include_wind:
        combos.extend(_WIND_COMBOS)
    return [dict(c, source=CODE_SOURCE) for c in combos]


def combine(factors: Dict[str, float], case_actions: Dict[str, float]) -> float:
    """Factored total of one action: Σ γ_i × (action of load case i).

    ``case_actions`` maps load-case id → that case's action on the member.
    Missing cases contribute 0.
    """
    return sum(factor * case_actions.get(case, 0.0)
               for case, factor in factors.items())


def envelope(actions_by_case: Dict[str, Dict[str, float]],
             combos: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-member governing demand across all combos.

    Args:
        actions_by_case: ``{load_case_id: {action: value}}`` for ONE member,
            e.g. ``{"D": {"M": 10.0, "V": 5.0, "N": 0.0}, ...}``.
        combos: as returned by :func:`strength_combinations`.

    Returns:
        ``{"M": {"value", "combo"}, "V": {...}, "N_max": {...}, "N_min": {...}}``
        — M and V envelope on absolute value (both load senses matter);
        N envelopes separately on max (compression) and min (tension), so a
        0.9D + 1.0E uplift case can govern columns.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for action in ("M", "V", "N"):
        best_max: Dict[str, Any] | None = None
        best_min: Dict[str, Any] | None = None
        for combo in combos:
            total = combine(combo["factors"],
                            {case: vals.get(action, 0.0)
                             for case, vals in actions_by_case.items()})
            if best_max is None or total > best_max["value"]:
                best_max = {"value": total, "combo": combo["name"],
                            "combo_id": combo["id"]}
            if best_min is None or total < best_min["value"]:
                best_min = {"value": total, "combo": combo["name"],
                            "combo_id": combo["id"]}
        if action == "N":
            out["N_max"] = best_max or {"value": 0.0, "combo": "", "combo_id": ""}
            out["N_min"] = best_min or {"value": 0.0, "combo": "", "combo_id": ""}
        else:
            out[action] = best_max or {"value": 0.0, "combo": "", "combo_id": ""}
    return out
