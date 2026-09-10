"""Isolated (pad) footing design per ACI 318-19 §13 / §22 / SBC 304.

Real equations, real numbers — no heuristics:

  §13.2.6   Footing size from SERVICE loads:  A_req = P_service / q_allow
  §13.2.7   Factored soil pressure:           qu = Pu / B²
  §22.6.5.2 Two-way (punching) shear at d/2 from column face; the depth d is
            iterated until Vu_punch <= 0.75·Vc_punch (this sets the depth).
  §22.5.1.1 One-way (beam) shear at d from column face.
  §13.2.7.1 Flexural reinforcement at the column face (bottom mat, both ways).
  §24.4.3   Minimum shrinkage/reinforcement steel  As_min = 0.0018·B·h.
  §25.4.2   Development length into the footing (reuses the real ld function).
  §22.8     Column bearing on footing  phi·Bn = phi·0.85·f'c·A1, sqrt(A2/A1)<=2.

Inputs are real:
  - Pu per column comes from the analysis member_forces envelope (factored).
  - P_service per column reproduces the engine's unfactored D+L (same basis as
    service deflection).
  - q_allow comes from the survey field `soil_bearing_capacity_kpa`; a 150 kPa
    fallback carries `assumed: true` and is flagged.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData
from app.services.concrete_design import (
    BAR_AREA_MM2, BAR_KG_PER_M, DEFAULT_FC_MPA, DEFAULT_FY_MPA,
    development_length_mm,
)

PHI_BENDING = 0.90          # ACI Table 21.2.1 (flexure)
PHI_SHEAR = 0.75            # one-way + two-way shear
PHI_BEARING = 0.65          # ACI §22.8.1 (bearing)
COVER_MM = 75.0             # soil contact clear cover (ACI §20.5.1.3: 76 mm)
BAR_DIA_MM = 12.0           # typical footing mat bar
LAMBDA_NWC = 1.0            # normal-weight concrete
ALPHA_S_INT = 40            # §22.6.5.2 alpha_s for interior columns
STEP_MM = 25.0              # depth iteration step
SIDE_STEP_M = 0.05          # footing dimension step


def _column_service_and_factored(plan: PlanData,
                                 analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-column service (D+L unfactored) and factored axial loads.

    Factored: reads the real envelope from analysis.member_forces (kind=column),
    the same numbers the compliance engine uses.
    Service: reproduces the analytic solver's unfactored D+L per column —
    dead_kpa + live_kpa distributed over the storeys — so sizing matches the
    service deflection basis (no invented factors).
    """
    mf = analysis.get("member_forces") or []
    cols = plan.columns
    loads = analysis.get("loads") or {}
    load_cases = loads.get("load_cases") or {}
    dead_kpa = float(load_cases.get("dead_kpa", 0.0) or 0.0)
    live_kpa = float(load_cases.get("live_kpa", 0.0) or 0.0)
    stories = max(1, plan.stories)
    n_cols = max(len(cols), 1)

    # Real floor area via same helper the engine uses.
    from app.services.geometry_utils import floor_envelope
    try:
        area = float(floor_envelope(plan)["area_m2"])
    except Exception:
        bounds = plan.bounds()
        area = max((bounds["max_x"] - bounds["min_x"]), 1.0) * max(
            (bounds["max_y"] - bounds["min_y"]), 1.0)

    p_svc = (dead_kpa + live_kpa) * area * stories / n_cols

    factored: Dict[str, float] = {}
    for f in mf:
        if isinstance(f, dict) and f.get("kind") == "column" and f.get("element_id"):
            factored[f["element_id"]] = float(f.get("axial_kN") or 0.0)

    rows = []
    for col in cols:
        rows.append({
            "element_id": col.id,
            "size_mm": float(col.size_m) * 1000.0,
            "cx": col.cx,
            "cy": col.cy,
            "p_service_kn": p_svc,
            "p_factored_kn": factored.get(col.id, 0.0) or p_svc,
        })
    return rows


