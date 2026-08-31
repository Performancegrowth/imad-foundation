"""
Sprint 7 — Section Designer (cross-section properties & design).

Computes the geometric and plastic section properties fundamental to
engineering design — area, centroid, second moments of area, radii of
gyration, elastic & plastic moduli, torsion constant. Uses the
``sectionproperties`` package (finite-element cross-section analysis) when
available for accurate results incl. composite/polygon sections, and falls
back to exact closed-form (pure-Python) formulas for the standard structural
shapes — rectangle, circle, I-beam, tee and channel — so the API and tests
stay fully functional in a lean environment.

Dimensions are in **millimetres** (the native unit of both
``sectionproperties`` and conventional section tables).
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

log = logging.getLogger("imad.sections")

try:
    from sectionproperties.analysis import Section as _SP_Section
    import sectionproperties.pre.library as _SP_LIB

    SECTIONPROPERTIES_AVAILABLE = True
except Exception:  # pragma: no cover - sectionproperties is optional
    _SP_Section = None
    _SP_LIB = None
    SECTIONPROPERTIES_AVAILABLE = False

# ── Material defaults (preliminary design; override per request) ────────────
MATERIALS: Dict[str, Dict[str, float]] = {
    # name:  elastic modulus MPa, yield MPa, density kg/m3
    "S275": {"e_mpa": 210_000.0, "fy": 275.0, "density": 7850.0},
    "S355": {"e_mpa": 210_000.0, "fy": 355.0, "density": 7850.0},
    "C30": {"e_mpa": 30_000.0, "fc": 30.0, "density": 2400.0},
    "C40": {"e_mpa": 32_500.0, "fc": 40.0, "density": 2400.0},
}


class SectionDesignError(Exception):
    """Raised when a section cannot be analysed."""


SUPPORTED_SHAPES = ("rect", "circle", "i", "tee", "channel")

# Map of the ``sectionproperties`` pre.library builder for every shape we
# can bridge to. Each builder takes *one* section dict and returns a geometry.
_SP_BUILDERS: Dict[str, Any] = {}


def _shape_builder(shape: str):
    """Registered sectionproperties builder for a shape (or None)."""
    return _SP_BUILDERS.get(shape)
# ─────────────────────────────────────────────── analytic section tables ────
def _rect_result(b: float, d: float) -> Dict[str, Any]:
    """Rectangle b (width) × d (depth), both mm. Centroid at (b/2, d/2)."""
    a = b * d
    ixx = b * d ** 3 / 12.0
    iyy = d * b ** 3 / 12.0
    return {
        "shape": "rect",
        "area_mm2": a,
        "centroid": {"x_mm": b / 2.0, "y_mm": d / 2.0},
        "ixx_mm4": ixx, "iyy_mm4": iyy, "ixy_mm4": 0.0,
        "rx_mm": math.sqrt(ixx / a), "ry_mm": math.sqrt(iyy / a),
        "zxx_mm3": ixx / (d / 2.0), "zyy_mm3": iyy / (b / 2.0),
        "sxx_mm3": b * d * d / 4.0, "syy_mm3": d * b * b / 4.0,
        "j_mm4": _rect_torsion(b, d),
    }


def _rect_torsion(b: float, d: float) -> float:
    """Saint-Venant torsion constant for a solid rectangle (b ≤ d)."""
    b, d = min(b, d), max(b, d)
    return (b ** 3 * d / 3.0) * (1.0 - 0.63 * (b / d) + 0.052 * (b / d) ** 5)


def _circle_result(d: float) -> Dict[str, Any]:
    """Solid circle of diameter d (mm)."""
    a = math.pi * d * d / 4.0
    i = math.pi * d ** 4 / 64.0
    return {
        "shape": "circle",
        "area_mm2": a,
        "centroid": {"x_mm": d / 2.0, "y_mm": d / 2.0},
        "ixx_mm4": i, "iyy_mm4": i, "ixy_mm4": 0.0,
        "rx_mm": math.sqrt(i / a), "ry_mm": math.sqrt(i / a),
        "zxx_mm3": math.pi * d ** 3 / 32.0, "zyy_mm3": math.pi * d ** 3 / 32.0,
        "sxx_mm3": d ** 3 / 6.0, "syy_mm3": d ** 3 / 6.0,
        "j_mm4": math.pi * d ** 4 / 32.0,
    }


def _i_result(h: float, bf: float, tf: float, tw: float) -> Dict[str, Any]:
    """Symmetric I-section: h total depth, bf flange width, tf flange
    thickness, tw web thickness (all mm). Centroid at mid-depth."""
    hw = max(h - 2 * tf, 0.0)                     # web clear height
    a = 2 * bf * tf + hw * tw
    ixx = (bf * h ** 3 - (bf - tw) * hw ** 3) / 12.0
    iyy = 2 * (tf * bf ** 3 / 12.0) + hw * tw ** 3 / 12.0
    sxx = bf * tf * (h - tf) + tw * hw * hw / 4.0          # plastic strong axis
    syy = (hw * tw * tw / 4.0) + 2.0 * (tf * bf * bf / 4.0) # plastic weak axis
    j = (2 * bf * tf ** 3 + hw * tw ** 3) / 3.0            # thin-walled J
    return {
        "shape": "i",
        "area_mm2": a,
        "centroid": {"x_mm": bf / 2.0, "y_mm": h / 2.0},
        "ixx_mm4": ixx, "iyy_mm4": iyy, "ixy_mm4": 0.0,
        "rx_mm": math.sqrt(ixx / a), "ry_mm": math.sqrt(iyy / a),
        "zxx_mm3": ixx / (h / 2.0), "zyy_mm3": iyy / (bf / 2.0),
        "sxx_mm3": sxx, "syy_mm3": syy,
        "j_mm4": j,
    }
def _tee_result(h: float, bf: float, tf: float, tw: float) -> Dict[str, Any]:
    """Tee section (flange on top): asymmetric about the horizontal axis,
    so we track two elastic moduli (top/bottom extreme fibres)."""
    a = bf * tf + (h - tf) * tw
    y_fl, y_w = h - tf / 2.0, (h - tf) / 2.0          # centroid of parts fr. bottom
    ybar = (bf * tf * y_fl + (h - tf) * tw * y_w) / a
    ixx_btm = (bf * tf ** 3 / 12.0 + bf * tf * y_fl ** 2
               + tw * (h - tf) ** 3 / 12.0 + (h - tf) * tw * y_w ** 2)
    ixx = ixx_btm - a * ybar ** 2
    iyy = tf * bf ** 3 / 12.0 + (h - tf) * tw ** 3 / 12.0
    z_bot = ixx / ybar
    z_top = ixx / (h - ybar)
    j = (bf * tf ** 3 + (h - tf) * tw ** 3) / 3.0     # thin-walled open J
    return {
        "shape": "tee",
        "area_mm2": a,
        "centroid": {"x_mm": bf / 2.0, "y_mm": ybar},
        "ixx_mm4": ixx, "iyy_mm4": iyy, "ixy_mm4": 0.0,
        "rx_mm": math.sqrt(ixx / a), "ry_mm": math.sqrt(iyy / a),
        "zxx_bottom_mm3": z_bot, "zxx_top_mm3": z_top,
        "zxx_mm3": min(z_bot, z_top),
        "zyy_mm3": iyy / (bf / 2.0),
        "sxx_mm3": None, "syy_mm3": None,             # asymmetric → SP only
        "j_mm4": j,
    }


def _channel_result(h: float, bf: float, tf: float, tw: float) -> Dict[str, Any]:
    """Channel section: symmetric about depth axis (strong x), asymmetric
    about the y axis (centroid shifts toward the web)."""
    hw = max(h - 2 * tf, 0.0)
    a = 2 * bf * tf + hw * tw
    ixx = (bf * h ** 3 - (bf - tw) * hw ** 3) / 12.0
    # First moments about the left edge → locate x centroid.
    sx_left = 2 * (bf * tf * bf / 2.0) + hw * tw * tw / 2.0
    xbar = sx_left / a
    iyy_left = 2 * (tf * bf ** 3 / 12.0 + bf * tf * (bf / 2.0) ** 2)
    iyy_left += hw * tw ** 3 / 12.0 + hw * tw * (tw / 2.0) ** 2
    iyy = iyy_left - a * xbar ** 2
    sxx = bf * tf * (h - tf) + tw * hw ** 2 / 4.0     # plastic strong axis
    j = (2 * bf * tf ** 3 + hw * tw ** 3) / 3.0
    return {
        "shape": "channel",
        "area_mm2": a,
        "centroid": {"x_mm": xbar, "y_mm": h / 2.0},
        "ixx_mm4": ixx, "iyy_mm4": iyy, "ixy_mm4": 0.0,
        "rx_mm": math.sqrt(ixx / a), "ry_mm": math.sqrt(iyy / a),
        "zxx_mm3": ixx / (h / 2.0),
        "zyy_left_mm3": iyy / xbar, "zyy_right_mm3": iyy / (bf - xbar),
        "zyy_mm3": min(iyy / xbar, iyy / (bf - xbar)),
        "sxx_mm3": sxx, "syy_mm3": None,
        "j_mm4": j,
    }
# Required dimensions (mm) per shape, for validation + sp-library mapping.
_SHAPE_DIMS = {
    "rect": ("b", "d"),
    "circle": ("d",),
    "i": ("h", "bf", "tf", "tw"),
    "tee": ("h", "bf", "tf", "tw"),
    "channel": ("h", "bf", "tf", "tw"),
}


def _normalize_section(section: Dict[str, Any]) -> "tuple[str, Dict[str, float]]":
    """Validate a section definition and return (shape, dims-as-floats)."""
    if not isinstance(section, dict):
        raise SectionDesignError("Section must be a JSON object.")
    shape = str(section.get("shape", "")).strip().lower()
    if shape not in SUPPORTED_SHAPES:
        raise SectionDesignError(
            f"Unsupported shape '{shape or '?'}'. Supported: {', '.join(SUPPORTED_SHAPES)}")
    dims: Dict[str, float] = {}
    for key in _SHAPE_DIMS[shape]:
        try:
            val = float(section[key])
        except (KeyError, TypeError, ValueError):
            raise SectionDesignError(f"Shape '{shape}' requires numeric dimension '{key}'.") from None
        if not (val > 0) or not math.isfinite(val):
            raise SectionDesignError(
                f"Dimension '{key}' must be a positive finite number (got {section[key]!r}).")
        dims[key] = val
    return shape, dims


_ANALYTIC: Dict[str, Any] = {
    "rect": lambda p: _rect_result(p["b"], p["d"]),
    "circle": lambda p: _circle_result(p["d"]),
    "i": lambda p: _i_result(p["h"], p["bf"], p["tf"], p["tw"]),
    "tee": lambda p: _tee_result(p["h"], p["bf"], p["tf"], p["tw"]),
    "channel": lambda p: _channel_result(p["h"], p["bf"], p["tf"], p["tw"]),
}


def _register_sp_builders() -> None:
    """Populate the optional sectionproperties->shape map (only when the
    heavy lib is importable; keeps module import side-effect free)."""
    if not SECTIONPROPERTIES_AVAILABLE:
        return
    try:
        lib = _SP_LIB
        _SP_BUILDERS.update({
            "rect": lambda p: lib.rectangular_section(d=p["d"], b=p["b"]),
            "circle": lambda p: lib.circular_section(d=p["d"]),
            "i": lambda p: lib.i_section(d=p["h"], b=p["bf"], t_f=p["tf"], t_w=p["tw"]),
            "tee": lambda p: lib.tee_section(d=p["h"], b=p["bf"], t_f=p["tf"], t_w=p["tw"]),
            "channel": lambda p: lib.channel_section(d=p["h"], b=p["bf"], t_f=p["tf"], t_w=p["tw"]),
        })
    except Exception as exc:  # pragma: no cover - noisy signed wheel edge cases
        log.warning("Could not register sectionproperties builders: %s", exc)


_register_sp_builders()


def _mesh(geometry: Any, mesh_size: float) -> Any:
    """Create a mesh on a sectionproperties geometry, tolerating v1/v2/v3
    keyword differences (mesh_size vs mesh_sizes)."""
    try:
        geometry.create_mesh(mesh_sizes=[mesh_size])
    except Exception:
        geometry.create_mesh(mesh_size=mesh_size)
    return geometry


class SectionDesigner:
    """Compute cross-section properties for structural shapes.

    Uses ``sectionproperties`` when installed (accurate, incl. complex
    shapes), otherwise exact closed-form formulas for the five standard
    shapes. Every ``analyze`` call returns a flat, JSON-friendly dict.
    """

    name = "section-designer"

    def analyze(self, section: Dict[str, Any],
                mesh_size: float = 5.0,
                force_analytic: bool = False) -> Dict[str, Any]:
        """Return geometric + plastic section properties.

        ``force_analytic=True`` bypasses sectionproperties (useful for tests
        and deterministic CI). Raises :class:`SectionDesignError` on bad input.
        """
        shape, dims = _normalize_section(section)
        if (not force_analytic and SECTIONPROPERTIES_AVAILABLE
                and _shape_builder(shape) is not None):
            try:
                result = _analyze_with_sp(shape, dims, mesh_size)
                result["solver"] = "sectionproperties"
                return result
            except Exception as exc:  # noqa: BLE001 - bridge must never 5xx
                log.warning("sectionproperties failed for %s (%s); analytic fallback.",
                            shape, exc)
        result = dict(_ANALYTIC[shape](dims))
        result["solver"] = "analytic"
        return result

    # -- material enrichment -------------------------------------------------
    def capacities(self, properties: Dict[str, Any],
                   material: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Preliminary member capacities from section properties.

        Uses code-agnostic first-yield / full-plastic mechanics (the actual
        code clauses arrive with structuralcodes in Sprint 9):
          N_pl   = A · fy            (plastic axial capacity)
          M_el   = Z_el · fy         (elastic moment capacity)
          M_pl   = S_pl · fy         (plastic moment capacity)
        """
        mat = material or {"e_mpa": 210_000.0, "fy": 355.0, "density": 7850.0}
        e = float(mat.get("e_mpa", 210_000.0))
        fy = float(mat.get("fy", 355.0))
        density = float(mat.get("density", 7850.0))
        a = properties.get("area_mm2", 0.0)
        weight_per_m = a * 1e-6 * density
        caps = {
            "material": {
                "e_mpa": e, "fy": fy, "density_kg_m3": density,
            },
            "weight_kg_per_m": round(weight_per_m, 3),
            "n_pl_kN": round(a * fy / 1000.0, 1),
        }
        zxx = properties.get("zxx_mm3")
        if zxx:
            caps["m_el_kNm"] = round(zxx * fy / 1e6, 2)
            caps["ei_kn_m2"] = round(e * properties.get("ixx_mm4", 0.0) / 1e9, 1)
        sxx = properties.get("sxx_mm3")
        if sxx:
            caps["m_pl_kNm"] = round(sxx * fy / 1e6, 2)
        return caps


