"""
Sprint 12 — BIM interoperability: IFC export/import + BCF-style issue tracking.

``export_ifc`` authors a real IFC4 STEP (.ifc) file from a :class:`PlanData`
model using a compact built-in SPF writer — columns/beams/walls/slabs with
extruded-rectangle geometry and the full spatial hierarchy
(IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey), so the output opens
in BIM viewers. If ``ifcopenshell`` is installed it is used for *import* to
extract structural elements back into PlanData; export never requires it.

BCF issues are tracked as JSON documents (the "custom JSON" option allowed by
the sprint spec) via the shared document store.
"""
from __future__ import annotations

import base64
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData

log = logging.getLogger("imad.bim")


class BIMError(Exception):
    """Raised when an IFC operation cannot be completed."""


def _guid() -> str:
    """IFC GlobalId: 16 random bytes → Base64 minus padding = 22 chars."""
    return base64.b64encode(uuid.uuid4().bytes).decode()[:22]


class _Ref:
    """Marks an integer as an entity reference (#n) inside _SpfWriter.add."""

    __slots__ = ("n",)

    def __init__(self, n: int) -> None:
        self.n = n


class _SpfWriter:
    """Incremental IFC-SPF builder: assigns #ids and formats entities."""

    def __init__(self) -> None:
        self._lines: List[str] = []
        self._n = 0

    def ref(self, n: int) -> _Ref:
        return _Ref(n)

    def add(self, entity: str, *args: Any) -> int:
        """Append one entity; ``_Ref`` args render as #n, tuples as enumerations."""
        self._n += 1
        rendered = []
        for a in args:
            if isinstance(a, _Ref):
                rendered.append(f"#{a.n}")
            elif a is None:
                rendered.append("$")
            elif isinstance(a, tuple):
                inner = ",".join(
                    f"#{x.n}" if isinstance(x, _Ref) else
                    ("$" if x is None else
                     (f"{x:.4f}" if isinstance(x, float) else str(x)))
                    for x in a)
                rendered.append(f"({inner})")
            elif isinstance(a, float):
                rendered.append(f"{a:.4f}")
            else:
                rendered.append(f"'{a}'")
        self._lines.append(
            f"#{self._n}= {entity.upper()}({','.join(rendered)});")
        return self._n

    def render(self, file_name: str) -> str:
        header = (
            "ISO-10303-21;\nHEADER;\n"
            "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');\n"
            f"FILE_NAME('{file_name}','{datetime.now(timezone.utc).isoformat()}',"
            "('Imad'),('Imad Engineering'),'Imad IFC Writer','Imad','');\n"
            "FILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n")
        return header + "\n".join(self._lines) + "\nENDSEC;\nEND-ISO-10303-21;\n"


# ────────────────────────────────────────────────────────────── IFC export ────
def _placement(w: "_SpfWriter", origin=(0.0, 0.0, 0.0)) -> int:
    pos = w.add("IFCCARTESIANPOINT", tuple(origin))
    axis = w.add("IFCAXIS2PLACEMENT3D", w.ref(pos))
    return w.add("IFCLOCALPLACEMENT", None, w.ref(axis))


def export_ifc(plan: PlanData, project_name: str = "Imad Project") -> bytes:
    """Author a minimal but valid IFC4 file from a structural plan.

    Hierarchy: IfcProject → IfcSite → IfcBuilding → one IfcBuildingStorey per
    level. Columns/beams/walls/slabs become prismatic extrusions placed on
    their storey — enough for coordination viewers to show a correct massing.
    """
    w = _SpfWriter()
    story_h = float(getattr(plan, "story_height_m", 3.0) or 3.0)
    stories = max(1, int(getattr(plan, "stories", 1)))

    origin2d = w.add("IFCCARTESIANPOINT", (0., 0.))
    ax2d = w.add("IFCAXIS2PLACEMENT2D", w.ref(origin2d))
    origin3d = w.add("IFCCARTESIANPOINT", (0., 0., 0.))
    z_dir = w.add("IFCDIRECTION", (0., 0., 1.))
    ctx = w.add("IFCGEOMETRICREPRESENTATIONCONTEXT", None, "Model", None,
                w.ref(w.add("IFCAXIS2PLACEMENT3D", w.ref(origin3d))),
                w.ref(z_dir))
    unit_len = w.add("IFCSIUNIT", "LENGTHUNIT", None, "METRE")
    unit_area = w.add("IFCSIUNIT", "AREAUNIT", None, "SQUARE_METRE")
    unit_vol = w.add("IFCSIUNIT", "VOLUMEUNIT", None, "CUBIC_METRE")
    _ = (unit_area, unit_vol)
    project = w.add("IFCPROJECT", _guid(), _guid(), None, "Imad export",
                    None, None, (), w.ref(ctx), w.ref(unit_len))
    _ = project

    site_placement = _placement(w)
    site = w.add("IFCSITE", _guid(), _guid(), None, None, "Site", None, None,
                 (), w.ref(site_placement), None, None, 0., (), ())
    building = w.add("IFCBUILDING", _guid(), _guid(), None, None,
                     project_name[:40], None, None, (),
                     w.ref(site_placement), None, None, (), ())
    return _emit_elements(w, ctx, site, building, plan, stories, story_h)


