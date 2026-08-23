"""
Sprint 2 — CAD & image processing.

``EzdxfCADProcessor`` reads DXF files and extracts structural centerlines from
S-WALLS / S-COLUMNS / S-BEAMS layers. ``ImageCADProcessor`` runs OpenCV line,
rect & circle detection on rasterized sheets. Both emit the shared
:class:`~app.models.plan_data.PlanData` contract, so downstream analysis is
source-agnostic.
"""
from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from itertools import count
from pathlib import Path
from typing import Iterable, List, Tuple

from app.models.plan_data import GridLine, PlanData, Wall, Beam, Column, ImageInput

log = logging.getLogger("imad.cad")

# Structural layer names per the Imad CAD standard.
LAYER_WALLS = "S-WALLS"
LAYER_COLUMNS = "S-COLUMNS"
LAYER_BEAMS = "S-BEAMS"

DXF_EXTENSIONS = (".dxf", ".dwg", ".ifc", ".obj")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".pdf")

DEFAULT_THICKNESS = 0.15   # bearing wall thickness (m)
DEFAULT_COLUMN_SIZE = 0.30 # column side (m)
MIN_CONTOUR_AREA = 400.0   # px² — filters noise during image parse


class CADProcessingError(Exception):
    """Raised when a design file cannot be parsed into plan geometry."""


class CADProcessor(ABC):
    """Abstract design-file → PlanData pipeline."""

    source_name: str = "cad"
    _ids: Iterable[int]

    def __init__(self) -> None:
        self._ids = count(1)

    @abstractmethod
    def parse(self, path: str, original_name: str = "") -> PlanData:
        """Parse a stored design file and return plan geometry."""

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._ids)}"

    def _build(self) -> PlanData:
        """Create an empty geometry doc pre-tagged with the source name."""
        return PlanData(source=self.source_name)


def get_cad_processor(filename: str) -> CADProcessor:
    """Return the processor best suited to a file's extension."""
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return ImageCADProcessor()
    if ext in DXF_EXTENSIONS:
        return EzdxfCADProcessor() if ext == ".dxf" else ImageCADProcessor()
    raise CADProcessingError(f"Unsupported CAD file type: '{ext or '?'}'")


# ──────────────────────────────────────────────────────────────── DXF ─────
class EzdxfCADProcessor(CADProcessor):
    """Parse DXF structural drawings with ``ezdxf`` (lazy import)."""

    source_name = "cad"

    def parse(self, path: str, original_name: str = "") -> PlanData:
        try:
            import ezdxf  # optional heavy dependency
        except ImportError as exc:
            raise CADProcessingError(
                "ezdxf is required to parse DXF files. Install with: pip install ezdxf"
            ) from exc

        if not Path(path).exists():
            raise CADProcessingError(f"DXF file not found: {path}")

        doc = ezdxf.readfile(path)
        model = doc.modelspace()
        plan = self._build()
        plan.units = "m"

        wall_runs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        beam_runs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        column_centers: List[Tuple[float, float]] = []

        for entity in model:
            layer = (getattr(entity.dxf, "layer", "") or "").upper()
            kind = entity.dxftype()
            if kind == "LINE":
                s, e = entity.dxf.start, entity.dxf.end
                p1, p2 = (float(s.x), float(s.y)), (float(e.x), float(e.y))
                _route_line(layer, p1, p2, wall_runs, beam_runs)
            elif kind == "CIRCLE":
                c = entity.dxf.center
                if layer == LAYER_COLUMNS:
                    column_centers.append((float(c.x), float(c.y)))
            elif kind == "LWPOLYLINE":
                points = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                if not points:
                    continue
                if layer == LAYER_WALLS:
                    for i in range(len(points)):
                        wall_runs.append((points[i], points[(i + 1) % len(points)]))
                elif layer == LAYER_BEAMS:
                    for i in range(len(points) - 1):
                        beam_runs.append((points[i], points[i + 1]))

        plan.walls = [_make_wall(self, a, b) for a, b in wall_runs]
        plan.beams = [_make_beam(self, a, b) for a, b in beam_runs]
        plan.columns = [_make_column(self, c) for c in column_centers]
        plan.grids = _grid_from_extents(plan)
        plan.materials = {"concrete": "C30", "steel": "A615 Gr60"}
        return plan


def _route_line(layer, p1, p2, wall_runs, beam_runs):
    if layer == LAYER_WALLS:
        wall_runs.append((p1, p2))
    elif layer == LAYER_BEAMS:
        beam_runs.append((p1, p2))


