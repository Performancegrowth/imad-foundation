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

    # ── Lateral-load parameters (roadmap #9e) ──────────────────────────────
    ss_mps2: Optional[float] = Field(None, gt=0, le=3.0,
        description="Mapped short-period spectral acceleration Ss (g)")
    s1_mps2: Optional[float] = Field(None, gt=0, le=2.0,
        description="Mapped 1-sec spectral acceleration S1 (g)")
    site_class: Optional[str] = Field(None, pattern="^[A-F]$",
        description="Site class per SBC 301 §12.2 (rock A → soft F)")
    r_factor: Optional[float] = Field(None, ge=1.0, le=8.0,
        description="Response modification factor R per §12.2")
    seismic_importance: Optional[float] = Field(None, ge=1.0, le=1.5,
        description="Importance factor I per §12.2")
    basic_wind_speed_mps: Optional[float] = Field(None, ge=0, le=100,
        description="3-sec gust basic wind speed V (m/s), SBC ch. 27")
    wind_exposure: Optional[str] = Field(None, pattern="^[BCD]$",
        description="Wind exposure category B/C/D per ch. 27")


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