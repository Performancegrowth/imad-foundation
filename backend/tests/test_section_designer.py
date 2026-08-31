"""Sprint 7 — Section Designer tests.

The analytic path is exercised against closed-form references; the
sectionproperties bridge is validated with an injected fake module (same
pattern as the IFC tests) so the suite stays lean.
"""
from __future__ import annotations

import sys
import types

import pytest

from app.services.section_designer import (
    MATERIALS,
    SectionDesigner,
    SectionDesignError,
    _analyze_with_sp,
    _normalize_section,
)


@pytest.fixture
def designer():
    return SectionDesigner()


# ────────────────────────────────────────────────── analytic correctness ────
def test_rect_properties_match_closed_form(designer):
    r = designer.analyze({"shape": "rect", "b": 300, "d": 500}, force_analytic=True)
    assert r["solver"] == "analytic"
    assert r["area_mm2"] == pytest.approx(150_000.0)
    assert r["ixx_mm4"] == pytest.approx(300 * 500**3 / 12)
    assert r["iyy_mm4"] == pytest.approx(500 * 300**3 / 12)
    assert r["zxx_mm3"] == pytest.approx(300 * 500**2 / 6)
    assert r["sxx_mm3"] == pytest.approx(300 * 500**2 / 4)   # b·d²/4
    assert r["centroid"] == {"x_mm": 150.0, "y_mm": 250.0}


def test_circle_properties_match_closed_form(designer):
    r = designer.analyze({"shape": "circle", "d": 400}, force_analytic=True)
    assert r["area_mm2"] == pytest.approx(3.14159265 * 400**2 / 4, rel=1e-5)
    assert r["ixx_mm4"] == pytest.approx(3.14159265 * 400**4 / 64, rel=1e-5)
    assert r["sxx_mm3"] == pytest.approx(400**3 / 6.0)        # D³/6
    assert r["j_mm4"] == pytest.approx(3.14159265 * 400**4 / 32, rel=1e-5)


def test_i_beam_area_and_inertia(designer):
    r = designer.analyze({"shape": "i", "h": 500, "bf": 300, "tf": 20, "tw": 12},
                         force_analytic=True)
    hw = 500 - 2 * 20
    assert r["area_mm2"] == pytest.approx(2 * 300 * 20 + hw * 12)      # 17 520
    assert r["ixx_mm4"] == pytest.approx(
        (300 * 500**3 - (300 - 12) * hw**3) / 12)
    assert r["iyy_mm4"] == pytest.approx(2 * (20 * 300**3 / 12) + hw * 12**3 / 12)
    # plastic strong axis: flanges + web contribution
    assert r["sxx_mm3"] == pytest.approx(300 * 20 * 480 + 12 * hw**2 / 4)


def test_tee_centroid_sits_toward_flange(designer):
    r = designer.analyze({"shape": "tee", "h": 400, "bf": 300, "tf": 25, "tw": 15},
                         force_analytic=True)
    ybar = r["centroid"]["y_mm"]
    # Asymmetric: centroid above mid-depth; plastic moduli need SP.
    assert 200 < ybar < 400
    assert r["sxx_mm3"] is None
    assert r["zxx_mm3"] == pytest.approx(min(r["zxx_top_mm3"], r["zxx_bottom_mm3"]))


def test_channel_centroid_shifts_to_web(designer):
    r = designer.analyze({"shape": "channel", "h": 400, "bf": 150, "tf": 20, "tw": 12},
                         force_analytic=True)
    assert r["centroid"]["x_mm"] < 75.0     # pulled toward the web
    assert r["syy_mm3"] is None
    assert r["sxx_mm3"] == pytest.approx(150 * 20 * 380 + 12 * 360**2 / 4)


def test_capacities_from_properties(designer):
    rect = designer.analyze({"shape": "rect", "b": 300, "d": 500}, force_analytic=True)
    caps = designer.capacities(rect, MATERIALS["S355"])
    assert caps["n_pl_kN"] == pytest.approx(150_000 * 355 / 1000)
    assert caps["m_el_kNm"] == pytest.approx(12_500_000 * 355 / 1e6)
    assert caps["m_pl_kNm"] == pytest.approx(18_750_000 * 355 / 1e6)
    assert caps["weight_kg_per_m"] == pytest.approx(150_000e-6 * 7850)


# ─────────────────────────────────────────────────────── input validation ────
def test_unknown_shape_rejected():
    with pytest.raises(SectionDesignError, match="Unsupported shape"):
        _normalize_section({"shape": "hexagon", "b": 10, "d": 10})


