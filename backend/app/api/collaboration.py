"""Sprint 12 — BIM interoperability, collaboration & lightweight PM.

IFC export/import · BCF issues · comments · markups · approval workflow
(draft → under_review → approved/rejected) · kanban tasks · notifications ·
webhooks for external plugins (Revit/AutoCAD scaffolding).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core import audit
from app.core.docstore import collection
from app.models.business import ApprovalState
from app.models.plan_data import PlanData
from app.services import bim_service
from app.services.bim_service import BIMError
from app.services.noncad_processor import PlanGenerationError, PlanGenerator

log = logging.getLogger("imad.api.collab")
router = APIRouter()


def docstore_now() -> str:
    """ISO timestamp used across collaboration history entries."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "draft": ["under_review"],
    "under_review": ["approved", "rejected"],
    "approved": [],
    "rejected": ["draft", "under_review"],
}


# ── IFC ───────────────────────────────────────────────────────────────────────
class IfcExportRequest(BaseModel):
    project_id: int = 1
    plan_name: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None


@router.post("/ifc/export", summary="Export a plan as an IFC4 STEP file")
async def ifc_export(payload: IfcExportRequest):
    try:
        plan = (PlanData(**payload.plan) if payload.plan
                else PlanGenerator.load_plan(payload.project_id, payload.plan_name or ""))
    except (PlanGenerationError, Exception) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot resolve plan: {exc}") from exc
    name = payload.plan_name or f"project-{payload.project_id}"
    try:
        path = bim_service.export_ifc_file(plan, project_name=name)
    except BIMError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    audit.log_action("ifc_export", project_id=payload.project_id,
                     details={"path": str(path)})
    return FileResponse(path, media_type="application/x-step",
                        filename=path.replace("\\", "/").split("/")[-1])


@router.post("/ifc/import", summary="Import an IFC file and extract structural elements")
async def ifc_import(file: UploadFile = File(...)):
    from app.core.storage import save_bytes

    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="IFC file exceeds 20 MB limit.")
    suffix = (file.filename or "model.ifc").lower().rsplit(".", 1)[-1]
    if suffix not in {"ifc"}:
        raise HTTPException(status_code=415, detail="Only .ifc files are supported.")
    path = save_bytes(raw, file.filename or "model.ifc")
    try:
        plan = bim_service.import_ifc(str(path))
    except BIMError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log_action("ifc_import", details={"file": file.filename})
    return {"plan": json.loads(plan.model_dump_json()),
            "counts": {"walls": len(plan.walls), "columns": len(plan.columns),
                       "beams": len(plan.beams)}}


# ── BCF-style issues ────────────────────────────────────────────────────────
class IssueCreate(BaseModel):
    project_id: int = 1
    title: str
    body: str = ""
    author: str = ""
    element_ref: str = ""
    position: Optional[List[float]] = None


@router.get("/bcf/issues", summary="List BCF coordination issues")
async def issues_list(project_id: int = 1, status: Optional[str] = None):
    return {"issues": bim_service.list_issues(project_id, status)}


@router.post("/bcf/issues", summary="Open a BCF coordination issue")
async def issues_create(payload: IssueCreate):
    issue = bim_service.create_issue(
        payload.project_id, payload.title, payload.body, payload.author,
        payload.element_ref, payload.position)
    audit.log_action("bcf_issue_created", project_id=payload.project_id,
                     details={"title": payload.title})
    return issue


@router.patch("/bcf/issues/{issue_id}", summary="Update issue status/fields")
async def issues_update(issue_id: str, body: Dict[str, Any]):
    updated = bim_service.update_issue(issue_id, **body)
    if not updated:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return updated


# ── Comments ─────────────────────────────────────────────────────────────────
class CommentCreate(BaseModel):
    project_id: int = 1
    target_kind: str = "result"
    target_id: str = ""
    author: str
    body: str


@router.get("/comments", summary="List comments for a project/target")
async def comments_list(project_id: int = 1, target_id: Optional[str] = None):
    docs = collection("comments").list(lambda d: d.get("project_id") == project_id)
    if target_id:
        docs = [d for d in docs if d.get("target_id") == target_id]
    return {"comments": sorted(docs, key=lambda d: d.get("created_at", ""))}


@router.post("/comments", summary="Add a comment")
async def comments_create(payload: CommentCreate):
    doc = collection("comments").put(payload.model_dump(), prefix="cmt")
    audit.log_action("comment_added", project_id=payload.project_id)
    return doc


