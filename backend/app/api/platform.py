"""Sprint 14 — Platform endpoints: job queue monitor, tutorials, support chat."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.jobs import get_job, jobs_dir
from app.services.agents import AgentError, support_reply

log = logging.getLogger("imad.api.platform")
router = APIRouter()

# Customer-success walkthroughs (Sprint 14) — served statically, editable later.
TUTORIALS: List[Dict[str, Any]] = [
    {"id": "upload-cad", "title": "Import a CAD drawing", "minutes": 3,
     "steps": ["Open the CAD workspace from the sidebar",
               "Drag a DXF, PDF or image onto the drop zone",
               "Press Process and review the extracted walls, columns and beams",
               "Save the extracted geometry as a plan"]},
    {"id": "create-plan", "title": "Create a plan without CAD", "minutes": 4,
     "steps": ["Open Create Plan", "Pick questionnaire, template or plain description",
               "Generate and adjust the layout in the 2D editor", "Save the plan"]},
    {"id": "analyze", "title": "Run a structural analysis", "minutes": 5,
     "steps": ["Open Analysis and pick a saved plan",
               "Press Analyze Structure and watch the progress bar",
               "Review forces, deflections and the 3D model"]},
    {"id": "boq", "title": "Price your design", "minutes": 4,
     "steps": ["Open the BOQ workspace", "Select the analyzed plan",
               "Generate quantities and the cutting-optimised BBS",
               "Export the PDF report or Excel workbook"]},
    {"id": "carbon", "title": "Sustainability check", "minutes": 3,
     "steps": ["Generate a BOQ first", "Open Sustainability",
               "Compare green alternatives (GGBS, EAF steel, reused formwork)",
               "Download the LCA report"]},
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    history: List[Dict[str, str]] = Field(default_factory=list)


@router.get("/jobs", summary="Queue monitor — recent background jobs")
async def list_jobs(limit: int = 25) -> Dict[str, Any]:
    files = sorted(Path(jobs_dir()).glob("job*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[: max(1, limit)]
    jobs: List[Dict[str, Any]] = []
    for f in files:
        try:
            jobs.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    counts: Dict[str, int] = {}
    for j in jobs:
        state = j.get("status", "unknown")
        counts[state] = counts.get(state, 0) + 1
    return {"jobs": jobs, "counts": counts,
            "backend": "in-process + disk (Redis/Celery-ready)"}


@router.get("/jobs/{job_id}", summary="Single job status")
async def job_status(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job.")
    return job


@router.get("/tutorials", summary="Customer-success walkthrough catalogue")
async def tutorials() -> Dict[str, Any]:
    return {"tutorials": TUTORIALS}


@router.post("/support/chat", summary="Live support chat (LLM with template fallback)")
async def support_chat(payload: ChatRequest) -> Dict[str, Any]:
    try:
        return await support_reply(payload.message, payload.history)
    except AgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc