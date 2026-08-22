"""Business & governance domain models (Sprints 9–13).

Pydantic contracts mirroring ``database/schema.sql`` additions. Persistence is
handled by :mod:`app.core.docstore`; these models define validation + shapes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ── Sprint 10 — governance ────────────────────────────────────────────────
SignatureStatus = Literal["draft", "requested", "signed", "rejected", "expired"]


class SignatureRequest(BaseModel):
    design_id: str
    project_id: int = 1
    engineer_name: str
    license_number: str
    provider: Literal["internal_seal", "docusign", "adobe_sign"] = "internal_seal"
    status: SignatureStatus = "requested"
    pdf_path: str = ""
    signed_at: Optional[str] = None
    notes: str = ""


class ComplianceCheckResult(BaseModel):
    design_id: str
    code_name: str = "SBC 304"          # Saudi Building Code — concrete
    check_name: str
    status: Literal["pass", "fail", "warn"]
    details: Dict[str, Any] = Field(default_factory=dict)


class SubmissionPackageRecord(BaseModel):
    project_id: int = 1
    file_path: str
    contents: List[str] = Field(default_factory=list)
    signed_by: Optional[str] = None
    municipality: str = "Riyadh Municipality"


# ── Sprint 12 — collaboration ───────────────────────────────────────────────
ApprovalState = Literal["draft", "under_review", "approved", "rejected"]


class Comment(BaseModel):
    project_id: int = 1
    target_kind: Literal["plan", "result", "option", "drawing"] = "result"
    target_id: str = ""
    author: str
    body: str = Field(min_length=1, max_length=4000)
    resolved: bool = False


class Markup(BaseModel):
    project_id: int = 1
    level: int = 0
    kind: Literal["pin", "rect", "freehand"] = "pin"
    points: List[List[float]] = Field(default_factory=list)
    color: str = "#C9A227"
    note: str = ""
    author: str = ""


class Approval(BaseModel):
    project_id: int = 1
    subject_kind: Literal["design_result", "submission", "boq"] = "design_result"
    subject_id: str
    state: ApprovalState = "draft"
    reviewer: str = ""
    history: List[Dict[str, Any]] = Field(default_factory=list)


TaskState = Literal["backlog", "in_progress", "review", "done"]


class TaskItem(BaseModel):
    project_id: int = 1
    title: str
    assignee: str = ""
    state: TaskState = "backlog"
    priority: Literal["low", "medium", "high"] = "medium"
    due: Optional[str] = None
    order: int = 0


class Notification(BaseModel):
    user_email: str = ""
    project_id: Optional[int] = None
    kind: Literal["info", "approval", "task", "job", "system"] = "info"
    message: str
    read: bool = False


class WebhookSubscription(BaseModel):
    url: str
    events: List[str] = Field(default_factory=lambda: ["analysis.completed"])
    secret_hint: str = ""                # never store the raw secret client-side
    active: bool = True


# ── Sprint 13 — ecosystem / marketplace ─────────────────────────────────────
class DesignDataSnapshot(BaseModel):
    """Anonymised design fingerprint — no client names/addresses ever stored."""
    region_code: str = ""                # hashed region, not address
    stories: int = 1
    footprint_m2: float = 0
    concrete_m3: float = 0
    rebar_kg: float = 0
    carbon_kgco2e: float = 0
    cost_usd: float = 0
    slab_type: str = "flat"
    avg_bay_m: float = 0
    source_hash: str = ""


class CostRecord(BaseModel):
    region: str
    item_code: str                       # e.g. CONC-C30, REBAR-B500, FORM-SLAB
    description: str = ""
    unit: Literal["m3", "kg", "tonne", "m2", "m", "item"]
    unit_cost: float = Field(ge=0)
    currency: str = "USD"
    valid_from: str = ""
    valid_to: str = ""
    source: str = "manual"


class Supplier(BaseModel):
    company: str
    categories: List[str] = Field(default_factory=lambda: ["concrete"])
    region: str = ""
    contact_email: str = ""
    rating: float = Field(default=0, ge=0, le=5)
    verified: bool = False               # placeholder for future vetting flow


class Consultant(BaseModel):
    name: str
    license_number: str
    specialties: List[str] = Field(default_factory=lambda: ["concrete design"])
    regions: List[str] = Field(default_factory=list)
    review_rate_usd: float = 0
    available: bool = True


class ConsultantReviewRequest(BaseModel):
    consultant_id: str
    project_id: int = 1
    scope: str = "Full structural review + stamp"
    status: Literal["pending", "accepted", "completed", "declined"] = "pending"


class Certification(BaseModel):
    user_email: str
    level: Literal["associate", "professional", "expert"] = "associate"
    score: float = Field(ge=0, le=100)
    passed: bool = False
    certificate_id: str = ""
    expires_at: Optional[str] = None


# ── Sprint 14 — platform ─────────────────────────────────────────────────────
RoleName = Literal["owner", "admin", "engineer", "reviewer", "viewer"]


class ApiKey(BaseModel):
    name: str
    prefix: str = ""                     # shown to the user: imad_live_ab12…
    key_hash: str = ""                   # sha256 of full key
    scopes: List[str] = Field(default_factory=lambda: ["read", "analyze"])
    revoked: bool = False


class WhiteLabelSettings(BaseModel):
    org_name: str = "Imad"
    logo_url: str = ""
    primary_color: str = "#0A5C36"
    accent_color: str = "#C9A227"
    custom_domain: str = ""
    enabled: bool = False


__all__ = [
    "SignatureRequest", "SignatureStatus", "ComplianceCheckResult",
    "SubmissionPackageRecord", "Comment", "Markup", "Approval", "ApprovalState",
    "TaskItem", "TaskState", "Notification", "WebhookSubscription",
    "DesignDataSnapshot", "CostRecord", "Supplier", "Consultant",
    "ConsultantReviewRequest", "Certification", "ApiKey", "WhiteLabelSettings",
    "RoleName",
]