"""Sprint 9C/14 — Subscriptions, billing, API keys, white-label, analytics."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core import audit
from app.services.subscriptions import (
    PLANS,
    ROLE_MATRIX,
    SubscriptionError,
    create_checkout_placeholder,
    get_subscription,
    upgrade,
)

log = logging.getLogger("imad.api.billing")
router = APIRouter()


class UpgradeRequest(BaseModel):
    user_email: str
    plan: str
    cycle: str = "monthly"


class CheckoutRequest(BaseModel):
    user_email: str
    plan: str
    cycle: str = "monthly"


class ApiKeyRequest(BaseModel):
    user_email: str = ""
    name: str = "default"
    scopes: List[str] = Field(default_factory=lambda: ["read", "analyze"])


@router.get("/plans", summary="Plan catalogue with the entitlement matrix")
async def list_plans() -> Dict[str, Any]:
    return {"plans": PLANS, "roles": ROLE_MATRIX}


@router.get("/subscriptions/{user_email}", summary="Fetch or provision a subscription")
async def subscription(user_email: str) -> Dict[str, Any]:
    sub = get_subscription(user_email)
    plan = PLANS.get(sub["plan"], PLANS["free"])
    return {"subscription": sub, "plan": plan}


@router.post("/subscriptions/upgrade", summary="Switch plan (Stripe capture is a placeholder)")
async def do_upgrade(payload: UpgradeRequest) -> Dict[str, Any]:
    try:
        sub = upgrade(payload.user_email, payload.plan, payload.cycle)
    except SubscriptionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log_action("subscription_upgraded",
                     details={"plan": payload.plan, "cycle": payload.cycle})
    return {"subscription": sub, "plan": PLANS[payload.plan]}


@router.post("/payments/checkout", summary="Create a Stripe *sandbox* checkout session")
async def checkout(payload: CheckoutRequest) -> Dict[str, Any]:
    try:
        session = create_checkout_placeholder(payload.user_email, payload.plan, payload.cycle)
    except SubscriptionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log_action("checkout_created", details={"plan": payload.plan})
    return session


@router.post("/payments/webhook", include_in_schema=False,
             summary="Stripe webhook placeholder (signature verification TODO)")
async def payments_webhook(request: Request,
                           x_signature: str = Header(default="")) -> Dict[str, Any]:
    body = await request.body()
    # TODO(S9C): stripe.Webhook.construct_event(body, sig, STRIPE_WEBHOOK_SECRET)
    log.info("Stripe webhook placeholder received (%d bytes, signed=%s)",
             len(body), bool(x_signature))
    audit.log_action("payment_webhook", details={"bytes": len(body), "mode": "sandbox"})
    return {"received": True, "mode": "sandbox"}


# ── Sprint 14 — API keys ─────────────────────────────────────────────────────
def _hash_key(raw: str) -> str:
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.post("/api-keys/generate", summary="Issue an API key (shown once)")
async def generate_api_key(payload: ApiKeyRequest) -> Dict[str, Any]:
    import secrets as _secrets

    from app.core.docstore import collection

    raw = f"imad_live_{_secrets.token_hex(16)}"
    store = collection("apikeys")
    doc = store.put({
        "user_email": payload.user_email,
        "name": payload.name,
        "prefix": raw[:14],
        "key_hash": _hash_key(raw),
        "scopes": payload.scopes,
        "revoked": False,
    }, prefix="key")
    audit.log_action("api_key_generated",
                     details={"key_id": doc["id"], "scopes": payload.scopes})
    # The raw key is returned exactly once; only its hash is persisted.
    return {"key_id": doc["id"], "name": doc["name"], "prefix": doc["prefix"],
            "scopes": doc["scopes"], "api_key": raw}


@router.get("/api-keys/{user_email}", summary="List API keys (metadata only)")
async def list_api_keys(user_email: str) -> Dict[str, Any]:
    from app.core.docstore import collection

    rows = collection("apikeys").list(
        lambda d: d.get("user_email") == user_email)
    return [{"key_id": r["id"], "name": r["name"], "prefix": r["prefix"],
             "scopes": r["scopes"], "revoked": r.get("revoked", False),
             "created_at": r.get("created_at")} for r in rows]


@router.delete("/api-keys/{key_id}", summary="Revoke an API key")
async def revoke_api_key(key_id: str) -> Dict[str, Any]:
    from app.core.docstore import collection

    doc = collection("apikeys").update(key_id, revoked=True)
    if not doc:
        raise HTTPException(status_code=404, detail="API key not found.")
    audit.log_action("api_key_revoked", details={"key_id": key_id})
    return {"revoked": True, "key_id": key_id}


# ── Sprint 14 — white-label ──────────────────────────────────────────────────
class WhiteLabelPayload(BaseModel):
    org_name: str = "Imad"
    logo_url: str = ""
    primary_color: str = "#0A5C36"
    accent_color: str = "#C9A227"
    custom_domain: str = ""
    enabled: bool = False


def _wl_id(user_email: str) -> str:
    import hashlib as _hl

    return "wl_" + _hl.sha256(user_email.encode("utf-8")).hexdigest()[:12]


@router.get("/whitelabel/{user_email}", summary="Fetch white-label settings")
async def get_whitelabel(user_email: str) -> Dict[str, Any]:
    from app.core.docstore import collection

    doc = collection("whitelabels").get(_wl_id(user_email))
    if not doc:
        return WhiteLabelPayload().model_dump()
    return {k: v for k, v in doc.items()
            if k in WhiteLabelPayload().model_dump().keys()}


@router.put("/whitelabel/{user_email}", summary="Update white-label settings")
async def put_whitelabel(user_email: str, payload: WhiteLabelPayload) -> Dict[str, Any]:
    from app.core.docstore import collection

    doc = collection("whitelabels").put(
        {"id": _wl_id(user_email), "user_email": user_email,
         **payload.model_dump()}, prefix="wl")
    audit.log_action("whitelabel_updated",
                     details={"org": payload.org_name, "enabled": payload.enabled})
    return {k: v for k, v in doc.items()
            if k in WhiteLabelPayload().model_dump().keys()}


# ── Sprint 9C — business analytics ───────────────────────────────────────────
@router.get("/analytics", summary="Platform analytics: projects, users, revenue")
async def analytics() -> Dict[str, Any]:
    """Aggregates live counters from the document stores + audit trail."""
    from app.core.docstore import collection
    from app.services.subscriptions import PLANS

    subs = collection("subscriptions").list()
    plan_counts: Dict[str, int] = {}
    mrr_usd = 0.0
    for s in subs:
        code = s.get("plan", "free")
        plan_counts[code] = plan_counts.get(code, 0) + 1
        price = float(PLANS.get(code, {}).get("price_monthly", 0))
        if s.get("cycle") == "yearly":
            price = float(PLANS.get(code, {}).get("price_yearly", price * 12)) / 12
        mrr_usd += price

    snapshots = collection("design_snapshots").list()
    total_projects = max(len({s.get("project_id") for s in subs}) , 1)
    users = len({s.get("user_email") for s in subs}) or 1

    series = []
    for code, meta in PLANS.items():
        count = plan_counts.get(code, 0)
        if count or code == "free":
            series.append({"label": meta.get("name", code),
                           "value": round(price_of(code) * count, 2)})
    return {
        "projects_total": total_projects,
        "users_total": users,
        "subscriptions": plan_counts,
        "mrr_usd": round(mrr_usd, 2),
        "arr_usd": round(mrr_usd * 12, 2),
        "snapshots_collected": len(snapshots),
        "revenue_by_plan": [s for s in series if s["value"] > 0],
    }


def price_of(code: str) -> float:
    return float(PLANS.get(code, {}).get("price_monthly", 0))