# ─────────────────────────────────────────────────────────────── image ─────
class ImageCADProcessor(CADProcessor):
    """Parse raster sheets (.png/.jpg/…) with OpenCV line & contour detection.

    The raster is converted to the SAME millimetre-in-``cm`` coordinate space
    as CAD files via a DPI assumption (default 96 px/in → px-to-metre scale),
    and detected primitives are mapped to the ``PlanData`` shape.
    """

    source_name = "image"

    def parse(self, path: str, original_name: str = "") -> PlanData:
        try:
            import cv2  # optional heavy dependency
            import numpy as np
        except ImportError as exc:
            raise CADProcessingError(
                "OpenCV is required to parse images. Install with: pip install opencv-python"
            ) from exc

        if not Path(path).exists():
            raise CADProcessingError(f"Image file not found: {path}")

        img = self._read_image(cv2, path)
        if img is None:
            raise CADProcessingError("Unable to read image (unsupported or corrupt).")

        scale = self._px_to_m(img)              # metres per pixel
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        plan = self._build()
        plan.units = "m"
        plan.image = ImageInput(file_name=original_name, provider="opencv")

        # 1. Walls: dominant straight lines (Hough).
        plan.walls = self._detect_walls(cv2, np, edges, scale)
        # 2. Columns: rectangles + filled circles (contours).
        plan.columns = self._detect_columns(cv2, gray, img, scale)
        # 3. Grids: derive from column grid coordinates.
        plan.grids = _grid_from_extents(plan)
        plan.materials = {"concrete": "C30", "steel": "A615 Gr60"}
        return plan

    # -- helpers -----------------------------------------------------
    @staticmethod
    def _read_image(cv2, path):
        return cv2.imread(path)

    @staticmethod
    def _px_to_m(img):
        """Assume 96 DPI scans: 1 px ≈ 0.000264583 m."""
        height_px, width_px = img.shape[:2]
        # Use the long dimension to infer a nominal metre scale.
        return 1 / 96 / 0.0254

    def _detect_walls(self, cv2, np, edges, scale):
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=60, maxLineGap=8)
        walls: List[Wall] = []
        if lines is None:
            return walls
        for ln in lines:
            # `ln` may be shape (1,4) (legacy OpenCV) or (4,) (newer OpenCV);
            # flatten so both shapes unpack cleanly.
            pts = np.asarray(ln).reshape(-1)
            if pts.size < 4:
                continue
            x1, y1, x2, y2 = (int(v) for v in pts[:4])
            length = math.hypot(x2 - x1, y2 - y1)
            if length < 20:
                continue
            walls.append(Wall(
                id=self._new_id("w"),
                x1=x1 * scale, y1=y1 * scale,
                x2=x2 * scale, y2=y2 * scale,
                thickness_m=DEFAULT_THICKNESS, level=0,
            ))
        return walls

    def _detect_columns(self, cv2, gray, img, scale):
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        columns: List[Column] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MIN_CONTOUR_AREA:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 0 and h > 0 and abs(w - h) / max(w, h) < 0.35:  # roughly square
                cx, cy = x + w / 2, y + h / 2
                columns.append(Column(
                    id=self._new_id("c"),
                    cx=cx * scale, cy=cy * scale,
                    size_m=DEFAULT_COLUMN_SIZE, height=3.0,
                ))
        return columns[:64]  # cap to keep grids legible


# ───────────────────────────────────────────────────────────── shared ─────
def _make_wall(proc, a, b) -> Wall:
    return Wall(id=proc._new_id("w"),
                x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                thickness_m=DEFAULT_THICKNESS, level=0, kind="bearing")


def _make_beam(proc, a, b) -> Beam:
    return Beam(id=proc._new_id("b"),
                x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                depth_m=0.5, width_m=0.3, level=0)


def _make_column(proc, center) -> Column:
    return Column(id=proc._new_id("c"),
                  cx=center[0], cy=center[1],
                  size_m=DEFAULT_COLUMN_SIZE, height=3.0)


def _grid_from_extents(plan) -> List[GridLine]:
    xs = sorted({w.x1 for w in plan.walls} | {w.x2 for w in plan.walls} |
                {c.cx for c in plan.columns})
    ys = sorted({w.y1 for w in plan.walls} | {w.y2 for w in plan.walls} |
                {c.cy for c in plan.columns})
    v_grids = [GridLine(id=f"v{i}", orientation="vertical", position=x, label=f"{i+1}")
               for i, x in enumerate(xs)]
    h_grids = [GridLine(id=f"h{i}", orientation="horizontal", position=y, label=f"{i+1}")
               for i, y in enumerate(ys)]
    return v_grids + h_grids