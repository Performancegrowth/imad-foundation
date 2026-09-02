"""Sprint 10 — Governance endpoints: compliance, e-signatures, submissions,
and the immutable audit trail viewer."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.docstore import collection
from app.core.storage import load_result
from app.services.boq_generator import generate_boq
from app.services.compliance_engine import ComplianceEngine
from app.services.exporters import build_pdf_report, exports_dir, now_iso
from app.services.noncad_processor import PlanGenerationError, PlanGenerator
from app.services.sbc304_report import generate_sbc304_report
from app.services.survey_processor import load_survey_reading

log = logging.getLogger("imad.api.governance")
router = APIRouter()

_signatures = collection("signature_requests")
_submissions = collection("submission_packages")
_checks = collection("compliance_checks")

SIGNING_ROLES = {"engineer", "admin", "owner"}   # RBAC gate for approve/sign


class ComplianceRequest(BaseModel):
    project_id: int = 1
    plan_name: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    survey: Optional[Dict[str, Any]] = None


class SignatureRequestBody(BaseModel):
    project_id: int = 1
    design_id: str = "current"
    engineer_name: str = Field(min_length=2)
    license_number: str = Field(min_length=2)
    provider: str = Field(default="internal_seal",
                          pattern="^(internal_seal|docusign|adobe_sign)$")
    actor_role: str = "engineer"


class SignatureCompleteBody(BaseModel):
    outcome: str = Field(default="signed", pattern="^(signed|rejected|expired)$")
    notes: str = ""


class SubmissionStatusBody(BaseModel):
    """A municipality-side tracking event for a submission package."""
    status: str = Field(pattern="^(generated|submitted|under_review|"
                                "approved|revision_required|rejected|signed)$")
    notes: str = ""
    authority: str = ""
    reference_number: str = ""


@router.post("/compliance/check", summary="Run SBC 304 code-compliance checks")
async def compliance_check(payload: ComplianceRequest) -> Dict[str, Any]:
    plan = _resolve_plan(payload.plan_name, payload.plan)
    engine = ComplianceEngine(plan, analysis=payload.analysis, survey=payload.survey)
    report = engine.run_all()
    record = _checks.put({
        "project_id": payload.project_id, "report": report,
    }, prefix="chk")
    audit.log_action("compliance_check", project_id=payload.project_id,
                     details={"check_id": record["id"],
                              "passed": report.get("summary", {}).get("passed")})
    return {"check_id": record["id"], **report}


class SBCPackageRequest(BaseModel):
    """Request for the preliminary SBC 304 calculation package (PDF)."""

    project_id: int = 1
    project_name: Optional[str] = None
    plan_name: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    analysis_result_id: Optional[str] = None
    survey: Optional[Dict[str, Any]] = None
    boq: Optional[Dict[str, Any]] = None


@router.post("/compliance/sbc304-package",
             summary="Generate the preliminary SBC 304 calculation package (PDF)")
async def sbc304_package(payload: SBCPackageRequest) -> Dict[str, Any]:
    """Assemble the Sprint 10 calculation package from engine outputs.

    The report builder only formats results; this endpoint resolves inputs:
    plan (inline or saved), analysis (inline, or a stored ``/analyze`` result
    id), survey (inline, or the project's recorded survey), compliance
    (always recomputed by the authoritative engine) and an optional BOQ.
    """
    plan = _resolve_plan(payload.plan_name, payload.plan)

    analysis = payload.analysis
    if analysis is None and payload.analysis_result_id:
        stored = load_result(payload.analysis_result_id)
        if not stored:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis result '{payload.analysis_result_id}' not found.",
            )
        # Storage wraps results in an envelope ({id, status, payload, ...});
        # the report needs the inner payload, not the envelope.
        analysis = stored.get("payload") if isinstance(stored, dict) else stored

    if analysis is None:
        # Homebuilder flow: no analysis supplied — run the authoritative
        # engine here (stores an auditable per-project result, exactly like
        # POST /analysis/analyze) instead of demanding analysis input.
        from app.api.analysis import run_analysis

        analysis_data: Dict[str, Any] = {"project_id": payload.project_id}
        if payload.plan_name:
            analysis_data["plan_name"] = payload.plan_name
        if payload.plan is not None:
            analysis_data["plan"] = payload.plan
        if payload.survey is not None:
            analysis_data["survey"] = payload.survey
        analysis = run_analysis(analysis_data)

    survey = payload.survey
    if survey is None and payload.project_id:
        reading = load_survey_reading(payload.project_id)
        if reading is not None:
            survey = reading.model_dump()

    # The compliance engine always runs here — the report builder never
    # invents or overrides PASS/WARN/FAIL results.
    compliance = ComplianceEngine(
        plan, analysis=analysis, survey=survey,
    ).run_all()

    boq = payload.boq
    if boq is None:
        try:
            boq = generate_boq(
                plan, project_name=payload.project_name
                or f"Project {payload.project_id}"
            )
        except Exception as exc:  # BOQ is supplementary — never blocks
            log.warning("SBC 304 package BOQ skipped: %s", exc)
            boq = None

    # Promote engine metadata carried inside the design dict so the report
    # builder sees a flat, auditable result object. Caller top-level keys
    # always win; nothing is fabricated when absent. The document code
    # identity is left to the compliance engine (SBC 304), while the design
    # code used by concrete_design travels inside design_factors/references.
    design = analysis.get("design") if isinstance(analysis.get("design"), dict) else {}
    report_analysis = {
        **analysis,
        "method": analysis.get("method") or analysis.get("solver"),
        "design_factors": analysis.get("design_factors")
        or design.get("design_factors"),
        "references": analysis.get("references") or design.get("references"),
    }

    path = generate_sbc304_report(
        project_id=payload.project_id,
        project_name=payload.project_name or f"Project {payload.project_id}",
        plan=plan,
        analysis=report_analysis,
        compliance=compliance,
        boq=boq,
        survey=survey,
    )

    record = _submissions.put({
        "project_id": payload.project_id,
        "file_path": path,
        "package_type": "sbc304_preliminary_calculation_package",
        "status": "generated",
        "tracking": [],
        "contents": ["sbc304_calculation_package", "compliance_report"]
                    + (["boq_summary"] if boq else []),
        "compliance_summary": compliance.get("summary"),
        "analysis_result_id": payload.analysis_result_id,
        "signed_by": None,
    }, prefix="sub")
    audit.log_action("sbc304_package_generated", project_id=payload.project_id,
                     details={"package_id": record["id"], "path": path})
    return record


@router.get("/compliance/sbc304-readiness/{project_id}",
            summary="Submission-readiness checklist for the SBC 304 package")
async def sbc304_readiness(project_id: int) -> Dict[str, Any]:
    """Report what exists for this project versus what the SBC 304
    submission path needs.

    Read-only and data-driven: every item reflects an actual stored
    artifact (saved plan, recorded survey, compliance run, generated
    package, professional sign-off). Nothing is generated here and no
    status is guessed.
    """
    from pathlib import Path

    def _latest(coll, predicate):
        try:
            records = [r for r in coll.list() if predicate(r)]
        except Exception:
            return None
        if not records:
            return None
        return max(records, key=lambda r: str(r.get("created_at", "")))

    saved_plans: list = []
    try:
        saved_plans = list(PlanGenerator.list_plans(project_id) or [])
    except Exception:
        saved_plans = []
    plan_names = [
        str(p.get("name") if isinstance(p, dict) else getattr(p, "name", ""))
        for p in saved_plans
        if (p.get("name") if isinstance(p, dict) else getattr(p, "name", None))
    ]

    survey = load_survey_reading(project_id)

    latest_check = _latest(
        _checks, lambda r: r.get("project_id") == project_id)
    latest_pkg = _latest(
        _submissions,
        lambda r: r.get("project_id") == project_id
        and str(r.get("package_type", "")).startswith("sbc304"),
    )

    pkg_file = (latest_pkg or {}).get("file_path")
    pkg_exists = bool(pkg_file) and Path(pkg_file).exists()

    check_summary = (latest_check or {}).get("report", {}).get("summary", {}) \
        if latest_check else {}
    failed_count = check_summary.get("failed", 0) or 0
    latest_signature = _latest(
        _signatures, lambda r: r.get("project_id") == project_id)

    checklist = [
        {
            "item": "Site plan (saved)",
            "ready": bool(plan_names),
            "detail": plan_names[0] if plan_names
            else "No saved plan for this project.",
        },
        {
            "item": "Site survey (geotechnical)",
            "ready": survey is not None,
            "detail": "Recorded survey available"
            if survey is not None else "No recorded survey for this project.",
        },
        {
            "item": "Code compliance run",
            "ready": latest_check is not None,
            "detail": (
                f"Last run: {check_summary.get('passed', 0)} passed / "
                f"{check_summary.get('warned', 0)} warned / "
                f"{failed_count} failed"
            ) if latest_check else "No compliance check recorded yet.",
        },
        {
            "item": "No failing code checks",
            "ready": latest_check is not None and failed_count == 0,
            "detail": "PASS (compliance engine)" if latest_check and failed_count == 0
            else f"{failed_count} failing checks" if latest_check
            else "Blocked until a compliance run exists.",
        },
        {
            "item": "SBC 304 calculation package (PDF)",
            "ready": pkg_exists,
            "detail": pkg_file if pkg_exists
            else "Not generated yet — POST /compliance/sbc304-package.",
        },
        {
            "item": "Professional engineer sign-off",
            "ready": bool((latest_pkg or {}).get("signed_by"))
            or (latest_signature or {}).get("status") == "signed",
            "detail": "Pending professional engineer review"
            if not ((latest_pkg or {}).get("signed_by")
                    or (latest_signature or {}).get("status") == "signed")
            else "Signed record on file.",
        },
    ]

    ready = all(item["ready"] for item in checklist)
    audit.log_action("sbc304_readiness_viewed", project_id=project_id,
                     details={"ready": ready})
    return {
        "project_id": project_id,
        "ready": ready,
        "status": "READY FOR ENGINEER REVIEW" if ready
        else "PENDING — items outstanding",
        "checks": checklist,
    }


@router.post("/signature/request", summary="Approve & sign — request engineer signature")
async def signature_request(payload: SignatureRequestBody) -> Dict[str, Any]:
    if payload.actor_role not in SIGNING_ROLES:
        raise HTTPException(status_code=403,
                            detail="Only licensed engineers may request signatures.")
    stamped = _stamped_review_pdf(payload.engineer_name, payload.license_number,
                                  payload.provider)
    record = _signatures.put({
        **payload.model_dump(),
        "status": "requested",
        "pdf_path": stamped,
        "signed_at": None,
    }, prefix="sig")
    audit.log_action("signature_requested", actor_role=payload.actor_role,
                     project_id=payload.project_id,
                     details={"signature_id": record["id"],
                              "engineer": payload.engineer_name})
    return record


@router.get("/signature/{signature_id}", summary="Signature request status")
async def signature_status(signature_id: str) -> Dict[str, Any]:
    record = _signatures.get(signature_id)
    if not record:
        raise HTTPException(status_code=404, detail="Signature request not found.")
    return record


@router.post("/signature/{signature_id}/complete",
             summary="Webhook completion from the e-sign provider (placeholder)")
async def signature_complete(signature_id: str, body: SignatureCompleteBody) -> Dict[str, Any]:
    existing = _signatures.get(signature_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Signature request not found.")
    updated = _signatures.update(
        signature_id, status=body.outcome,
        signed_at=now_iso() if body.outcome == "signed" else None,
        notes=body.notes)
    audit.log_action("signature_completed", details={
        "signature_id": signature_id, "outcome": body.outcome})
    return updated


@router.get("/submission/{ref}",
            summary="List a project's submissions (numeric project id) "
                    "or get one submission's details (submission id)")
async def submission_ref(ref: str) -> Dict[str, Any]:
    """Dual-mode per the roadmap #16 contract.

    ``/submission/{project_id}`` (digits) lists that project's packages,
    newest first; ``/submission/{submission_id}`` returns one record.
    One route avoids FastAPI's int-conversion 422 shadowing the string-id
    form (routes are matched in order and never fall through).
    """
    if ref.isdigit():
        project_id = int(ref)
        docs = _submissions.list(lambda d: d.get("project_id") == project_id)
        docs.sort(key=lambda d: str(d.get("created_at", "")), reverse=True)
        return {"project_id": project_id, "packages": docs, "submissions": docs}

    doc = _submissions.get(ref)
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return doc


@router.post("/submission/{submission_id}/status",
             summary="Record a submission status transition (municipality tracking)")
async def submission_transition(
    submission_id: str, body: SubmissionStatusBody,
) -> Dict[str, Any]:
    """Append an auditable tracking event and update the record's status.

    Data-driven only: the caller supplies the real-world outcome (submitted,
    under review, approved, revision required, rejected, signed). Nothing is
    inferred about the municipality's decision.
    """
    doc = _submissions.get(submission_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found.")

    event = {
        "status": body.status,
        "at": now_iso(),
        "notes": body.notes,
        "authority": body.authority,
        "reference_number": body.reference_number,
    }
    tracking = list(doc.get("tracking") or []) + [event]
    updated = _submissions.update(
        submission_id, status=body.status, tracking=tracking)
    audit.log_action("submission_status_changed",
                     project_id=doc.get("project_id"),
                     details={"submission_id": submission_id,
                              "status": body.status,
                              "reference_number": body.reference_number})
    return updated


@router.post("/submission/generate", summary="Build a municipality-ready submission PDF")
async def submission_generate(payload: ComplianceRequest,
                              signed_by: Optional[str] = None) -> Dict[str, Any]:
    """Combine calculation note, compliance report and project info into one PDF."""
    plan = _resolve_plan(payload.plan_name, payload.plan)
    report = ComplianceEngine(plan, analysis=payload.analysis,
                              survey=payload.survey).run_all()
    try:
        boq = generate_boq(plan, project_name=f"Project {payload.project_id}")
    except Exception as exc:  # BOQ is supplementary — never block submission
        log.warning("Submission BOQ skipped: %s", exc)
        boq = None

    sections = [("Compliance results", [[
        "Check", "Clause", "Status", "Detail"
    ]] + [[c.get("check_name"), (c.get("details") or {}).get("clause", ""),
          c.get("status"),
          (c.get("details") or {}).get("note")
          or (c.get("details") or {}).get("message", "")]
         for c in report.get("checks", [])],
        f"{report.get('summary', {}).get('passed', 0)} passed · "
        f"{report.get('summary', {}).get('failed', 0)} failed · "
        f"{report.get('summary', {}).get('warned', 0)} warnings."),
    ]
    if boq:
        totals = boq.get("totals") or {}
        sections.append(("Preliminary BOQ totals",
                         [["Metric", "Value"],
                          ["Total estimate (USD)", totals.get("amount_usd", "N/A")],
                          ["Cost / m² (USD)", totals.get("amount_per_m2", "N/A")],
                          ["Rebar (kg)", totals.get("rebar_kg", "N/A")]],
                         None))

    path = exports_dir() / f"submission-p{payload.project_id}-{_stamp_slug()}.pdf"
    build_pdf_report(
        path,
        title="Municipality Submission Package",
        subtitle=str(payload.project_id),
        meta_rows=[
            ["Code basis", report.get("code_name", "SBC 304")],
            ["Signed by", signed_by or "— pending signature —"],
            ["Generated", now_iso()],
        ],
        summary_box={
            "Checks passed": report.get("summary", {}).get("passed", 0),
            "Checks failed": report.get("summary", {}).get("failed", 0),
            "Warnings": report.get("summary", {}).get("warned", 0),
        },
        sections=sections,
        chart_drawing=None,
    )
    record = _submissions.put({
        "project_id": payload.project_id,
        "file_path": str(path),
        "status": "signed" if signed_by else "generated",
        "tracking": [],
        "contents": ["calculation_note", "compliance_report"]
                    + (["boq_summary"] if boq else []),
        "signed_by": signed_by,
        "compliance_check_id": None,
    }, prefix="sub")
    audit.log_action("submission_generated", project_id=payload.project_id,
                     details={"package_id": record["id"], "path": str(path)})
    return record


@router.get("/audit-log/{project_id}", summary="Immutable audit trail (read-only)")
async def audit_trail(project_id: int, limit: int = 200) -> Dict[str, Any]:
    entries = audit.list_log(project_id=project_id, limit=min(limit, 1000))
    integrity = audit.verify_chain()
    return {"project_id": project_id, "entries": entries,
            "integrity": integrity}


def _resolve_plan(plan_name: Optional[str], plan_dict: Optional[Dict[str, Any]]):
    """Shared plan resolution: inline dict wins, else load a saved plan."""
    if plan_dict:
        from app.models.plan_data import PlanData

        try:
            return PlanData(**plan_dict)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid plan: {exc}") from exc
    if plan_name:
        try:
            return PlanGenerator.load_plan(1, plan_name)
        except PlanGenerationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail="Provide 'plan' or 'plan_name'.")


def _stamped_review_pdf(engineer_name: str, license_number: str,
                        provider: str) -> str:
    """Render the sealed review document (e-sign provider placeholder)."""
    path = exports_dir() / f"review-seal-{_stamp_slug()}.pdf"
    provider_label = {
        "internal_seal": "Imad Internal e-Seal",
        "docusign": "DocuSign (sandbox)",
        "adobe_sign": "Adobe Sign (sandbox)",
    }.get(provider, provider)
    build_pdf_report(
        path,
        title="Engineering Review & Digital Seal",
        subtitle="Design review certificate — Imad Autonomous Engineering Engine",
        meta_rows=[
            ["Engineer", engineer_name],
            ["License no.", license_number],
            ["Signing provider", provider_label],
            ["Sealed at", now_iso()],
        ],
        summary_box={"Review status": "APPROVED & SIGNED",
                     "Code basis": "SBC 304 / ACI 318-19"},
        sections=[(
            "Reviewer declaration",
            [["#", "Statement"],
             ["1", "The structural design has been reviewed against the applicable code."],
             ["2", "Compliance checks were executed by the Imad compliance engine."],
             ["3", "The signer accepts professional responsibility for this submission."]],
            "This document carries the engineer's digital seal. Verify authenticity "
            "via the Imad audit chain before relying on it.",
        )],
    )
    return str(path)


def _stamp_slug() -> str:
    import secrets

    return secrets.token_hex(4)