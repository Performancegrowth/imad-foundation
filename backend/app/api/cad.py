"""Sprint 2 — CAD / image processing endpoint."""
from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.storage import load_upload, result_id, save_result
from app.models.plan_data import PlanData
from app.services.cad_processor import (
    CADProcessingError,
    CADProcessor,
    get_cad_processor,
)

log = logging.getLogger("imad.api.cad")

router = APIRouter()


class ProcessRequest(BaseModel):
    file_id: int


class ProcessResponse(BaseModel):
    result_id: str
    status: str
    source: str
    file_id: int
    counts: Dict[str, int]
    plan: Dict


@router.post("/process-cad", response_model=ProcessResponse, summary="Extract structure from a design file")
async def process_cad(payload: ProcessRequest):
    """Parse an uploaded CAD/image file into shared plan geometry."""
    meta = load_upload(payload.file_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown file_id {payload.file_id}.")

    try:
        processor: CADProcessor = get_cad_processor(meta["original_name"])
    except CADProcessingError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    try:
        plan: PlanData = await _run_processor(processor, meta["stored_path"], meta["original_name"])
    except CADProcessingError as exc:
        save_result(result_id("cad"), {"error": str(exc)}, status="failed")
        raise HTTPException(status_code=422, detail=f"Processing failed: {exc}") from exc

    rid = result_id("cad")
    save_result(rid, {"file_id": payload.file_id, "source": plan.source,
                      "plan": plan.model_dump(mode="json"),
                      "counts": _counts(plan)})

    return ProcessResponse(
        result_id=rid,
        status="completed",
        source=plan.source,
        file_id=payload.file_id,
        counts=_counts(plan),
        plan=plan.model_dump(mode="json"),
    )


async def _run_processor(processor: CADProcessor, path: str, name: str) -> PlanData:
    """Bridge any processor's sync parse into async context."""
    return processor.parse(path, name)


def _counts(plan: PlanData) -> Dict[str, int]:
    return {
        "walls": len(plan.walls),
        "columns": len(plan.columns),
        "beams": len(plan.beams),
        "grids": len(plan.grids),
        "stories": plan.stories,
    }