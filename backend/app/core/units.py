"""Lightweight unit helpers built on Pint (optional dependency).

Wraps conversion so engineering services can be explicit about unit
transformations (e.g. kN to N, kN·m to N·mm) while keeping calculations
clear and testable. Degrades to pass-through when Pint is not installed,
so the API and test suite keep working in a lean environment.
"""
from __future__ import annotations

from typing import Optional, Union

try:
    from pint import UnitRegistry

    _UREG = UnitRegistry(autoconvert_offset_to_baseunit=True)
    PINT_AVAILABLE = True
except Exception:  # pragma: no cover - Pint is optional
    _UREG = None
    PINT_AVAILABLE = False


def convert(
    value: Optional[Union[int, float]], source: str, target: str
) -> Optional[float]:
    """Convert a scalar between Pint-compatible unit strings.

    Returns None for a None input; passes the value through unchanged when
    Pint is not available or the unit expression fails to parse (never raises).
    """
    if value is None:
        return None
    if not PINT_AVAILABLE:
        return float(value)
    try:
        return float(_UREG.Quantity(float(value), source).to(target).magnitude)
    except Exception:  # pragma: no cover - defensive
        return float(value)


def plausible_kpa(value: Optional[float], low: float = 50.0, high: float = 500.0) -> bool:
    """Return True when a soil-bearing reading sits in the plausible band."""
    return value is None or low <= float(value) <= high