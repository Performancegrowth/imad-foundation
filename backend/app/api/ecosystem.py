"""Sprint 13 — Data moat, cost database & marketplace endpoints.

Anonymised design snapshots feed aggregate analytics (design trends);
the regional cost database overrides BOQ default rates; suppliers and
licensed consultants form the marketplace; certification completes the
ecosystem with quiz scoring and a printable certificate.

Privacy: snapshots strip client names, addresses and project identifiers —
only engineering quantities and a hashed region code are retained.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.core.docstore import collection
from app.models.business import (
    Certification,
    Consultant,
    ConsultantReviewRequest,
    CostRecord,
    DesignDataSnapshot,
    Supplier,
)

log = logging.getLogger("imad.api.ecosystem")
router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_region(region: str) -> str:
    """Privacy: store only a truncated hash of the region string."""
    if not region:
        return ""
    return hashlib.sha256(region.strip().lower().encode()).hexdigest()[:12]


# ── Anonymised design snapshots ──────────────────────────────────────────────
class SnapshotRequest(BaseModel):
    region: str = ""
    stories: int = Field(default=1, ge=1, le=40)
    footprint_m2: float = Field(default=0, ge=0)
    concrete_m3: float = 0
    rebar_kg: float = 0
    carbon_kgco2e: float = 0
    cost_usd: float = 0
    slab_type: str = "flat"
    avg_bay_m: float = 0


@router.post("/design-data/snapshot",
             summary="Record an anonymised design snapshot on completion",
             status_code=201)
async def save_snapshot(payload: SnapshotRequest) -> Dict[str, Any]:
    snap = DesignDataSnapshot(
        region_code=_hash_region(payload.region),
        stories=payload.stories,
        footprint_m2=payload.footprint_m2,
        concrete_m3=payload.concrete_m3,
        rebar_kg=payload.rebar_kg,
        carbon_kgco2e=payload.carbon_kgco2e,
        cost_usd=payload.cost_usd,
        slab_type=payload.slab_type[:32],
        avg_bay_m=payload.avg_bay_m,
        # source_hash ties the snapshot to an anonymous build fingerprint
        source_hash=hashlib.sha256(
            f"{payload.stories}|{payload.footprint_m2}|{payload.slab_type}".encode()
        ).hexdigest()[:16],
    )
    doc = collection("design_snapshots").put(snap.model_dump(), prefix="dsn")
    audit.log_action("design_snapshot_saved", details={"source_hash": snap.source_hash})
    return {"id": doc["id"], "anonymised": True, "region_code": snap.region_code}


@router.get("/analytics/design",
            summary="Aggregated design trends across all anonymised snapshots")
async def design_analytics() -> Dict[str, Any]:
    snaps = collection("design_snapshots").list()
    if not snaps:
        return {"count": 0, "message": "No snapshots recorded yet."}

    n = len(snaps)
    def _avg(field: str) -> float:
        vals = [float(s.get(field) or 0) for s in snaps]
        return round(sum(vals) / max(len(vals), 1), 2)

    by_stories: Dict[str, List[float]] = {}
    for s in snaps:
        key = f"{min(int(s.get('stories') or 1), 10)}" + ("+" if int(s.get("stories") or 1) > 10 else "")
        gfa = max(float(s.get("footprint_m2") or 0) * max(int(s.get("stories") or 1), 1), 1.0)
        by_stories.setdefault(key, []).append(
            float(s.get("carbon_kgco2e") or 0) / gfa)

    story_bands = {
        k: {"projects": len(v),
            "avg_carbon_intensity_kgco2e_m2": round(sum(v) / max(len(v), 1), 1)}
        for k, v in sorted(by_stories.items(), key=lambda kv: kv[0])
    }
    slab_mix: Dict[str, int] = {}
    for s in snaps:
        slab_mix[s.get("slab_type", "flat")] = slab_mix.get(s.get("slab_type", "flat"), 0) + 1

    return {
        "count": n,
        "avg_stories": _avg("stories"),
        "avg_footprint_m2": _avg("footprint_m2"),
        "avg_concrete_m3": _avg("concrete_m3"),
        "avg_rebar_kg": _avg("rebar_kg"),
        "avg_cost_usd": _avg("cost_usd"),
        "rebar_per_m3_concrete_avg": round(
            sum(float(s.get("rebar_kg") or 0) for s in snaps)
            / max(sum(float(s.get("concrete_m3") or 0) for s in snaps), 1e-9), 1),
        "story_bands": story_bands,
        "slab_type_distribution": slab_mix,
    }


# ── Regional cost database ───────────────────────────────────────────────────
class CostRecordIn(BaseModel):
    region: str
    item_code: str
    description: str = ""
    unit: str = "m3"
    unit_cost: float = Field(ge=0)
    currency: str = "USD"
    source: str = "manual"


@router.get("/costs", summary="Query the regional cost database")
async def costs_list(region: Optional[str] = None,
                     item_code: Optional[str] = None) -> Dict[str, Any]:
    docs = collection("cost_records").list()
    if region:
        docs = [d for d in docs if d.get("region", "").lower() == region.lower()]
    if item_code:
        docs = [d for d in docs if d.get("item_code") == item_code]
    docs.sort(key=lambda d: (d.get("region", ""), d.get("item_code", "")))
    return {"count": len(docs), "records": docs}


@router.post("/costs", summary="Add or update a cost record", status_code=201)
async def costs_upsert(payload: CostRecordIn) -> Dict[str, Any]:
    try:
        record = CostRecord(
            region=payload.region, item_code=payload.item_code,
            description=payload.description, unit=payload.unit,  # type: ignore[arg-type]
            unit_cost=payload.unit_cost, currency=payload.currency,
            valid_from=_now()[:10], source=payload.source)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid record: {exc}") from exc

    store = collection("cost_records")
    existing = next((d for d in store.list()
                     if d["region"].lower() == payload.region.lower()
                     and d["item_code"] == payload.item_code), None)
    doc = store.update(existing["id"], **record.model_dump()) if existing \
        else store.put(record.model_dump(), prefix="cst")
    audit.log_action("cost_record_saved",
                     details={"region": payload.region, "item": payload.item_code})
    return doc


@router.post("/costs/import",
             summary="Bulk import cost records from CSV rows "
                     "(region,item_code,unit,unit_cost[,description])",
             status_code=201)
async def costs_import(rows: List[List[str]]) -> Dict[str, Any]:
    """Bulk import — accepts a matrix of CSV-style rows."""
    store = collection("cost_records")
    imported, skipped = 0, []
    for i, row in enumerate(rows):
        if len(row) < 4:
            skipped.append({"row": i, "reason": "need ≥4 columns"})
            continue
        region, item_code, unit, cost = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
        if not region or not item_code:
            skipped.append({"row": i, "reason": "empty key"})
            continue
        try:
            value = float(cost)
        except ValueError:
            skipped.append({"row": i, "reason": f"bad cost '{cost}'"})
            continue
        existing = next((d for d in store.list()
                         if d["region"].lower() == region.lower()
                         and d["item_code"] == item_code), None)
        data = CostRecord(
            region=region, item_code=item_code, unit=unit,  # type: ignore[arg-type]
            unit_cost=value, description=row[4] if len(row) > 4 else "",
            valid_from=_now()[:10], source="bulk_import").model_dump()
        store.update(existing["id"], **data) if existing else store.put(data, prefix="cst")
        imported += 1
    return {"imported": imported, "skipped": skipped}


# ── Supplier marketplace ──────────────────────────────────────────────────────
class SupplierIn(BaseModel):
    company: str
    categories: List[str] = ["concrete"]
    region: str = ""
    contact_email: str = ""
    rating: float = Field(default=0, ge=0, le=5)


@router.get("/suppliers", summary="Browse the supplier directory")
async def suppliers_list(category: Optional[str] = None,
                         region: Optional[str] = None) -> Dict[str, Any]:
    docs = collection("suppliers").list()
    if category:
        docs = [d for d in docs if category.lower() in
                [c.lower() for c in (d.get("categories") or [])]]
    if region:
        docs = [d for d in docs if d.get("region", "").lower() == region.lower()]
    docs.sort(key=lambda d: -float(d.get("rating") or 0))
    return {"count": len(docs), "suppliers": docs}


@router.post("/suppliers", summary="Register a supplier", status_code=201)
async def suppliers_register(payload: SupplierIn) -> Dict[str, Any]:
    doc = collection("suppliers").put(
        Supplier(company=payload.company, categories=payload.categories,
                 region=payload.region, contact_email=payload.contact_email,
                 rating=payload.rating, verified=False).model_dump(),
        prefix="sup")
    audit.log_action("supplier_registered", details={"company": payload.company})
    return doc


# ── Consultant marketplace (review & stamp) ──────────────────────────────────
class ConsultantIn(BaseModel):
    name: str
    license_number: str
    specialties: List[str] = ["concrete design"]
    regions: List[str] = []
    review_rate_usd: float = Field(default=0, ge=0)


@router.get("/consultants", summary="Browse licensed consultants offering review & stamp")
async def consultants_list(specialty: Optional[str] = None) -> Dict[str, Any]:
    docs = collection("consultants").list()
    if specialty:
        docs = [d for d in docs if specialty.lower() in
                [s.lower() for s in (d.get("specialties") or [])]]
    docs.sort(key=lambda d: float(d.get("review_rate_usd") or 0))
    return {"count": len(docs), "consultants": docs}


@router.post("/consultants", summary="Register as a reviewing consultant", status_code=201)
async def consultants_register(payload: ConsultantIn) -> Dict[str, Any]:
    doc = collection("consultants").put(
        Consultant(name=payload.name, license_number=payload.license_number,
                   specialties=payload.specialties, regions=payload.regions,
                   review_rate_usd=payload.review_rate_usd).model_dump(),
        prefix="cns")
    audit.log_action("consultant_registered", details={"name": payload.name})
    return doc


class ReviewRequestIn(BaseModel):
    consultant_id: str
    project_id: int = 1
    scope: str = "Full structural review + stamp"


@router.post("/consultants/request-review",
             summary="Request a licensed review/stamp from a consultant",
             status_code=202)
async def request_review(payload: ReviewRequestIn) -> Dict[str, Any]:
    consultant = collection("consultants").get(payload.consultant_id)
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found.")
    if not consultant.get("available", True):
        raise HTTPException(status_code=409, detail="Consultant is not accepting work.")
    req = ConsultantReviewRequest(
        consultant_id=payload.consultant_id, project_id=payload.project_id,
        scope=payload.scope[:200], status="pending")
    doc = collection("consultant_requests").put(req.model_dump(), prefix="rev")
    audit.log_action("review_requested", project_id=payload.project_id,
                     details={"consultant_id": payload.consultant_id})
    return {
        **doc,
        "consultant": consultant.get("name"),
        "rate_usd": consultant.get("review_rate_usd", 0),
        "note": "The consultant has been notified; payment settlement is handled offline in this release.",
    }


@router.get("/consultants/requests/{project_id}",
            summary="List review requests for a project")
async def review_requests(project_id: int) -> Dict[str, Any]:
    docs = collection("consultant_requests").list(
        lambda d: int(d.get("project_id") or 0) == project_id)
    return {"count": len(docs), "requests": docs}


# ── Training & certification ─────────────────────────────────────────────────
QUIZ = [
    {"q": "Which load combination is NOT part of ACI 318 basic strength combos?",
     "options": ["1.4D", "1.2D + 1.6L", "0.9D + 1.6W", "1.2D + 1.0L + 1.0W"], "answer": 2},
    {"q": "A flat slab is most economical for:",
     "options": ["Long spans > 12 m", "Residential grids 6–8 m", "Heavy industrial loads", "Bridge decks"],
     "answer": 1},
    {"q": "Embodied carbon of concrete is dominated by:",
     "options": ["Aggregates", "Clinker content", "Water", "Admixtures"], "answer": 1},
    {"q": "GGBS substitution primarily improves:",
     "options": ["Early strength", "Chloride resistance & carbon footprint", "Slump", "Air content"],
     "answer": 1},
    {"q": "Deflection limit for a typical interior beam per SBC/ACI (L/?) is:",
     "options": ["L/180", "L/250", "L/360", "L/800"], "answer": 2},
]


@router.get("/certification/quiz", summary="Fetch the certification quiz (5 questions)")
async def certification_quiz() -> Dict[str, Any]:
    return {"questions": [{"id": i, "question": q["q"], "options": q["options"]}
                          for i, q in enumerate(QUIZ)]}


class QuizSubmission(BaseModel):
    user_email: str
    answers: List[int] = Field(min_length=1, max_length=len(QUIZ))
    level: str = "associate"


@router.post("/certification/complete", summary="Score the quiz and issue a certificate")
async def certification_complete(payload: QuizSubmission) -> Dict[str, Any]:
    if len(payload.answers) != len(QUIZ):
        raise HTTPException(status_code=422,
                            detail=f"Expected {len(QUIZ)} answers, got {len(payload.answers)}.")
    correct = sum(1 for a, q in zip(payload.answers, QUIZ) if a == q["answer"])
    score = round(100 * correct / len(QUIZ), 1)
    passed = score >= 60
    level = payload.level if payload.level in ("associate", "professional", "expert") \
        else "associate"
    cert_id = ""
    if passed:
        cert_id = f"IMAD-{level[:3].upper()}-{hashlib.sha256(payload.user_email.encode()).hexdigest()[:8].upper()}"
        cert = Certification(user_email=payload.user_email, level=level,  # type: ignore[arg-type]
                             score=score, passed=True, certificate_id=cert_id,
                             expires_at=None)
        collection("certifications").put(cert.model_dump(), prefix="crt")
        audit.log_action("certification_issued",
                         details={"user": payload.user_email, "score": score})
    return {"score": score, "passed": passed, "certificate_id": cert_id,
            "correct": correct, "total": len(QUIZ)}