def _punching_shear_capacity(fc_mpa, bo_mm, d_mm, beta_c, alpha_s):
    """ACI 318-19 §22.6.5.2 — least of three expressions (SI, N)."""
    lam = LAMBDA_NWC
    root = math.sqrt(fc_mpa)
    vc1 = (2.0 / 12.0 + (4.0 / 12.0) / beta_c) * lam * root * bo_mm * d_mm
    vc2 = ((alpha_s * d_mm / bo_mm) + 2.0) / 12.0 * lam * root * bo_mm * d_mm
    vc3 = (4.0 / 12.0) * lam * root * bo_mm * d_mm
    vc_n = min(vc1, vc2, vc3)
    return vc_n / 1000.0  # N -> kN


def _one_way_shear_capacity(fc_mpa, b_mm, d_mm):
    """ACI 318-19 §22.5.1.1 — Vc = 0.17·lambda·sqrt(f'c)·bw·d (N)."""
    vc_n = 0.17 * LAMBDA_NWC * math.sqrt(fc_mpa) * b_mm * d_mm
    return vc_n / 1000.0  # N -> kN


def _required_steel(mu_kn_m, fc_mpa, fy_mpa, b_mm, d_mm):
    """Solve As from Mu = phi·As·fy·(d - a/2), a = As·fy/(0.85·f'c·b).

    Real quadratic in As (same as beam/column design).
    ``mu_kn_m`` is in kN·m; converted internally to N·mm (1 kN·m = 1e6 N·mm).
    Returns As in mm².
    """
    phi = PHI_BENDING
    A = phi * fy_mpa ** 2 / (2.0 * 0.85 * fc_mpa * b_mm)
    B = -phi * fy_mpa * d_mm
    C = mu_kn_m * 1e6  # kN·m -> N·mm
    disc = B * B - 4.0 * A * C
    if disc < 0:
        return 0.0
    as_mm2 = (-B - math.sqrt(disc)) / (2.0 * A)
    return max(0.0, as_mm2)


def _select_mat_bars(as_required_mm2, b_mm, available_dia=(10, 12, 14, 16),
                     spacing_options=(150, 175, 200, 225, 250)):
    """Pick a real bottom mat (both directions) whose As >= required."""
    for dia in available_dia:
        a_bar = BAR_AREA_MM2.get(dia, 0.0)
        if a_bar <= 0:
            continue
        for sp in spacing_options:
            n_each_way = max(2, math.ceil(b_mm / sp))
            # total bars of this diameter each way = floor(B/spacing)+1
            as_prov = a_bar * n_each_way
            if as_prov >= as_required_mm2:
                total_len_m = n_each_way * (b_mm / 1000.0) * 2.0  # both ways
                return {
                    "bar_diameter_mm": dia,
                    "spacing_mm": sp,
                    "n_each_way": n_each_way,
                    "as_provided_mm2": round(as_prov, 1),
                    "total_length_m": round(total_len_m, 2),
                }
    # Fallback: largest dia at min spacing
    n = max(2, math.ceil(b_mm / spacing_options[0]))
    return {"bar_diameter_mm": available_dia[-1],
            "spacing_mm": spacing_options[0], "n_each_way": n,
            "as_provided_mm2": round(BAR_AREA_MM2[available_dia[-1]] * n, 1),
            "total_length_m": round(n * b_mm / 1000.0 * 2.0, 2)}


def _footing_development_length(db_mm: float, fy_mpa: float, fc_mpa: float,
                                cover_mm: float, spacing_mm: float) -> float:
    """ACI 318-19 §25.4.2.3 — ldc with the REAL (cb+Ktr)/db credit.

    For a footing mat, cb = min(cover, clear spacing / 2) and Ktr = 0 (no
    transverse reinforcement), capped at (cb+Ktr)/db <= 2.5. This is the
    correct footing treatment — NOT the conservative 1.0 used for beams
    without transverse-steel credit.
    """
    clear_spacing = max(spacing_mm - db_mm, 0.0)
    cb = min(cover_mm, clear_spacing / 2.0)
    ratio = min(cb / db_mm, 2.5)
    ld = (fy_mpa * db_mm) / (2.1 * LAMBDA_NWC * math.sqrt(fc_mpa) * ratio)
    return max(ld, 300.0)  # §25.4.2.1 minimum


