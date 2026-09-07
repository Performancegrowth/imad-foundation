"""Roadmap #9e — SBC 301 seismic (§12.8) and wind (ch. 27) computations."""
import math
import pytest

from app.services.lateral_loads import (
    DEFAULT_CD, DEFAULT_I, DEFAULT_R, DEFAULT_S1, DEFAULT_SITE_CLASS, DEFAULT_SS,
    DEFAULT_WIND_EXPOSURE, DEFAULT_WIND_SPEED_MPS,
    SeismicParameters, WindParameters,
    _interpolate_table, _kz_wind, _site_coefficient,
    approximate_period, compute_spectral_design, elf_base_shear,
    seismic_response_coefficient, velocity_pressure_kpa, wind_base_shear,
)


# ── Seismic (§12.8) ─────────────────────────────────────────────────────────

def test_site_coefficient_interpolation():
    # Site class D, Ss=0.35 → between 0.25 (Fa=1.6) and 0.50 (Fa=1.4)
    fa = _site_coefficient(0.35, "D", 
                           {"D": [1.6, 1.4, 1.2, 1.1, 1.0]}, [0.25, 0.50, 0.75, 1.0, 1.25])
    assert 1.4 < fa < 1.6


def test_site_coefficient_clamps_out_of_range():
    fa_low = _site_coefficient(0.1, "D", {"D": [1.6, 1.4, 1.2, 1.1, 1.0]}, [0.25, 0.50, 0.75, 1.0, 1.25])
    fa_high = _site_coefficient(2.0, "D", {"D": [1.6, 1.4, 1.2, 1.1, 1.0]}, [0.25, 0.50, 0.75, 1.0, 1.25])
    assert fa_low == 1.6
    assert fa_high == 1.0


def test_spectral_design_site_d():
    sd = compute_spectral_design(0.35, 0.12, "D")
    assert sd["fa"] > 1.0  # Site D amplifies
    assert sd["fv"] > 1.0
    assert sd["sds"] > 0
    assert sd["sd1"] > 0
    assert sd["sds"] == pytest.approx((2 / 3) * sd["fa"] * 0.35, rel=1e-3)


def test_approximate_period():
    # Ta = 0.085 · H^0.75 for concrete MRF
    t = approximate_period(6.0)
    assert t == pytest.approx(0.085 * (6.0 ** 0.75), rel=1e-3)
    assert t > 0


def test_seismic_response_coefficient_bounds():
    # Cs must be between Cs_min and Cs_max
    cs_data = seismic_response_coefficient(0.35, 0.18, 5.0, 1.0, 0.326)
    assert cs_data["cs_min"] <= cs_data["cs"] <= cs_data["cs_max"]


def test_elf_base_shear_computes_real_cs():
    """Cs must come from SBC 301 tables, NOT hardcoded 0.10."""
    sp = SeismicParameters(ss=0.35, s1=0.12, site_class="D", height_m=6.0)
    result = elf_base_shear(0.0, 0.0, 500.0, sp)
    assert result["cs"] != 0.10  # NOT the old hardcoded value
    assert result["cs"] > 0
    assert result["base_shear_kn"] == pytest.approx(result["cs"] * 500.0, rel=1e-2)
    assert result["period_s"] > 0
    # Provenance must cite the code
    assert "SBC 301" in result["provenance"]["method"]
    assert result["provenance"]["site_class"] == "D"


def test_elf_base_shear_with_survey_params():
    """When survey provides Ss/S1/site_class, they drive the computation."""
    sp = SeismicParameters(ss=0.8, s1=0.3, site_class="C", height_m=9.0, stories=3)
    result = elf_base_shear(0.0, 0.0, 1000.0, sp)
    assert result["provenance"]["ss"] == 0.8
    assert result["provenance"]["s1"] == 0.3
    assert result["provenance"]["site_class"] == "C"
    # Higher Ss → higher Cs → higher base shear
    assert result["cs"] > 0.05


def test_elf_base_shear_deterministic():
    sp = SeismicParameters(ss=0.35, s1=0.12, site_class="D", height_m=6.0)
    a = elf_base_shear(0.0, 0.0, 500.0, sp)
    b = elf_base_shear(0.0, 0.0, 500.0, sp)
    assert a["cs"] == b["cs"]
    assert a["base_shear_kn"] == b["base_shear_kn"]


# ── Wind (ch. 27) ───────────────────────────────────────────────────────────

def test_kz_wind_interpolation():
    # Exposure B at 5m → 0.62, at 10m → 0.72
    kz_5 = _kz_wind(5.0, "B")
    kz_10 = _kz_wind(10.0, "B")
    assert kz_5 == pytest.approx(0.62, abs=0.01)
    assert kz_10 == pytest.approx(0.72, abs=0.01)
    assert kz_10 > kz_5  # higher elevation → higher Kz


def test_kz_wind_exposure_categories():
    # At same height, exposure D > C > B
    kz_b = _kz_wind(10.0, "B")
    kz_c = _kz_wind(10.0, "C")
    kz_d = _kz_wind(10.0, "D")
    assert kz_d > kz_c > kz_b


def test_velocity_pressure():
    # qz = 0.613 · Kz · Kzt · Kd · Ke · V² (kPa)
    qz = velocity_pressure_kpa(6.0, 32.0, "B", 1.0, 0.85, 1.0)
    assert qz > 0
    # Higher wind speed → much higher qz (V²)
    qz_half = velocity_pressure_kpa(6.0, 16.0, "B", 1.0, 0.85, 1.0)
    assert qz == pytest.approx(4 * qz_half, rel=0.05)


def test_wind_base_shear():
    wp = WindParameters(height_m=6.0, width_m=12.0, length_m=20.0)
    result = wind_base_shear(wp)
    assert result["base_shear_kn"] > 0
    assert result["qz_kpa"] > 0
    assert "SBC 301" in result["provenance"]["method"]
    assert result["provenance"]["basic_wind_speed_mps"] == DEFAULT_WIND_SPEED_MPS


def test_wind_base_shear_deterministic():
    wp = WindParameters(height_m=6.0, width_m=12.0, length_m=20.0)
    a = wind_base_shear(wp)
    b = wind_base_shear(wp)
    assert a["base_shear_kn"] == b["base_shear_kn"]


def test_wind_base_shear_with_survey_params():
    """When survey provides wind speed/exposure, they drive the computation."""
    wp = WindParameters(basic_wind_speed_mps=40.0, exposure_category="C",
                        height_m=9.0, width_m=15.0, length_m=25.0, stories=3)
    result = wind_base_shear(wp)
    assert result["provenance"]["basic_wind_speed_mps"] == 40.0
    assert result["provenance"]["exposure"] == "C"
    assert result["base_shear_kn"] > 0


# ── Defaults are Saudi-appropriate ─────────────────────────────────────────

def test_defaults_saudi_appropriate():
    assert DEFAULT_SS == 0.35
    assert DEFAULT_S1 == 0.12
    assert DEFAULT_SITE_CLASS == "D"
    assert DEFAULT_R == 5.0
    assert DEFAULT_WIND_SPEED_MPS == 32.0
    assert DEFAULT_WIND_EXPOSURE == "B"