def _emit_elements(w, ctx: int, site: int, building: int,
                   plan: PlanData, stories: int, story_h: float) -> bytes:
    """Emit per-storey structural elements; finalises and returns SPF bytes."""
    b = plan.bounds()
    width_x = max(b["max_x"] - b["min_x"], 1.0)
    width_y = max(b["max_y"] - b["min_y"], 1.0)

    def shape_of(sx: float, sy: float, sz: float) -> int:
        """Extruded rectangle profile → swept solid → shape representation."""
        ax2d = w.add("IFCAXIS2PLACEMENT2D",
                     w.ref(w.add("IFCCARTESIANPOINT", (0., 0.))))
        profile = w.add("IFCRECTANGLEPROFILEDEF", "AREA", None,
                        w.ref(ax2d), sx, sy)
        base = w.add("IFCCARTESIANPOINT", (0., 0., 0.))
        z_dir = w.add("IFCDIRECTION", (0., 0., 1.))
        ax3 = w.add("IFCAXIS2PLACEMENT3D", w.ref(base), None, w.ref(z_dir))
        body = w.add("IFCEXTRUDEDAREASOLID", w.ref(profile), w.ref(ax3),
                     w.ref(z_dir), sz)
        return w.add("IFCSHAPEREPRESENTATION", w.ref(ctx), "Body",
                     "SweptSolid", (w.ref(body),))

    def element(kind: str, name: str, x: float, y: float, z: float,
                shape_ref: int) -> None:
        plcm = _placement(w, (x, y, z))
        w.add(kind, _guid(), _guid(), None, None, name[:40], None, None, (),
              w.ref(plcm), w.ref(shape_ref), None)

    for level in range(stories):
        z = level * story_h
        st_plcm = _placement(w, (0.0, 0.0, z))
        storey = w.add("IFCBUILDINGSTOREY", _guid(), _guid(), None, None,
                       f"Storey {level + 1}", None, None, (),
                       w.ref(st_plcm), None, None, (), ())
        # Aggregation: site → building → storey keeps viewers happy.
        w.add("IFCRELAGGREGATES", _guid(), _guid(), None, None, (),
              w.ref(building), (w.ref(storey),))
        if level == 0:
            w.add("IFCRELAGGREGATES", _guid(), _guid(), None, None, (),
                  w.ref(site), (w.ref(building),))

        for col in plan.columns:
            s = col.size_m
            element("IFCCOLUMN", f"COL {col.id}", col.cx - s / 2, col.cy - s / 2,
                    z, shape_of(s, s, story_h))

        for beam in plan.beams:
            length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
            if length < 0.2:
                continue
            horizontal = abs(beam.y2 - beam.y1) < 1e-6
            sx = length if horizontal else beam.width_m
            sy = beam.width_m if horizontal else length
            bx = min(beam.x1, beam.x2) - (sy / 2 if not horizontal else 0.0)
            by = min(beam.y1, beam.y2) - (sx / 2 if horizontal else 0.0)
            element("IFCBEAM", f"BEAM {beam.id}", bx, by,
                    z + story_h - beam.depth_m, shape_of(sx, sy, beam.depth_m))

        for wall in getattr(plan, "walls", []) or []:
            wl = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
            if wl < 0.2:
                continue
            horizontal = abs(wall.y2 - wall.y1) < 1e-6
            sx = wl if horizontal else wall.thickness_m
            sy = wall.thickness_m if horizontal else wl
            wx = min(wall.x1, wall.x2)
            wy = min(wall.y1, wall.y2)
            element("IFCWALL", f"WALL {wall.id}", wx, wy, z,
                    shape_of(sx, sy, story_h * 0.98))

        element("IFCSLAB", f"SLAB L{level + 1}", b["min_x"], b["min_y"], z,
                shape_of(width_x, width_y, 0.18))

    log.info("Authored IFC4 export: %d entities", w._n)
    return w.render(f"{plan.source or 'imad'}-{stories}st.ifc").encode("utf-8")


def export_ifc_file(plan: PlanData, out_path=None,
                    project_name: str = "Imad Project") -> str:
    """Write the IFC export next to other generated documents."""
    from .exporters import exports_dir

    path = Path(out_path) if out_path else (
        exports_dir() / f"{project_name.replace(' ', '-').lower()}"
                        f"-{datetime.now(timezone.utc):%Y%m%d%H%M%S}.ifc")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(export_ifc(plan, project_name))
    return str(path)