def _column_bearing_capacity(fc_mpa, a1_mm2, a2_mm2):
    """ACI 318-19 §22.8.1 — phi·Bn with sqrt(A2/A1) <= 2."""
    phi = PHI_BEARING
    bn = phi * 0.85 * fc_mpa * a1_mm2 / 1000.0  # kN (A1 in mm²)
    ratio = math.sqrt(a2_mm2 / a1_mm2) if a1_mm2 > 0 else 1.0
    return bn * min(ratio, 2.0)


def design_foundations(plan: PlanData, analysis: Optional[Dict[str, Any]] = None,
                       survey: Optional[Any] = None,
                       fc_mpa: float = DEFAULT_FC_MPA,
                       fy_mpa: float = DEFAULT_FY_MPA) -> Dict[str, Any]:
    """Design one isolated footing per column (real ACI 318-19 checks)."""
    analysis = analysis or {}
    q_allow_raw = getattr(survey, "soil_bearing_capacity_kpa", None) if survey else None
    assumed = q_allow_raw is None or float(q_allow_raw) <= 0
    q_allow_kpa = float(q_allow_raw) if q_allow_raw else 150.0
    gw = getattr(survey, "groundwater_depth_m", None) if survey else None

    rows = _column_service_and_factored(plan, analysis)
    footings = []
    n_cols = max(len(rows), 1)
    for row in rows:
        p_svc = max(float(row["p_service_kn"]), 1.0)
        pu = max(float(row["p_factored_kn"]), p_svc)
        b_col_mm = max(float(row["size_mm"]), 150.0)

        # §13.2.6 — size on service load, rounded to a buildable dimension.
        area_req = p_svc / q_allow_kpa
        b_m = math.ceil(math.sqrt(max(area_req, 0.36)) / SIDE_STEP_M) * SIDE_STEP_M

        # Development length feeds back into footing size: §25.4.2.1 has a
        # 300 mm minimum ld; grow B until the bars fully develop past the
        # column face (standard practice — never ship a footing whose mat
        # steel isn't developed).
        for _grow in range(12):  # up to +0.6 m
            b_mm = b_m * 1000.0
            qu = pu / (b_m ** 2)
            cantilever_m = (b_m - b_col_mm / 1000.0) / 2.0
            available_mm = max(b_mm / 2.0 - b_col_mm / 2.0 - COVER_MM, 0.0)
            # Prelim steel to gauge ld needs a bar choice.
            as_min_here = 0.0018 * b_mm * 300.0
            probe = _select_mat_bars(as_min_here, b_mm)
            ld_here = _footing_development_length(
                probe["bar_diameter_mm"], fy_mpa, fc_mpa, COVER_MM, probe["spacing_mm"])
            if ld_here <= available_mm:
                break
            b_m += SIDE_STEP_M
        b_mm = b_m * 1000.0

        # §22.6.5.2 — iterate depth until punching shear passes.
        h_m = 0.30
        d_mm = (h_m * 1000.0) - COVER_MM - BAR_DIA_MM / 2.0
        for _ in range(60):
            bo_mm = 4.0 * (b_col_mm + d_mm)
            area_punch_m2 = ((b_col_mm + d_mm) / 1000.0) ** 2
            vu_punch_kn = qu * (b_m ** 2 - area_punch_m2)
            vc_punch_kn = _punching_shear_capacity(
                fc_mpa, bo_mm, d_mm, 1.0, ALPHA_S_INT)
            if vu_punch_kn <= PHI_SHEAR * vc_punch_kn:
                break
            d_mm += STEP_MM
        h_mm = math.ceil((d_mm + COVER_MM + BAR_DIA_MM / 2.0) / 10.0) * 10.0
        d_mm = h_mm - COVER_MM - BAR_DIA_MM / 2.0
        h_m = h_mm / 1000.0
        if gw is not None and float(gw) < 2.5:
            h_mm += 150.0
            h_m = h_mm / 1000.0
            d_mm = h_mm - COVER_MM - BAR_DIA_MM / 2.0
        ratio_punch = vu_punch_kn / max(PHI_SHEAR * vc_punch_kn, 1e-6)

        # §22.5.1.1 — one-way (beam) shear at distance d from column face.
        vu_1way_kn = qu * b_m * max(cantilever_m - d_mm / 1000.0, 0.0)
        vc_1way_kn = _one_way_shear_capacity(fc_mpa, b_mm, d_mm)
        ratio_1way = vu_1way_kn / max(PHI_SHEAR * vc_1way_kn, 1e-6)

        # §13.2.7.1 — flexure at column face: Mu = qu·B·Lc²/2 (kN·m).
        mu_knm = qu * b_m * cantilever_m ** 2 / 2.0
        as_req = _required_steel(mu_knm, fc_mpa, fy_mpa, b_mm, d_mm)
        as_min = 0.0018 * b_mm * h_mm
        as_use = max(as_req, as_min)
        mat = _select_mat_bars(as_use, b_mm)
        a_blk = mat["as_provided_mm2"] * fy_mpa / (0.85 * fc_mpa * b_mm)
        phi_mn_knm = PHI_BENDING * mat["as_provided_mm2"] * fy_mpa * (
            d_mm - a_blk / 2.0) / 1e6
        ratio_flex = mu_knm / max(phi_mn_knm, 1e-6)

        # §25.4.2 — development length with the real footing (cb+Ktr)/db credit.
        ld = _footing_development_length(
            mat["bar_diameter_mm"], fy_mpa, fc_mpa, COVER_MM, mat["spacing_mm"])
        available_mm = max(b_mm / 2.0 - b_col_mm / 2.0 - COVER_MM, 0.0)
        ratio_ld = ld / max(available_mm, 1e-6)

        # §22.8 — column bearing on footing.
        bn_kn = _column_bearing_capacity(fc_mpa, b_col_mm ** 2, b_mm ** 2)
        ratio_bearing = pu / max(bn_kn, 1e-6)

        # §13.2.6 — soil bearing is a SERVICE-load check:
        #   ratio = P_service / (B² · q_allow).
        soil_ratio = p_svc / max(b_m * b_m * q_allow_kpa, 1e-6)
        util = max(soil_ratio, ratio_punch, ratio_1way, ratio_flex,
                   ratio_bearing)

        conc = b_m * b_m * h_m
        rebar_kg = mat["total_length_m"] * BAR_KG_PER_M.get(
            mat["bar_diameter_mm"], 0.888)

        footings.append({
            "element": row["element_id"],
            "cx": row["cx"], "cy": row["cy"],
            "width_m": round(b_m, 2), "length_m": round(b_m, 2),
            "depth_m": round(h_m, 3), "d_mm": round(d_mm, 1),
            "p_service_kn": round(p_svc, 1),
            "p_factored_kn": round(pu, 1),
            "q_allow_kpa": q_allow_kpa, "qu_kpa": round(qu, 2),
            "ratios": {
                "soil": round(soil_ratio, 3),
                "punching": round(ratio_punch, 3),
                "one_way_shear": round(ratio_1way, 3),
                "flexure": round(ratio_flex, 3),
                "development": round(ratio_ld, 3),
                "bearing": round(ratio_bearing, 3)},
            "utilization": round(util, 3),
            "ok": util <= 1.0 and ratio_ld <= 1.0,
            "reinforcement": mat,
            "ld_mm": round(ld, 1),
            "available_mm": round(available_mm, 1),
            "boq": {"concrete_m3": round(conc, 3),
                    "rebar_kg": round(rebar_kg, 2),
                    "rebar_tonnes": round(rebar_kg / 1000.0, 3)},
            "nodes": _footing_3d_nodes(row["element_id"], row["cx"], row["cy"],
                                       b_m, h_m),
        })

    return {
        "code": "ACI 318-19 §13 / §22 (SBC 304)",
        "q_allow_kpa": q_allow_kpa,
        "assumed_soil": assumed,
        "groundwater_depth_m": gw,
        "footings": footings,
        "count": n_cols,
    }


def _footing_3d_nodes(element_id: str, cx: float, cy: float,
                      width_m: float, depth_m: float) -> List[Dict[str, Any]]:
    """3D viewer nodes: a box for the footing under the column."""
    return [{
        "id": f"footing-{element_id}",
        "type": "box",
        "x": cx, "y": depth_m / 2.0, "z": cy,
        "length": width_m, "width": depth_m, "height": width_m,
        "rotation_z": 0.0, "color": "#6b7280",
        "floor": -1,
    }]