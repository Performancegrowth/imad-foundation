"""
Sprint 9C / 14 — Subscription & monetisation layer.

Plan catalogue, entitlement matrix and quota enforcement. Payment capture is
a Stripe *placeholder*: ``create_checkout_placeholder`` returns a sandbox
payload so the UI wires up today and the real SDK drops in later without
API changes.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger("imad.subscriptions")

PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free", "price_month": 0, "price_year": 0,
        "tagline": "Evaluate Imad on a single project.",
        "limits": {"projects": 1, "stories": 2},
        "features": {
            "cad_import": True, "plan_editor": True, "survey": True,
            "structural_analysis": False,
            "generative_design": False,
            "boq": False, "pdf_export": False, "excel_export": False,
            "three_d": True, "watermark_3d": True,
            "api_access": False, "white_label": False,
        },
    },
    "pay_per_project": {
        "name": "Pay-Per-Project", "price_month": 99, "price_year": 950,
        "tagline": "$99 per project — for one-off submissions.",
        "limits": {"projects": 3, "stories": 10},
        "features": {
            "cad_import": True, "plan_editor": True, "survey": True,
            "structural_analysis": True, "generative_design": True,
            "boq": True, "pdf_export": True, "excel_export": True,
            "three_d": True, "watermark_3d": False,
            "api_access": False, "white_label": False,
        },
    },
    "office": {
        "name": "Office", "price_month": 299, "price_year": 2870,
        "tagline": "For engineering offices — unlimited projects.",
        "limits": {"projects": 999, "stories": 40},
        "features": {
            "cad_import": True, "plan_editor": True, "survey": True,
            "structural_analysis": True, "generative_design": True,
            "boq": True, "pdf_export": True, "excel_export": True,
            "three_d": True, "watermark_3d": False,
            "api_access": True, "white_label": False,
        },
    },
    "enterprise": {
        "name": "Enterprise", "price_month": 999, "price_year": 9590,
        "tagline": "White-label, SSO, dedicated support and SLAs.",
        "limits": {"projects": 99999, "stories": 120},
        "features": {
            "cad_import": True, "plan_editor": True, "survey": True,
            "structural_analysis": True, "generative_design": True,
            "boq": True, "pdf_export": True, "excel_export": True,
            "three_d": True, "watermark_3d": False,
            "api_access": True, "white_label": True,
        },
    },
}

# Role-based permission matrix (Sprint 14 RBAC).
ROLE_MATRIX: Dict[str, Dict[str, bool]] = {
    "owner":    {"manage_billing": True, "manage_users": True, "sign": True,
                 "approve": True, "edit": True, "run_analysis": True, "export": True},
    "admin":    {"manage_billing": False, "manage_users": True, "sign": False,
                 "approve": True, "edit": True, "run_analysis": True, "export": True},
    "engineer": {"manage_billing": False, "manage_users": False, "sign": True,
                 "approve": False, "edit": True, "run_analysis": True, "export": True},
    "reviewer": {"manage_billing": False, "manage_users": False, "sign": False,
                 "approve": True, "edit": False, "run_analysis": True, "export": True},
    "viewer":   {"manage_billing": False, "manage_users": False, "sign": False,
                 "approve": False, "edit": False, "run_analysis": False, "export": False},
}

ANNUAL_DISCOUNT_PCT = 20


class SubscriptionError(Exception):
    """Raised when an action violates plan entitlements."""


def plan_catalogue() -> List[Dict[str, Any]]:
    out = []
    for key, p in PLANS.items():
        out.append({
            "id": key, "name": p["name"],
            "price_month": p["price_month"], "price_year": p["price_year"],
            "annual_discount_pct": ANNUAL_DISCOUNT_PCT if p["price_year"] else 0,
            "tagline": p["tagline"], "features": p["features"],
            "limits": p["limits"],
        })
    return out


def get_subscription(user_email: str) -> Dict[str, Any]:
    from app.core.docstore import collection

    subs = collection("subscriptions")
    existing = next((s for s in subs.list(
        lambda d: d.get("user_email") == user_email)), None)
    if existing:
        return existing
    return subs.put({
        "id": f"sub_{secrets.token_hex(4)}",
        "user_email": user_email,
        "plan": "free",
        "status": "active",
        "projects_used": 1,
        "billing_cycle": "monthly",
        "stripe_customer_id": None,       # set by payment webhook later
    }, prefix="sub")


def require_feature(user_email: str, feature: str) -> Dict[str, Any]:
    """Raise SubscriptionError when the plan excludes ``feature``."""
    sub = get_subscription(user_email)
    plan = PLANS.get(sub["plan"], PLANS["free"])
    if not plan["features"].get(feature, False):
        raise SubscriptionError(
            f"'{feature}' is not included in the {plan['name']} plan. "
            "Upgrade to unlock it.")
    return sub


def upgrade(user_email: str, plan_id: str, cycle: str = "monthly") -> Dict[str, Any]:
    if plan_id not in PLANS:
        raise SubscriptionError(f"Unknown plan '{plan_id}'.")
    if cycle not in ("monthly", "annual"):
        raise SubscriptionError("Cycle must be monthly or annual.")
    from app.core.docstore import collection

    sub = get_subscription(user_email)
    sub.update({"plan": plan_id, "billing_cycle": cycle,
                "upgraded_at": datetime.now(timezone.utc).isoformat()})
    return collection("subscriptions").put(sub, prefix="sub")


def create_checkout_placeholder(user_email: str, plan_id: str,
                                cycle: str = "monthly") -> Dict[str, Any]:
    """Stripe *sandbox* placeholder — swap for stripe.checkout.Session.create."""
    plan = PLANS.get(plan_id)
    if not plan:
        raise SubscriptionError(f"Unknown plan '{plan_id}'.")
    amount = plan["price_year"] if cycle == "annual" else plan["price_month"]
    log.info("Stripe placeholder checkout: %s → %s (%s)", user_email, plan_id, cycle)
    return {
        "provider": "stripe_sandbox",
        "session_id": f"cs_test_{secrets.token_hex(8)}",
        "amount_usd": amount, "cycle": cycle, "plan": plan_id,
        "success_url": "/pricing?session_id={CHECKOUT_SESSION_ID}",
        "note": "Set STRIPE_SECRET_KEY in .env to activate real checkout.",
    }


# ── API keys (Sprint 14) ─────────────────────────────────────────────────────
def generate_api_key(name: str, scopes: List[str]) -> Dict[str, Any]:
    raw = f"imad_live_{secrets.token_hex(16)}"
    record = {
        "name": name or "default",
        "prefix": raw[:14],
        "key_hash": hashlib.sha256(raw.encode()).hexdigest(),
        "scopes": scopes or ["read"],
        "revoked": False,
    }
    from app.core.docstore import collection

    saved = collection("apikeys").put(record, prefix="key")
    return {**saved, "secret_once": raw}     # displayed exactly once


def verify_api_key(raw: str) -> Optional[Dict[str, Any]]:
    from app.core.docstore import collection

    h = hashlib.sha256(raw.encode()).hexdigest()
    return next((k for k in collection("apikeys").list()
                 if k["key_hash"] == h and not k.get("revoked")), None)


def revoke_api_key(key_id: str) -> bool:
    from app.core.docstore import collection

    return collection("apikeys").update(key_id, revoked=True) is not None