"""
Sprint 4 — Survey engineering module.

``ManualSurveyProcessor`` validates + persists hand-entered site data.
``FileSurveyProcessor`` ingests evidence from PDF reports, CSV/dxf surveys and
LAS point clouds. Both normalise into :class:`SurveyReading` and a readable
:class:`SurveySummary`, which later sprints feed to foundation & earthwork.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.models.survey_data import SurveyReading, SurveySummary

log = logging.getLogger("imad.survey")

SURVEY_EXTENSIONS = (".pdf", ".csv", ".dxf", ".las", ".laz")
CSV_COLUMN_HINTS = {
    "bearing": "soil_bearing_capacity_kpa",
    "bearing_capacity": "soil_bearing_capacity_kpa",
    "kpa": "soil_bearing_capacity_kpa",
    "groundwater": "groundwater_depth_m",
    "water_table": "groundwater_depth_m",
    "depth": "groundwater_depth_m",
    "slope": "terrain_slope_deg",
    "latitude": "latitude",
    "lat": "latitude",
    "longitude": "longitude",
    "lon": "longitude",
    "long": "longitude",
    "elevation": "altitude_m",
    "altitude": "altitude_m",
    "z": "altitude_m",
}


class SurveyError(Exception):
    """Raised on invalid or unreadable survey input."""


class SurveyProcessor(ABC):
    """Base survey ingest contract."""

    source: str = "manual"

    @abstractmethod
    def process(self, *args, **kwargs):
        """Produce normalised survey data."""


def default_storage_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "storage" / "survey"


# ───────────────────────────────────────────────────────── manual ────────────
class ManualSurveyProcessor(SurveyProcessor):
    """Validate and persist hand-entered geotechnical data."""

    source = "manual"

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir) if storage_dir else default_storage_dir()

    def validate(self, data: Dict[str, Any]) -> SurveyReading:
        """Coerce + validate a manual entry (raises :class:`SurveyError`)."""
        try:
            reading = SurveyReading(**data)
        except Exception as exc:
            raise SurveyError(f"Invalid survey entry: {exc}") from exc
        return reading

    def process(self, project_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        reading = self.validate(data)
        entries = self._load_entries(project_id)
        payload = reading.model_dump(mode="json")
        payload["source"] = "manual"
        entries.append(payload)
        self._write_entries(project_id, entries)
        summary = _summarise(reading, source="manual")
        return summary.model_dump(mode="json") | {"stored": len(entries)}

    def load_summary(self, project_id: int) -> SurveySummary:
        entries = self._load_entries(project_id)
        if not entries:
            return SurveySummary(message="No survey data recorded yet.")
        readings = [SurveyReading(**e) for e in entries]
        summary = _summarise(readings[-1], source=entries[-1].get("source", "manual"))
        summary.entries = len(readings)
        return summary

    def _load_entries(self, project_id: int) -> List[Dict[str, Any]]:
        path = self.storage_dir / str(project_id) / "survey.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_entries(self, project_id: int, entries: List[Dict[str, Any]]) -> None:
        target = self.storage_dir / str(project_id)
        target.mkdir(parents=True, exist_ok=True)
        (target / "survey.json").write_text(
            json.dumps(entries, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────── file ─────────
class FileSurveyProcessor(SurveyProcessor):
    """Parse uploaded survey evidence files into reading + summary."""

    source = "file"

    def process(self, path: str, project_id: int) -> Dict[str, Any]:
        ext = Path(path).suffix.lower()
        if ext not in SURVEY_EXTENSIONS:
            raise SurveyError(f"Unsupported survey file type '{ext or '?'}'.")
        reading, summary = self._dispatch(ext, path)
        return reading.model_dump(mode="json") | summary.model_dump(mode="json")

    def _dispatch(self, ext: str, path: str) -> Tuple[SurveyReading, SurveySummary]:
        if ext == ".pdf":
            return self._parse_pdf(path)
        if ext == ".csv":
            return self._parse_csv(path)
        if ext == ".dxf":
            return self._parse_dxf(path)
        if ext in (".las", ".laz"):
            return self._parse_las(path)
        raise SurveyError(f"Unhandled extension {ext}.")

    def _parse_pdf(self, path: str) -> Tuple[SurveyReading, SurveySummary]:
        try:
            import pdfplumber
        except ImportError as exc:
            raise SurveyError("pdfplumber required to parse PDF reports.") from exc

        text = ""
        with pdfplumber.open(path) as pdf:
            text = " ".join((page.extract_text() or "") for page in pdf.pages)
        reading = SurveyReading(raw_payload={"pdf_excerpt": text[:2000]})
        reading.soil_bearing_capacity_kpa = _match_number(
            text, r"(bearing capacity|q_all|qadm)[^0-9.]*([0-9.]+)\s*kPa")
        reading.groundwater_depth_m = _match_number(
            text, r"(groundwater|water table|GWT)[^0-9.]*([0-9.]+)\s*m")
        reading.soil_type = _match_text(text, r"(sand|silt|clay|gravel|rock)")
        summary = _summarise(reading, source="pdf")
        return reading, summary

    def _parse_csv(self, path: str) -> Tuple[SurveyReading, SurveySummary]:
        reading = SurveyReading()
        header = []
        rows = []
        with open(path, newline="", encoding="utf-8", errors="replace") as handle:
            reader = csv.DictReader(handle)
            header = list(reader.fieldnames or [])
            rows = list(reader)
        mapped: Dict[str, List[float]] = {}
        for col in header:
            field = _map_column(col)
            if field:
                mapped.setdefault(field, [])
        for row in rows:
            for col in header:
                field = _map_column(col)
                if not field or row.get(col) in (None, ""):
                    continue
                try:
                    mapped[field].append(float(row[col]))
                except ValueError:
                    continue
        for field, values in mapped.items():
            if values:
                setattr(reading, field, sum(values) / len(values))  # mean
        reading.raw_payload = {"rows": len(rows)}
        if reading.latitude is not None and reading.longitude is not None:
            reading.notes = f"{len(rows)} coordinate/elevation records imported."
        summary = _summarise(reading, source="csv", entries=len(rows))
        return reading, summary

    def _parse_dxf(self, path: str) -> Tuple[SurveyReading, SurveySummary]:
        try:
            import ezdxf
        except ImportError as exc:
            raise SurveyError("ezdxf required to parse contour DXF.") from exc
        try:
            doc = ezdxf.readfile(path)
            elevations = [
                float(e.dxf.elevation)
                for e in doc.modelspace()
                if e.dxftype() == "LWPOLYLINE" and hasattr(e.dxf, "elevation")
            ]
            if not elevations:
                elevations = [
                    float(e.dxf.start.z)
                    for e in doc.modelspace()
                    if e.dxftype() == "LINE" and hasattr(e.dxf.start, "z")
                ]
        except Exception as exc:
            raise SurveyError(f"Could not read DXF contours: {exc}") from exc
        if elevations:
            reading = SurveyReading(
                raw_payload={"contours": len(elevations)},
                terrain_slope_deg=_slope_from_elevations(elevations),
            )
        else:
            reading = SurveyReading(raw_payload={"contours": 0})
        summary = _summarise(reading, source="dxf", entries=len(elevations))
        return reading, summary

    def _parse_las(self, path: str) -> Tuple[SurveyReading, SurveySummary]:
        try:
            import laspy
        except ImportError as exc:
            raise SurveyError("laspy required to parse LAS point clouds.") from exc
        try:
            las = laspy.read(path)
            z = las.z if hasattr(las, "z") else None
        except Exception as exc:
            raise SurveyError(f"Could not read LAS: {exc}") from exc
        if z is None or len(z) == 0:
            raise SurveyError("LAS file contains no elevation data.")
        sample = [float(v) for v in z[:20000]]
        reading = SurveyReading(
            raw_payload={"points": int(len(z))},
            terrain_slope_deg=_slope_from_elevations(sample),
        )
        summary = _summarise(reading, source="las", entries=int(len(z)))
        return reading, summary


# ─────────────────────────────────────────────────────────────── helpers ─────
def _summarise(reading: SurveyReading, source: str, entries: int = 1) -> SurveySummary:
    location = None
    if reading.latitude is not None and reading.longitude is not None:
        location = f"{reading.latitude:.4f}, {reading.longitude:.4f}"
    parts = []
    if reading.soil_bearing_capacity_kpa:
        parts.append(f"Soil bearing ≈ {reading.soil_bearing_capacity_kpa:.0f} kPa")
    if reading.groundwater_depth_m is not None:
        parts.append(f"GWT ≈ {reading.groundwater_depth_m:.2f} m")
    if reading.terrain_slope_deg is not None:
        parts.append(f"Slope ≈ {reading.terrain_slope_deg:.1f}°")
    return SurveySummary(
        soil_bearing_capacity_kpa=reading.soil_bearing_capacity_kpa,
        groundwater_depth_m=reading.groundwater_depth_m,
        terrain_slope_deg=reading.terrain_slope_deg,
        location=location,
        source=source,
        entries=entries,
        message="; ".join(parts) if parts
                else f"{source} import produced no numeric picks.",
    )


def _match_number(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(2))
    except (ValueError, IndexError):
        return None


def _match_text(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).lower() if m else None


def _map_column(header: str) -> Optional[str]:
    key = re.sub(r"[^a-z]+", "_", header.lower()).strip("_")
    return CSV_COLUMN_HINTS.get(key) or CSV_COLUMN_HINTS.get(header.lower())


def _slope_from_elevations(elevations: List[float]) -> float:
    """Estimate terrain slope (°) from the spread of point elevations."""
    if len(elevations) < 2:
        return 0.0
    low, high = min(elevations), max(elevations)
    span = high - low
    return round(math.degrees(math.atan(span / 100.0)), 1)  # 100 m sampling window