# ────────────────────────────────────────────────────────────── IFC import ────
def import_ifc(file_path: str) -> PlanData:
    """Extract structural elements from an IFC file back into PlanData.

    Prefers ``ifcopenshell`` (robust IFC2x3/IFC4 parsing); falls back to a
    lightweight regex scan of the SPF payload for simple exports — including
    our own writer — so the feature degrades gracefully without the dependency.
    """
    path = Path(file_path)
    if not path.exists():
        raise BIMError(f"IFC file not found: {file_path}")

    try:
        import ifcopenshell  # type: ignore
    except ImportError:
        log.info("ifcopenshell not installed — using lightweight SPF scan.")
        return _import_with_regex(path.read_text(encoding="utf-8", errors="ignore"))

    try:
        return _import_with_ifcopenshell(ifcopenshell.open(str(path)))
    except Exception as exc:  # noqa: BLE001 — surfaced as 4xx at the API layer
        raise BIMError(f"IFC import failed: {exc}") from exc


def _import_with_ifcopenshell(model: Any) -> PlanData:
    """Map IFC product entities onto the PlanData contract."""
    columns: List[Dict[str, Any]] = []
    beams: List[Dict[str, Any]] = []
    walls: List[Dict[str, Any]] = []
    storeys = len(model.by_type("IfcBuildingStorey")) or 1

    def origin(product: Any) -> tuple:
        try:
            coords = product.ObjectPlacement.RelativePlacement.Location.Coordinates
            x = float(coords[0]); y = float(coords[1])
            z = float(coords[2]) if len(coords) > 2 else 0.0
            return x, y, z
        except Exception:  # noqa: BLE001 — placement quirks default to origin
            return 0.0, 0.0, 0.0

    for prod in model.by_type("IfcColumn"):
        x, y, z = origin(prod)
        columns.append({"id": (prod.Name or f"C{len(columns) + 1}"),
                        "cx": round(x + 0.15, 3), "cy": round(y + 0.15, 3),
                        "size_m": 0.3, "height": 3.0,
                        "level": max(0, int(round(z / 3.0)))})
    for prod in model.by_type("IfcBeam"):
        x, y, z = origin(prod)
        beams.append({"id": (prod.Name or f"B{len(beams) + 1}"),
                      "x1": round(x, 3), "y1": round(y, 3),
                      "x2": round(x + 6.0, 3), "y2": round(y, 3),
                      "width_m": 0.3, "depth_m": 0.5,
                      "level": max(0, int(round(z / 3.0)))})
    for prod in model.by_type("IfcWall"):
        x, y, z = origin(prod)
        walls.append({"id": (prod.Name or f"W{len(walls) + 1}"),
                      "x1": round(x, 3), "y1": round(y, 3),
                      "x2": round(x + 5.0, 3), "y2": round(y, 3),
                      "thickness_m": 0.2, "level": max(0, int(round(z / 3.0))),
                      "kind": "bearing"})

    if not (columns or beams or walls):
        raise BIMError("No structural elements found in the IFC file.")
    return PlanData(source="ifc", walls=walls, columns=columns, beams=beams,
                    stories=max(storeys, 1), label="Imported IFC")


