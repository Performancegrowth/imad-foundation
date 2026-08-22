"""Survey data model — Sprint 4 engineering site data.

Captures site constraints that drive foundation and earthwork decisions:
soil bearing capacity, groundwater depth, coordinates, terrain slope, plus
file-imported evidence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SurveyReading(BaseModel):
    """A validated survey / geotechnical reading with SI units."""

    cycle: str = "baseline"
    soil_bearing_capacity_kpa: Optional[float] = Field(None, gt=0, le=5000)
    groundwater_depth_m: Optional[float] = Field(None, ge=0, le=500)
    terrain_slope_deg: Optional[float] = Field(None, ge=0, le=90)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    altitude_m: Optional[float] = None
    soil_type: Optional[str] = None        # e.g. "clay", "sand", "rock"
    water_table_varied: bool = False
    notes: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    captured_at: Optional[datetime] = None


class SurveySummary(BaseModel):
    """Human-readable summary card drawn from imported survey data."""

    soil_bearing_capacity_kpa: Optional[float] = None
    groundwater_depth_m: Optional[float] = None
    terrain_slope_deg: Optional[float] = None
    location: Optional[str] = None
    source: str = "manual"          # manual | pdf | csv | dxf | las
    entries: int = 0
    message: str = ""


class SurveyData(SurveyReading):
    """Persisted survey row returned by the API."""

    id: int
    project_id: int
    source: str = "manual"
    created_at: datetime

    class Config:
        orm_mode = True