"""Sprint 7 — Section Designer endpoints.

POST /sections/analyze → cross-section properties (+ preliminary capacities)
for standard shapes (rect / circle / I / tee / channel). Uses the
``sectionproperties`` package when installed, otherwise exact closed-form
formulas (the response flags which solver produced the numbers).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.section_designer import (
    MATERIALS,
    SUPPORTED_SHAPES,
    SectionDesigner,
    SectionDesignError,
)

log = logging.getLogger("imad.api.sections")
router = APIRouter()

_designer = SectionDesigner()


class SectionRequest(BaseModel):
    section: Dict[str, Any] = Field(
        ..., description="Shape definition, e.g. {'shape':'rect','b':300,'d':500}")
    material: Optional[Dict[str, Any]] = Field(
        None, description="Optional overrides: e_mpa / fy / density (or a MATERIALS name)")
    mesh_size: float = Field(5.0, gt=0, description="sectionproperties mesh size (mm)")
    force_analytic: bool = Field(
        False, description="Bypass sectionproperties and use closed-form formulas")


def _resolve_material(material: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Allow shorthand material names ('S355', 'C30') or explicit overrides."""
    if not material:
        return None
    if set(material.keys()) == {"name"} and material["name"] in MATERIALS:
        return MATERIALS[material["name"]]
    return material


@router.post("/sections/analyze", summary="Cross-section properties & capacities")
async def analyze_section(payload: SectionRequest) -> Dict[str, Any]:
    """Compute geometric + plastic section properties for one section."""
    try:
        props = _designer.analyze(
            payload.section,
            mesh_size=payload.mesh_size,
            force_analytic=payload.force_analytic,
        )
    except SectionDesignError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surfaced as 500 below
        log.exception("Section analysis crashed")
        raise HTTPException(status_code=500, detail=f"Section analysis failed: {exc}") from exc

    response: Dict[str, Any] = {
        "status": "completed",
        "solver": props.get("solver"),
        "supported_shapes": list(SUPPORTED_SHAPES),
        **props,
    }
    try:
        response["capacities"] = _designer.capacities(props, _resolve_material(payload.material))
    except Exception as exc:  # noqa: BLE001 — capacities are additive
        log.warning("Capacities skipped: %s", exc)
    return response