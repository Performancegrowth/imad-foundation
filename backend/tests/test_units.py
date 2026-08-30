"""Unit-handling tests (Pint-backed helpers in app/core/units.py)."""
from app.core.units import convert, plausible_kpa


def test_kilonewton_to_newton():
    assert convert(1.0, "kilonewton", "newton") == 1000.0
    assert convert(2.5, "kilonewton", "newton") == 2500.0


def test_moment_knm_to_nmm():
    # 1 kN·m = 1e6 N·mm
    assert convert(1.0, "kilonewton * meter", "newton * millimeter") == 1_000_000.0


def test_kpa_to_mpa():
    assert convert(1000.0, "kilopascal", "megapascal") == 1.0


def test_none_and_zero():
    assert convert(None, "kilonewton", "newton") is None
    assert convert(0.0, "kilonewton", "newton") == 0.0


def test_plausible_kpa():
    assert plausible_kpa(150.0)
    assert plausible_kpa(None)  # unknown is allowed (not flagged bad)
    assert not plausible_kpa(1e6)