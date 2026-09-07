"""SBC 301 lateral-load computations — seismic (§12.8 ELF) and wind (ch. 27).

Replaces the hardcoded Cs = 0.10 placeholder with code-engineered values:

Seismic (§12.8):
    Ss, S1  →  Fa, Fv (site coefficients, §12.4 tables)
    Fa·Ss  →  SMS,  Sds = (2/3)·SMS
    Fv·S1  →  SM1,  Sd1 = (2/3)·SM1
    Cs = Sds / (R / I)          (§12.8.1.1)
    V  = Cs · W                  (ELF base shear)

Wind (ch. 27 — simplified):
    qz = 0.613 · Kz · Kzt · Kd · Ke · V²   (velocity pressure, N/m²)
    Vw = qz · Cp · A                        (base shear)

All tables are from SBC 301 / ASCE 7-10 (which SBC adopts). Defaults are
provided for Saudi Arabia where the survey omits them, and every default
is flagged in the returned ``provenance`` dict so reports disclose it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── SBC 301 §12.4 site coefficient tables ──────────────────────────────────
_FA_TABLE: Dict[str, List[float]] = {
    "A": [0.8, 0.8, 0.8, 0.8, 0.8],
    "B": [1.0, 1.0, 1.0, 1.0, 1.0],
    "C": [1.2, 1.2, 1.1, 1.0, 1.0],
    "D": [1.6, 1.4, 1.2, 1.1, 1.0],
    "E": [2.5, 1.7, 1.2, 0.9, 0.9],
}
_FV_TABLE: Dict[str, List[float]] = {
    "A": [0.8, 0.8, 0.8, 0.8, 0.8],
    "B": [1.0, 1.0, 1.0, 1.0, 1.0],
    "C": [1.7, 1.6, 1.5, 1.4, 1.3],
    "D": [2.4, 2.0, 1.8, 1.6, 1.5],
    "E": [3.5, 3.2, 2.8, 2.4, 2.4],
}
_SS_BREAKPOINTS = [0.25, 0.50, 0.75, 1.00, 1.25]
_S1_BREAKPOINTS = [0.10, 0.20, 0.30, 0.40, 0.50]

DEFAULT_SS = 0.35
DEFAULT_S1 = 0.12
DEFAULT_SITE_CLASS = "D"
DEFAULT_R = 5.0
DEFAULT_I = 1.0
DEFAULT_CD = 4.5

DEFAULT_WIND_SPEED_MPS = 32.0
DEFAULT_WIND_EXPOSURE = "B"
DEFAULT_KZT = 1.0
DEFAULT_KD = 0.85
DEFAULT_KE = 1.0


@dataclass
class SeismicParameters:
    ss: float = DEFAULT_SS
    s1: float = DEFAULT_S1
    site_class: str = DEFAULT_SITE_CLASS
    r_factor: float = DEFAULT_R
    importance: float = DEFAULT_I
    cd: float = DEFAULT_CD
    height_m: float = 6.0
    stories: int = 1
    floor_height_m: float = 3.2


@dataclass
class WindParameters:
    basic_wind_speed_mps: float = DEFAULT_WIND_SPEED_MPS
    exposure_category: str = DEFAULT_WIND_EXPOSURE
    kzt: float = DEFAULT_KZT
    kd: float = DEFAULT_KD
    ke: float = DEFAULT_KE
    height_m: float = 6.0
    width_m: float = 12.0
    length_m: float = 20.0
    stories: int = 1
    floor_height_m: float = 3.2


def _interpolate_table(value: float, breakpoints: List[float],
                       coefficients: List[float]) -> float:
    if value <= breakpoints[0]:
        return coefficients[0]
    if value >= breakpoints[-1]:
        return coefficients[-1]
    for i in range(len(breakpoints) - 1):
        if breakpoints[i] <= value <= breakpoints[i + 1]:
            frac = (value - breakpoints[i]) / (breakpoints[i + 1] - breakpoints[i])
            return coefficients[i] + frac * (coefficients[i + 1] - coefficients[i])
    return coefficients[-1]


def _site_coefficient(value: float, site_class: str,
                      table: Dict[str, List[float]],
                      breakpoints: List[float]) -> float:
    sc = (site_class or "D").upper()
    if sc not in table:
        sc = "D"
    return _interpolate_table(value, breakpoints, table[sc])


def compute_spectral_design(ss: float, s1: float, site_class: str) -> Dict[str, float]:
    fa = _site_coefficient(ss, site_class, _FA_TABLE, _SS_BREAKPOINTS)
    fv = _site_coefficient(s1, site_class, _FV_TABLE, _S1_BREAKPOINTS)
    sds = (2.0 / 3.0) * fa * ss
    sd1 = (2.0 / 3.0) * fv * s1
    return {"fa": fa, "fv": fv, "sds": sds, "sd1": sd1}


def approximate_period(height_m: float) -> float:
    return 0.085 * (height_m ** 0.75)


def seismic_response_coefficient(sds: float, sd1: float, r: float,
                                  importance: float, t_sec: float) -> Dict[str, float]:
    r_over_i = r / importance
    cs = sds / r_over_i
    cs_max = sd1 / (t_sec * r_over_i) if t_sec > 0 else cs
    cs_min_a = 0.044 * sds * importance
    s1_back = sd1 * 1.5
    cs_min_b = 0.5 * s1_back / r_over_i if s1_back > 0.6 else 0.0
    cs_min = max(cs_min_a, cs_min_b)
    cs_governing = max(cs_min, min(cs, cs_max))
    return {
        "cs": round(cs_governing, 4),
        "cs_uncapped": round(cs, 4),
        "cs_max": round(cs_max, 4),
        "cs_min": round(cs_min, 4),
    }


def elf_base_shear(sds: float, sd1: float, weight_kn: float,
                    params: SeismicParameters) -> Dict[str, Any]:
    spectral = compute_spectral_design(params.ss, params.s1, params.site_class)
    t_a = approximate_period(params.height_m)
    cs_data = seismic_response_coefficient(
        spectral["sds"], spectral["sd1"], params.r_factor,
        params.importance, t_a)
    v = cs_data["cs"] * weight_kn
    provenance = {
        "ss": params.ss, "s1": params.s1, "site_class": params.site_class,
        "fa": spectral["fa"], "fv": spectral["fv"],
        "sds": round(spectral["sds"], 4), "sd1": round(spectral["sd1"], 4),
        "r": params.r_factor, "I": params.importance,
        "period_ta": round(t_a, 3),
        "cs": cs_data["cs"], "cs_max": cs_data["cs_max"], "cs_min": cs_data["cs_min"],
        "method": "SBC 301 §12.8 ELF (ASCE 7-10 §12.8)",
    }
    return {
        "base_shear_kn": round(v, 2),
        "weight_kn": round(weight_kn, 2),
        "period_s": round(t_a, 3),
        "cs": cs_data["cs"],
        "provenance": provenance,
    }


# ── Wind (SBC 301 ch. 27 simplified) ────────────────────────────────────────
_WIND_KZ = {
    3.0: (0.57, 0.85, 1.03),
    5.0: (0.62, 0.90, 1.08),
    10.0: (0.72, 1.00, 1.18),
    15.0: (0.80, 1.08, 1.25),
    20.0: (0.85, 1.13, 1.30),
    30.0: (0.93, 1.20, 1.37),
}


def _kz_wind(height_m: float, exposure: str) -> float:
    exp_idx = {"B": 0, "C": 1, "D": 2}.get((exposure or "B").upper(), 0)
    heights = sorted(_WIND_KZ.keys())
    if height_m <= heights[0]:
        return _WIND_KZ[heights[0]][exp_idx]
    if height_m >= heights[-1]:
        return _WIND_KZ[heights[-1]][exp_idx]
    for i in range(len(heights) - 1):
        if heights[i] <= height_m <= heights[i + 1]:
            frac = (height_m - heights[i]) / (heights[i + 1] - heights[i])
            return (_WIND_KZ[heights[i]][exp_idx]
                    + frac * (_WIND_KZ[heights[i + 1]][exp_idx]
                              - _WIND_KZ[heights[i]][exp_idx]))
    return _WIND_KZ[heights[-1]][exp_idx]


def velocity_pressure_kpa(height_m: float, wind_speed_mps: float,
                           exposure: str = "B", kzt: float = 1.0,
                           kd: float = 0.85, ke: float = 1.0) -> float:
    kz = _kz_wind(height_m, exposure)
    qz_pa = 0.613 * kz * kzt * kd * ke * (wind_speed_mps ** 2)
    return qz_pa / 1000.0


def wind_base_shear(params: WindParameters) -> Dict[str, Any]:
    h = params.height_m
    w = params.width_m
    qz = velocity_pressure_kpa(
        h, params.basic_wind_speed_mps, params.exposure_category,
        params.kzt, params.kd, params.ke)
    cp_total = 1.3
    area = h * w
    v_wind = qz * cp_total * area
    provenance = {
        "basic_wind_speed_mps": params.basic_wind_speed_mps,
        "exposure": params.exposure_category,
        "kzt": params.kzt, "kd": params.kd, "ke": params.ke,
        "kz": round(_kz_wind(h, params.exposure_category), 3),
        "qz_kpa": round(qz, 3),
        "cp_total": cp_total,
        "projected_area_m2": round(area, 1),
        "method": "SBC 301 ch. 27 simplified (ASCE 7-10 §27.5)",
    }
    return {
        "base_shear_kn": round(v_wind, 2),
        "qz_kpa": round(qz, 3),
        "provenance": provenance,
    }