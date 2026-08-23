"""Sprint 14 — Background job status/result endpoints.

Long-running work (structural analysis, BOQ generation, carbon reports,
generative design) is dispatched to a queue and completed by the worker
service. These endpoints let clients poll for progress and retrieve the
final JSON result.

Routes:
    GET /api/jobs/{job_id}         → status + progress + error
    GET /api/jobs/{job_id}/result  → completed payload (409 if still running)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import jobs

router = APIRouter()

_FIELDS = ("id", "kind", "status", "progress", "error", "created_at", "updated_at")


@router.get("/jobs/{job_id}", summary="Poll a background job's status")
async def job_status(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'.")
    return {key: job.get(key) for key in _FIELDS}


@router.get("/jobs/{job_id}/result", summary="Fetch a completed job's result")
async def job_result(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'.")
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed yet.")
    return {"job_id": job_id, "kind": job.get("kind"), "result": job.get("result")}