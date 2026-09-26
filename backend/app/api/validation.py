"""Sprint 11 — Engineering validation & certification endpoints.

POST /validation/run       → run the hand-calc benchmark suite
GET  /validation/report    → latest stored suite report
GET  /validation/report/pdf→ branded PDF accuracy report download
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.core.docstore import collection
from app.services.validation_engine import ValidationError, run_suite, validation_pdf

log = logging.getLogger("imad.api.validation")
# AuthZ: benchmark reports back the certification posture of the deployment.
router = APIRouter(dependencies=[Depends(get_current_user)])

# Public, read-only mirror for the marketing "Proof" page. The benchmark
# numbers are the same suite the authed routes run — nothing sensitive is
# exposed (no project data), so anonymous visitors may read the latest
# published report. Writes stay behind auth on `router` above.
public_router = APIRouter()

KNOWN_CASES = (
    "beam_udl",
    "column_gravity",
    "frame_elf",
    "cont_beam",
    "oneway_slab",
    "twoway_slab",
    "punching",
    "footing",
    "column_pm",
    "dev_length",
    "wind_shear",
    "seismic_shear",
)
# Accept either the canonical engine ids above or the friendly aliases below.
_CASE_ALIASES = {"beam": "beam_udl", "column": "column_gravity", "frame": "frame_elf"}


class ValidationRunRequest(BaseModel):
    cases: Optional[List[str]] = None      # default: all benchmarks


@router.post("/validation/run", summary="Run benchmark suite vs hand calculations")
async def run(payload: ValidationRunRequest) -> Dict[str, Any]:
    cases = payload.cases or None
    if cases:
        cases = [_CASE_ALIASES.get(c, c) for c in cases]
    if cases:
        unknown = [c for c in cases if c not in KNOWN_CASES]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown cases {unknown}; valid: {KNOWN_CASES}")
    try:
        report = run_suite(cases)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    stored = collection("validation_reports").put(report, prefix="val")
    return {"report_id": stored["id"], **report}


@router.get("/validation/report", summary="Latest validation suite report")
async def latest() -> Dict[str, Any]:
    reports = collection("validation_reports").list()
    if not reports:
        raise HTTPException(
            status_code=404,
            detail="No validation run yet — POST /validation/run first.")
    latest_report = max(reports, key=lambda r: r.get("created_at", ""))
    return latest_report


@public_router.get("/validation/public",
                   summary="Latest benchmark report (public, no auth)")
async def public_latest() -> Dict[str, Any]:
    """Latest stored report, computed on first request if none exists yet.

    Keeps the public Proof page populated without exposing any per-user or
    per-project data — the suite is deterministic and input-free.
    """
    reports = collection("validation_reports").list()
    if reports:
        return max(reports, key=lambda r: r.get("created_at", ""))
    try:
        report = run_suite(None)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    collection("validation_reports").put(report, prefix="val")
    return report


@router.get("/validation/report/pdf", summary="Download the latest accuracy report (PDF)")
async def latest_pdf():
    reports = collection("validation_reports").list()
    if not reports:
        raise HTTPException(status_code=404, detail="No validation run yet.")
    latest_report = max(reports, key=lambda r: r.get("created_at", ""))
    try:
        path = validation_pdf(latest_report)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/pdf",
                        filename=path.replace("\\", "/").split("/")[-1])


# ── B3 public trust assets (no auth): reproducible hash + shareable PDF ─────
# Deliberately on `public_router` (no auth): prospects must be able to verify
# the benchmark numbers without an account. NOTE: GET /validation/report/pdf
# above is the authed stored-report download; the public PDF therefore lives
# on its own path /validation/public/report/pdf so neither route shadows
# the other.
@public_router.get("/validation/hash",
                   summary="SHA-256 of the canonical validation report")
async def validation_hash() -> dict:
    from app.services.validation_engine import run_suite
    import hashlib, json
    from datetime import datetime, timezone
    report = run_suite()
    canonical_report = dict(report)
    canonical_report.pop("ran_at", None)   # timestamp varies per call; excluded from hash
    canonical = json.dumps(canonical_report, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "hash": f"sha256:{digest}",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(report.get("cases", [])),
        "algorithm": "sha256",
        "canonicalization": "json.dumps(sort_keys=True, separators=(',',':'))",
        "excluded_fields": ["ran_at"],
        "note": "ran_at varies per call; excluded from hash so the 12-case content hash is deterministic.",
    }


@public_router.get("/validation/public/report/pdf",
                   summary="Download the validation report as PDF (public)")
async def validation_report_pdf():
    from app.services.validation_engine import run_suite
    from app.services.exporters import validation_report_pdf as build_pdf
    from fastapi.responses import Response
    import hashlib, json
    from datetime import datetime, timezone
    report = run_suite()
    canonical_report = dict(report)
    canonical_report.pop("ran_at", None)   # timestamp varies per call; excluded from hash
    canonical = json.dumps(canonical_report, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    computed_at = datetime.now(timezone.utc).isoformat()
    pdf_bytes = build_pdf(report, hash_value=digest, computed_at=computed_at)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="imad-validation-report.pdf"',
            "X-Validation-Hash": f"sha256:{digest}",
            "X-Computed-At": computed_at,
        },
    )