@router.patch("/comments/{comment_id}/resolve", summary="Mark comment resolved")
async def comments_resolve(comment_id: str):
    doc = collection("comments").update(comment_id, resolved=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Comment not found.")
    return doc


# ── Approvals (draft → under_review → approved/rejected) ────────────────────
class ApprovalCreate(BaseModel):
    project_id: int = 1
    subject_kind: str = "design_result"
    subject_id: str
    reviewer: str = ""


class ApprovalTransition(BaseModel):
    state: ApprovalState
    actor: str = ""


@router.get("/approvals", summary="List approval workflows")
async def approvals_list(project_id: int = 1):
    docs = collection("approvals").list(lambda d: d.get("project_id") == project_id)
    return {"approvals": docs}


@router.post("/approvals", summary="Start an approval workflow", status_code=201)
async def approvals_create(payload: ApprovalCreate):
    existing = collection("approvals").list(
        lambda d: d.get("subject_id") == payload.subject_id
        and d.get("subject_kind") == payload.subject_kind)
    if existing:
        return existing[0]
    doc = collection("approvals").put({
        **payload.model_dump(),
        "state": "draft",
        "history": [{"state": "draft", "actor": payload.reviewer or "system",
                     "at": docstore_now()}],
    }, prefix="apr")
    return doc


@router.post("/approvals/{approval_id}/transition", summary="Move approval to next state")
async def approvals_transition(approval_id: str, payload: ApprovalTransition):
    doc = collection("approvals").get(approval_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Approval not found.")
    current = doc.get("state", "draft")
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if payload.state not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Illegal transition {current} → {payload.state}. Allowed: {allowed}")
    history = doc.get("history", []) + [{
        "state": payload.state, "actor": payload.actor or "system",
        "at": docstore_now()}]
    updated = collection("approvals").update(
        approval_id, state=payload.state, history=history,
        reviewer=payload.actor or doc.get("reviewer", ""))
    # Notification for the interested parties.
    collection("notifications").put({
        "project_id": doc.get("project_id"),
        "kind": "approval",
        "message": f"Approval {approval_id} moved to '{payload.state}'",
    }, prefix="ntf")
    audit.log_action("approval_transition", project_id=doc.get("project_id"),
                     details={"to": payload.state})
    return updated


# ── Tasks (lightweight kanban) ───────────────────────────────────────────────
TASK_STATES = ("backlog", "in_progress", "review", "done")


class TaskCreate(BaseModel):
    project_id: int = 1
    title: str
    assignee: str = ""
    state: str = "backlog"
    priority: str = "medium"
    due: Optional[str] = None


class TaskMove(BaseModel):
    state: str
    order: int = 0


@router.get("/tasks", summary="List project tasks for the kanban board")
async def tasks_list(project_id: int = 1):
    docs = collection("tasks").list(lambda d: d.get("project_id") == project_id)
    docs.sort(key=lambda d: (d.get("order", 0), d.get("created_at", "")))
    return {"tasks": docs, "states": list(TASK_STATES)}


@router.post("/tasks", summary="Create a task", status_code=201)
async def tasks_create(payload: TaskCreate):
    if payload.state not in TASK_STATES:
        raise HTTPException(status_code=422,
                            detail=f"state must be one of {TASK_STATES}")
    doc = collection("tasks").put(payload.model_dump(), prefix="tsk")
    collection("notifications").put({
        "project_id": payload.project_id, "kind": "task",
        "message": f"New task: {payload.title}"}, prefix="ntf")
    return doc


@router.patch("/tasks/{task_id}/move", summary="Drag-and-drop move between states")
async def tasks_move(task_id: str, payload: TaskMove):
    if payload.state not in TASK_STATES:
        raise HTTPException(status_code=422,
                            detail=f"state must be one of {TASK_STATES}")
    doc = collection("tasks").update(task_id, state=payload.state,
                                     order=payload.order)
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found.")
    return doc


@router.delete("/tasks/{task_id}", summary="Delete a task")
async def tasks_delete(task_id: str):
    if not collection("tasks").delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"deleted": task_id}


# ── Notifications ────────────────────────────────────────────────────────────
@router.get("/notifications", summary="List notifications (newest first)")
async def notifications_list(project_id: Optional[int] = None, unread_only: bool = False):
    docs = collection("notifications").list()
    if project_id is not None:
        docs = [d for d in docs if d.get("project_id") in (None, project_id)]
    if unread_only:
        docs = [d for d in docs if not d.get("read")]
    return {"notifications": sorted(docs, key=lambda d: d.get("created_at", ""),
                                    reverse=True)[:100]}


@router.post("/notifications/{notification_id}/read",
             summary="Mark a notification as read")
async def notifications_read(notification_id: str):
    doc = collection("notifications").update(notification_id, read=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return doc


# ── Webhooks (Revit/AutoCAD plugin scaffolding) ──────────────────────────────
class WebhookCreate(BaseModel):
    url: str
    events: List[str] = ["analysis.completed"]
    secret_hint: str = ""


@router.get("/webhooks", summary="List registered plugin webhooks")
async def webhooks_list():
    docs = collection("webhooks").list()
    # Never expose raw secrets through the API.
    return {"webhooks": [{k: v for k, v in d.items() if k != "secret"} for d in docs]}


@router.post("/webhooks", summary="Register a webhook for external integrations",
             status_code=201)
async def webhooks_create(payload: WebhookCreate):
    if not payload.url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="url must be http(s).")
    import secrets as _secrets

    secret = _secrets.token_hex(16)
    doc = collection("webhooks").put({
        "url": payload.url,
        "events": payload.events,
        "secret": secret,
        "secret_hint": payload.secret_hint,
        "active": True,
    }, prefix="whk")
    audit.log_action("webhook_registered", details={"url": payload.url})
    # The raw signing secret is shown exactly once, at creation time.
    return {k: v for k, v in doc.items() if k != "secret"} | {"signing_secret": secret}


@router.delete("/webhooks/{webhook_id}", summary="Remove a webhook")
async def webhooks_delete(webhook_id: str):
    if not collection("webhooks").delete(webhook_id):
        raise HTTPException(status_code=404, detail="Webhook not found.")
    return {"deleted": webhook_id}


async def fire_webhooks(event: str, payload: Dict[str, Any]) -> int:
    """Best-effort fan-out of an event to registered webhooks.

    Used by other modules (analysis, BOQ) to notify plugins; failures are
    logged and never raised so background jobs stay healthy.
    """
    import httpx

    subs = collection("webhooks").list(
        lambda d: d.get("active") and event in (d.get("events") or []))
    delivered = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sub in subs:
            try:
                await client.post(sub["url"], json={"event": event, "data": payload},
                                  headers={"X-Imad-Event": event})
                delivered += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("Webhook %s delivery failed: %s", sub.get("id"), exc)
    return delivered