def _import_with_regex(text: str) -> PlanData:
    """Parse IfcColumn/IfcBeam/IfcWall entities from raw SPF text.

    Handles the attribute layout our writer emits (and most simple exports):
    resolves placement origins, profile dimensions and storey counts.
    """
    columns: List[Dict[str, Any]] = []
    beams: List[Dict[str, Any]] = []
    walls: List[Dict[str, Any]] = []

    storey_names = re.findall(
        r"IFCBUILDINGSTOREY\([^,]*,[^,]*,[^,]*,[^,]*,'([^']*)'", text)
    storeys = max(len(storey_names), 1)

    origins: Dict[int, tuple] = {}
    placements: Dict[int, int] = {}
    for m in re.finditer(
            r"#(\d+)= ?IFCCARTESIANPOINT\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)"
            r"\s*(?:,\s*([-\d.eE+]+)\s*)?\)", text):
        z = float(m.group(4)) if m.group(4) else 0.0
        origins[int(m.group(1))] = (float(m.group(2)), float(m.group(3)), z)
    for m in re.finditer(r"#(\d+)= ?IFCLOCALPLACEMENT\([^,]*,\s*#(\d+)\s*\)", text):
        placements[int(m.group(1))] = int(m.group(2))

    profiles: Dict[int, tuple] = {}
    solids: Dict[int, tuple] = {}
    shapes: Dict[int, int] = {}
    for m in re.finditer(
            r"#(\d+)= ?IFCRECTANGLEPROFILEDEF\([^,]*,[^,]*,[^,]*,"
            r"\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)", text):
        profiles[int(m.group(1))] = (abs(float(m.group(2))), abs(float(m.group(3))))
    for m in re.finditer(
            r"#(\d+)= ?IFCEXTRUDEDAREASOLID\(\s*#(\d+)\s*,[^,]*,[^,]*,"
            r"\s*([-\d.eE+]+)\s*\)", text):
        prof = profiles.get(int(m.group(2)))
        if prof:
            solids[int(m.group(1))] = (prof[0], prof[1], abs(float(m.group(3))))
    for m in re.finditer(
            r"#(\d+)= ?IFCSHAPEREPRESENTATION\([^,]*,'Body','SweptSolid',"
            r"\(\s*#(\d+)\s*\)\)", text):
        if int(m.group(2)) in solids:
            shapes[int(m.group(1))] = int(m.group(2))

    def origin_of(attr: str) -> tuple:
        if attr.startswith("#"):
            axis = placements.get(int(attr.lstrip("#")))
            if axis is not None:
                return origins.get(axis, (0.0, 0.0, 0.0))
        return 0.0, 0.0, 0.0

    def dims_of(attrs: List[str]) -> tuple:
        for a in attrs:
            if a.startswith("#") and int(a.lstrip("#")) in shapes:
                return solids.get(shapes[int(a.lstrip("#"))], (0.3, 0.3, 3.0))
        return (0.3, 0.3, 3.0)

    n_slabs = len(re.findall(r"#\d+= ?IFCSLAB\(", text))
    spec = (("IFCCOLUMN", columns, _col_from),
            ("IFCBEAM", beams, _beam_from),
            ("IFCWALL", walls, _wall_from))
    for kind, bucket, fn in spec:
        for m in re.finditer(rf"#\d+= ?{kind}\(([^)]*)\)", text):
            attrs = [a.strip() for a in m.group(1).split(",")]
            item = fn(attrs, origin_of, dims_of)
            if item:
                bucket.append(item)

    if not (columns or beams or walls):
        raise BIMError("No structural elements found in the IFC file.")
    return PlanData(source="ifc", walls=walls, columns=columns, beams=beams,
                    stories=storeys, label=f"Imported IFC ({n_slabs} slabs)")


def _col_from(attrs, origin_of, dims_of):
    name = attrs[4].strip("'") if len(attrs) > 4 else "COL"
    x, y, _z = origin_of(attrs[8]) if len(attrs) > 8 else (0, 0, 0)
    sx, sy, sz = dims_of(attrs[9:10])
    return {"id": name, "cx": round(x + sx / 2, 3), "cy": round(y + sy / 2, 3),
            "size_m": round((sx + sy) / 2, 3), "height": sz or 3.0, "level": 0}


def _beam_from(attrs, origin_of, dims_of):
    name = attrs[4].strip("'") if len(attrs) > 4 else "BEAM"
    x, y, _z = origin_of(attrs[8]) if len(attrs) > 8 else (0, 0, 0)
    sx, sy, sz = dims_of(attrs[9:10])
    return {"id": name, "x1": round(x, 3), "y1": round(y + sy / 2, 3),
            "x2": round(x + sx, 3), "y2": round(y + sy / 2, 3),
            "width_m": round(sy, 3), "depth_m": round(sz, 3), "level": 0}


def _wall_from(attrs, origin_of, dims_of):
    name = attrs[4].strip("'") if len(attrs) > 4 else "WALL"
    x, y, _z = origin_of(attrs[8]) if len(attrs) > 8 else (0, 0, 0)
    sx, sy, _sz = dims_of(attrs[9:10])
    return {"id": name, "x1": round(x, 3), "y1": round(y, 3),
            "x2": round(x + sx, 3), "y2": round(y, 3),
            "thickness_m": round(sy, 3), "level": 0, "kind": "bearing"}


# ───────────────────────────────────────── BCF-style issue tracking (JSON) ────
def create_issue(project_id: int, title: str, body: str = "",
                 author: str = "", element_ref: str = "",
                 position: Optional[List[float]] = None) -> Dict[str, Any]:
    """Register a BCF-style coordination issue (custom-JSON option)."""
    from app.core.docstore import collection

    issue = {
        "project_id": project_id,
        "title": title,
        "body": body,
        "author": author,
        "element_ref": element_ref,
        "position": position or [],
        "status": "open",
        "topic_id": _guid(),
    }
    return collection("bcf_issues").put(issue, prefix="bcf")


def list_issues(project_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    from app.core.docstore import collection

    issues = collection("bcf_issues").list(
        lambda d: d.get("project_id") == project_id)
    if status:
        issues = [i for i in issues if i.get("status") == status]
    return sorted(issues, key=lambda d: d.get("created_at", ""), reverse=True)


def update_issue(issue_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    from app.core.docstore import collection

    return collection("bcf_issues").update(issue_id, **fields)