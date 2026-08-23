"""Sprint 4 — Survey processor tests."""
from __future__ import annotations

import pytest

from app.services.survey_processor import (
    CSV_COLUMN_HINTS,
    FileSurveyProcessor,
    ManualSurveyProcessor,
    SurveyError,
)


def test_manual_validation_accepts_valid():
    proc = ManualSurveyProcessor(storage_dir="/tmp/imad-test-survey")
    reading = proc.validate({
        "soil_bearing_capacity_kpa": 180,
        "groundwater_depth_m": 2.4,
        "terrain_slope_deg": 5,
        "latitude": 24.7,
        "longitude": 46.7,
    })
    assert reading.soil_bearing_capacity_kpa == 180


def test_manual_validation_rejects_out_of_range():
    proc = ManualSurveyProcessor(storage_dir="/tmp/imad-test-survey")
    with pytest.raises(SurveyError):
        proc.validate({"soil_bearing_capacity_kpa": -5})
    with pytest.raises(SurveyError):
        proc.validate({"latitude": 95.0})


def test_manual_summary_empty():
    proc = ManualSurveyProcessor(storage_dir="/tmp/imad-test-survey-empty")
    summary = proc.load_summary(12345)
    assert "No survey data" in summary.message


def test_csv_import_maps_columns(tmp_path):
    content = (
        "latitude,longitude,elevation,z\n"
        "24.70,46.70,310.5,310.5\n"
        "24.71,46.71,312.0,312.0\n"
    )
    csv_file = tmp_path / "topo.csv"
    csv_file.write_text(content, encoding="utf-8")

    result = FileSurveyProcessor().process(str(csv_file), project_id=1)
    assert result["latitude"] == pytest.approx((24.70 + 24.71) / 2, abs=0.01)
    assert result["longitude"] == pytest.approx((46.70 + 46.71) / 2, abs=0.01)
    assert result["source"] == "csv"
    assert result["entries"] == 2


def test_survey_rejects_unknown_extension(tmp_path):
    unknown = tmp_path / "notes.txt"
    unknown.write_text("hello")
    with pytest.raises(SurveyError, match="Unsupported"):
        FileSurveyProcessor().process(str(unknown), project_id=1)


def test_column_hint_table_maps_common_headers():
    assert CSV_COLUMN_HINTS["bearing_capacity"] == "soil_bearing_capacity_kpa"
    assert CSV_COLUMN_HINTS["groundwater"] == "groundwater_depth_m"
    assert CSV_COLUMN_HINTS["latitude"] == "latitude"