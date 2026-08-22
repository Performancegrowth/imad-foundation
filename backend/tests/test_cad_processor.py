"""Sprint 2 — CAD & image processor tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.cad_processor import (
    CADProcessingError,
    EzdxfCADProcessor,
    ImageCADProcessor,
    get_cad_processor,
)


def _build_sample_dxf(path: Path):
    """Generate a minimal structural DXF with S-layers."""
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # One bearing wall on S-WALLS
    msp.add_line((0, 0), (12, 0), dxfattribs={"layer": "S-WALLS"})
    # Two columns as circles on S-COLUMNS
    msp.add_circle((2, 2), radius=0.15, dxfattribs={"layer": "S-COLUMNS"})
    msp.add_circle((10, 2), radius=0.15, dxfattribs={"layer": "S-COLUMNS"})
    # One beam on S-BEAMS
    msp.add_line((2, 2), (10, 2), dxfattribs={"layer": "S-BEAMS"})
    doc.saveas(path)
    return path


def test_factory_routes_by_extension():
    assert isinstance(get_cad_processor("plan.dxf"), EzdxfCADProcessor)
    assert isinstance(get_cad_processor("scan.png"), ImageCADProcessor)
    assert isinstance(get_cad_processor("scan.PDF"), ImageCADProcessor)
    with pytest.raises(CADProcessingError):
        get_cad_processor("notes.txt")


def test_dxf_extracts_structural_centerlines(tmp_path):
    pytest.importorskip("ezdxf")
    dxf = _build_sample_dxf(tmp_path / "sample.dxf")
    plan = EzdxfCADProcessor().parse(str(dxf), "sample.dxf")

    assert plan.units == "m"
    assert plan.source == "cad"
    assert len(plan.walls) == 1
    assert len(plan.columns) == 2
    assert len(plan.beams) == 1
    # wall endpoints preserved
    w = plan.walls[0]
    assert (w.x1, w.y1) == (0.0, 0.0)
    assert (w.x2, w.y2) == (12.0, 0.0)
    # material defaults applied
    assert plan.materials["concrete"] == "C30"


def test_image_processor_opens_or_reports(tmp_path):
    # Without OpenCV installed the processor must raise a helpful error,
    # never a raw ImportError.
    try:
        import cv2  # noqa: F401
    except ImportError:
        with pytest.raises(CADProcessingError, match="OpenCV"):
            ImageCADProcessor().parse(str(tmp_path / "ghost.png"), "ghost.png")
    else:
        # Build a tiny blank image and ensure parse completes when opencv exists.
        import cv2
        import numpy as np
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.rectangle(img, (40, 40), (160, 160), (255, 255, 255), 3)
        p = tmp_path / "box.png"
        cv2.imwrite(str(p), img)
        plan = ImageCADProcessor().parse(str(p), "box.png")
        assert plan.image is not None
        assert plan.image.provider == "opencv"


def test_dxf_missing_file_raises():
    with pytest.raises(CADProcessingError, match="not found"):
        EzdxfCADProcessor().parse("nope.dxf", "nope.dxf")