def test_missing_dimension_rejected():
    with pytest.raises(SectionDesignError, match="requires numeric"):
        _normalize_section({"shape": "i", "h": 500, "bf": 300, "tf": 20})


def test_negative_and_nan_dimensions_rejected():
    with pytest.raises(SectionDesignError, match="positive finite"):
        _normalize_section({"shape": "rect", "b": -5, "d": 100})
    with pytest.raises(SectionDesignError, match="positive finite"):
        _normalize_section({"shape": "rect", "b": float("nan"), "d": 100})


def test_analyze_surfaces_validation_errors(designer):
    with pytest.raises(SectionDesignError):
        designer.analyze({"shape": "nope"})


# ────────────────────────────────────────── sectionproperties bridge ────────
class _FakeSPSection:
    """Mimics sectionproperties.analysis.Section's getter surface."""

    def __init__(self, geometry):
        self.geometry = geometry

    def calculate_geometric_properties(self):
        pass

    def calculate_plastic_properties(self):
        pass

    def calculate_torsion_properties(self):
        pass

    def get_area(self):
        return 123456.0

    def get_perimeter(self):
        return 1600.0

    def get_centroids(self):
        return (150.0, 250.0)

    def get_second_moments(self):
        return (3.1e9, 1.1e9, 0.0)

    def get_radii_of_gyration(self):
        return (158.5, 94.4)

    def get_section_moduli(self):
        return (12.4e6, 4.4e6, 0.0)

    def get_plastic_section_moduli(self):
        return (18.7e6, 6.6e6)

    def get_torsion_props(self):
        return (987654321.0, 0.0)


@pytest.fixture
def fake_sp(monkeypatch):
    import app.services.section_designer as sd

    geom_holder = {}

    def fake_builder(dims):
        geom_holder["dims"] = dict(dims)
        return object()  # opaque geometry handle

    monkeypatch.setattr(sd, "_SP_BUILDERS",
                        {"rect": fake_builder, "i": fake_builder})
    monkeypatch.setattr(sd, "_shape_builder",
                        lambda shape: sd._SP_BUILDERS.get(shape))
    monkeypatch.setattr(sd, "_SP_Section", _FakeSPSection)
    monkeypatch.setattr(sd, "_mesh", lambda geometry, size: geometry)
    return geom_holder


def test_sp_bridge_maps_full_result(fake_sp):
    shape, dims = _normalize_section({"shape": "rect", "b": 300, "d": 500})
    out = _analyze_with_sp(shape, dims, mesh_size=5.0)
    assert out["shape"] == "rect"
    assert out["area_mm2"] == pytest.approx(123_456.0)
    assert out["centroid"] == {"x_mm": 150.0, "y_mm": 250.0}
    assert out["ixx_mm4"] == pytest.approx(3.1e9)
    assert out["sxx_mm3"] == pytest.approx(18.7e6)
    assert out["j_mm4"] == pytest.approx(987_654_321.0)
    assert out["perimeter_mm"] == pytest.approx(1600.0)


def test_analyze_prefers_sp_when_available(designer, fake_sp, monkeypatch):
    import app.services.section_designer as sd

    monkeypatch.setattr(sd, "SECTIONPROPERTIES_AVAILABLE", True)
    r = designer.analyze({"shape": "rect", "b": 300, "d": 500})
    assert r["solver"] == "sectionproperties"
    assert fake_sp["dims"] == {"b": 300.0, "d": 500.0}


def test_analyze_falls_back_when_sp_crashes(designer, fake_sp, monkeypatch):
    import app.services.section_designer as sd

    monkeypatch.setattr(sd, "SECTIONPROPERTIES_AVAILABLE", True)

    def boom(*args, **kwargs):
        raise RuntimeError("mesh exploded")

    monkeypatch.setattr(sd, "_analyze_with_sp", boom)
    r = designer.analyze({"shape": "rect", "b": 300, "d": 500})
    assert r["solver"] == "analytic"
    assert r["area_mm2"] == pytest.approx(150_000.0)


# ─────────────────────────────────────────────────────────────── API ────────
def test_sections_api_analyze_and_validation():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        res = client.post("/api/v1/sections/analyze",
                          json={"section": {"shape": "rect", "b": 300, "d": 500},
                                "material": {"name": "S355"}})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "completed"
        assert body["area_mm2"] == pytest.approx(150_000.0)
        assert body["capacities"]["n_pl_kN"] == pytest.approx(53_250.0, rel=1e-3)

        bad = client.post("/api/v1/sections/analyze",
                          json={"section": {"shape": "rect", "b": -1, "d": 500}})
        assert bad.status_code == 422