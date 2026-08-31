"""Tests for the IFC → PlanData processor, using an injected fake
ifcopenshell so the suite runs without the heavy native dependency."""

import sys
import types

import pytest

from app.services.cad_processor import IfcCADProcessor, get_cad_processor


class _Settings:
    def set(self, *args, **kwargs):
        pass


class _BBox:
    def __init__(self, entity):
        self.min = (entity.minx, entity.miny, entity.minz)
        self.max = (entity.maxx, entity.maxy, entity.maxz)


class _Shape:
    def __init__(self, entity):
        self.entity = entity


class _Entity:
    def __init__(self, min_, max_, elevation=None, name=None):
        self.minx, self.miny, self.minz = min_
        self.maxx, self.maxy, self.maxz = max_
        self.Elevation = elevation
        self.Name = name


class _Model:
    def __init__(self):
        self._walls = [_Entity((0, 0, 0), (10, 0.3, 3))]
        self._columns = [_Entity((2, 2, 0), (2.6, 2.6, 3))]
        self._beams = [_Entity((0, 2, 3), (10, 2.3, 3.5))]
        self._storeys = [
            _Entity((0, 0, 0), (0, 0, 0), elevation=0),
            _Entity((0, 0, 0), (0, 0, 0), elevation=3),
        ]

    def by_type(self, kind):
        return {
            "IfcWall": self._walls,
            "IfcColumn": self._columns,
            "IfcBeam": self._beams,
            "IfcBuildingStorey": self._storeys,
        }[kind]


@pytest.fixture
def fake_ifc(monkeypatch):
    geom = types.ModuleType("ifcopenshell.geom")
    geom.settings = lambda: _Settings()
    geom.create_shape = lambda settings, entity: _Shape(entity)
    geom.bbox = lambda settings, shape: _BBox(shape.entity)

    mod = types.ModuleType("ifcopenshell")
    mod.geom = geom
    mod.open = lambda path: _Model()

    monkeypatch.setitem(sys.modules, "ifcopenshell", mod)
    monkeypatch.setitem(sys.modules, "ifcopenshell.geom", geom)
    return mod


def test_route_uses_ifc_processor():
    assert get_cad_processor("plan.ifc").source_name == "ifc"


def test_ifc_parse_reduces_geometry(monkeypatch, tmp_path, fake_ifc):
    p = tmp_path / "building.ifc"
    p.write_text("ISO-10303-21;\nEND-ISO-10303-21;", encoding="utf-8")

    plan = IfcCADProcessor().parse(str(p), "building.ifc")

    assert plan.source == "ifc"
    assert len(plan.walls) == 1
    w = plan.walls[0]
    assert abs(w.x1 - 0.0) < 1e-6 and abs(w.x2 - 10.0) < 1e-6
    assert abs(w.y1 - 0.15) < 1e-6          # centre-line of the 0.3 m run
    assert abs(w.thickness_m - 0.3) < 1e-3
    assert abs(w.height_m - 3.0) < 1e-3

    assert len(plan.columns) == 1
    c = plan.columns[0]
    assert abs(c.cx - 2.3) < 1e-6
    assert abs(c.cy - 2.3) < 1e-6
    assert c.level == 0

    assert len(plan.beams) == 1
    b = plan.beams[0]
    assert abs(b.depth_m - 0.5) < 1e-3      # beam minz=3 → maxz=3.5
    assert b.level == 1                     # closest storey elevation 3.0

    assert plan.stories == 2
    assert len(plan.grids) > 0  # derived from extents


class _NameEntity:
    """Entity that has a Name but no geometry (bbox returns None)."""
    def __init__(self, name):
        self.Name = name


class _NoGeomModel:
    """Fake model where _bbox returns None for every entity."""
    def __init__(self):
        self._walls = [_NameEntity("WALL_10.000_3.000_0.300")]
        self._columns = [_NameEntity("COL_0.400_0.400_0.400")]
        self._beams = [_NameEntity("BEAM_10.000_0.300_0.500")]
        self._storeys = []

    def by_type(self, kind):
        return {
            "IfcWall": self._walls,
            "IfcColumn": self._columns,
            "IfcBeam": self._beams,
            "IfcBuildingStorey": self._storeys,
        }[kind]


def test_ifc_parse_name_fallback(monkeypatch, tmp_path):
    """When geometry extraction fails, parse dimensions from entity names."""
    import types
    geom = types.ModuleType("ifcopenshell.geom")
    geom.settings = lambda: _Settings()
    geom.create_shape = lambda settings, entity: (_ for _ in ()).throw(Exception("no geom"))
    geom.bbox = lambda settings, shape: None
    mod = types.ModuleType("ifcopenshell")
    mod.geom = geom
    mod.open = lambda path: _NoGeomModel()
    monkeypatch.setitem(sys.modules, "ifcopenshell", mod)
    monkeypatch.setitem(sys.modules, "ifcopenshell.geom", geom)

    p = tmp_path / "fallback.ifc"
    p.write_text("ISO-10303-21;\nEND-ISO-10303-21;", encoding="utf-8")
    plan = IfcCADProcessor().parse(str(p), "test.ifc")

    assert len(plan.walls) == 1
    w = plan.walls[0]
    assert abs(w.x2 - 10.0) < 1e-6       # length parsed from name
    assert abs(w.height_m - 3.0) < 1e-3  # height parsed from name
    assert abs(w.thickness_m - 0.300) < 1e-3

    assert len(plan.columns) == 1
    assert plan.columns[0].size_m == 0.400

    assert len(plan.beams) == 1

    assert plan.source == "ifc"