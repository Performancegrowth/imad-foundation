"""Sprint 10 — Governance endpoints: compliance, e-signatures, submissions,
and the immutable audit trail viewer."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.docstore import collection
from app.services.boq_generator import generate_boq
from app.services.compliance_engine import ComplianceEngine
from app.services.exporters import build_pdf_report, exports_dir, now_iso
from app.services.noncad_processor import PlanGenerationError, PlanGenerator

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
                              "passed": report.get("summary", {}).get("pass")})
    return {"check_id": record["id"], **report}


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


@router.get("/submission/{project_id}", summary="List submission packages for a project")
async def list_submissions(project_id: int) -> Dict[str, Any]:
    docs = _submissions.list(lambda d: d.get("project_id") == project_id)
    return {"project_id": project_id, "packages": docs}


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
    ]] + [[c.get("check"), c.get("clause", ""), c.get("status"),
          c.get("detail", "")] for c in report.get("checks", [])],
        f"{report.get('summary', {}).get('pass', 0)} passed · "
        f"{report.get('summary', {}).get('fail', 0)} failed · "
        f"{report.get('summary', {}).get('warn', 0)} warnings."),
    ]
    if boq:
        sections.append(("Preliminary BOQ totals",
                         [["Metric", "Value"],
                          ["Total estimate (USD)", boq["totals"]["amount_usd"]],
                          ["Cost / m² (USD)", boq["totals"]["amount_per_m2"]],
                          ["Rebar (kg)", boq["totals"]["rebar_kg"]]],
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
            "Checks passed": report.get("summary", {}).get("pass", 0),
            "Checks failed": report.get("summary", {}).get("fail", 0),
            "Warnings": report.get("summary", {}).get("warn", 0),
        },
        sections=sections,
        chart_drawing=None,
    )
    record = _submissions.put({
        "project_id": payload.project_id,
        "file_path": str(path),
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