def _analyze_with_sp(shape: str, dims: Dict[str, float], mesh_size: float) -> Dict[str, Any]:
    """Bridge a shape+dims into a sectionproperties run, mapping its result
    surface onto the shared schema (mm-based units)."""
    builder = _shape_builder(shape)
    if builder is None:
        raise SectionDesignError(
            f"'{shape}' is not bridged to sectionproperties in this environment.")
    geometry = builder(dims)
    geom = _mesh(geometry, mesh_size)
    sec = _SP_Section(geom)
    sec.calculate_geometric_properties()
    sec.calculate_plastic_properties()
    torsion = None
    try:
        sec.calculate_torsion_properties()
        torsion = float(sec.get_torsion_props()[0])
    except Exception:  # pragma: no cover - torsion not defined for some comps
        torsion = None

    cx, cy = sec.get_centroids()
    ixx, iyy, ixy = sec.get_second_moments()
    rx, ry = sec.get_radii_of_gyration()
    zxx, zyy, zxy = sec.get_section_moduli()
    plastic = (None, None)
    try:
        plastic = sec.get_plastic_section_moduli()
    except Exception:  # pragma: no cover
        plastic = (None, None)

    result: Dict[str, Any] = {
        "shape": shape,
        "area_mm2": float(sec.get_area()),
        "centroid": {"x_mm": float(cx), "y_mm": float(cy)},
        "ixx_mm4": float(ixx), "iyy_mm4": float(iyy), "ixy_mm4": float(ixy),
        "rx_mm": float(rx), "ry_mm": float(ry),
        "zxx_mm3": float(zxx), "zyy_mm3": float(zyy),
        "sxx_mm3": (float(plastic[0]) if plastic[0] is not None else None),
        "syy_mm3": (float(plastic[1]) if plastic[1] is not None else None),
        "j_mm4": torsion,
    }
    if hasattr(sec, "get_perimeter"):
        try:
            result["perimeter_mm"] = float(sec.get_perimeter())
        except Exception:  # pragma: no cover
            pass
    return result
