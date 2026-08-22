"""Shared engineering geometry schema (the single plan data contract).

Every source — CAD processor, image processor, plan editor, questionnaire,
template, or natural-language description — emits the same ``PlanData`` shape,
so downstream structural analysis and BOQ treat all inputs identically.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    x: float = 0.0
    y: float = 0.0


class GridLine(BaseModel):
    id: str
    orientation: Literal["vertical", "horizontal"] = "vertical"
    position: float = 0.0
    label: str = ""


class Wall(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    thickness_m: float = 0.15
    level: int = 0          # floor / storey index
    height_m: Optional[float] = None
    kind: Literal["bearing", "partition"] = "bearing"


class Beam(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    depth_m: float = 0.5
    width_m: float = 0.3
    level: int = 0


class Column(BaseModel):
    id: str
    cx: float
    cy: float
    size_m: float = 0.3    # side length (square plastic)
    height: float = 3.0
    level: int = 0


class Room(BaseModel):
    id: str
    label: str = ""
    boundary: List[GeoPoint] = Field(default_factory=list)  # closed polygon
    area_m2: float = 0.0
    level: int = 0


class ImageInput(BaseModel):
    """Reference to a non-CAD source (scan / photo) that produced this plan."""

    source_id: Optional[int] = None
    file_name: str = ""
    provider: str = ""


class PlanData(BaseModel):
    """The canonical floor-plan / structural layout in meters."""

    version: str = "1.0"
    units: str = "m"
    source: str = "cad"            # cad | image | editor | questionnaire | template | ai
    walls: List[Wall] = Field(default_factory=list)
    columns: List[Column] = Field(default_factory=list)
    beams: List[Beam] = Field(default_factory=list)
    grids: List[GridLine] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)
    stories: int = 1
    materials: Dict[str, Any] = Field(default_factory=lambda: {"concrete": "C30", "steel": "A615 Gr60"})
    image: Optional[ImageInput] = None
    label: str = ""
    original: Dict[str, Any] = Field(default_factory=dict)

    def bounds(self) -> Dict[str, float]:
        """Overall extent (min_x, min_y, max_x, max_y) across all elements."""
        xs, ys = [0.0], [0.0]
        for wall in self.walls:
            xs += [wall.x1, wall.x2]
            ys += [wall.y1, wall.y2]
        for column in self.columns:
            xs += [column.cx]
            ys += [column.cy]
        for beam in self.beams:
            xs += [beam.x1, beam.x2]
            ys += [beam.y1, beam.y2]
        return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}

    def __bool__(self) -> bool:
        """True when the plan actually contains load-bearing geometry."""
        return bool(self.walls or self.columns or self.beams)