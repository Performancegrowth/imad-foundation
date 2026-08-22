"""Sprint 9B — AI business agent endpoints (sales / marketing / support).

All agents run on the local Ollama stack with deterministic fallbacks, so the
endpoints always answer — see ``services/agents.py``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.agents import (
    AgentError,
    marketing_content,
    sales_email,
    support_reply,
)

log = logging.getLogger("imad.api.agents")
router = APIRouter()


class SalesRequest(BaseModel):
    kind: str = Field(default="lead", pattern="^(lead|followup|proposal)$")
    company: str = ""
    contact: str = ""
    notes: str = ""


class MarketingRequest(BaseModel):
    kind: str = Field(default="social", pattern="^(social|blog|newsletter)$")
    topic: str = Field(min_length=3, max_length=200)


class SupportRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: List[Dict[str, str]] = Field(default_factory=list)


@router.post("/agents/sales", summary="Draft a sales email (lead / follow-up / proposal)")
async def sales(payload: SalesRequest) -> Dict[str, Any]:
    try:
        return await sales_email(payload.kind, payload.model_dump(exclude={"kind"}))
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agents/marketing", summary="Generate marketing content (social / blog / newsletter)")
async def marketing(payload: MarketingRequest) -> Dict[str, Any]:
    try:
        return await marketing_content(payload.kind, payload.topic)
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agents/support", summary="Support chatbot reply")
@router.post("/support/chat", include_in_schema=False)   # Sprint 14 alias
async def support(payload: SupportRequest) -> Dict[str, Any]:
    try:
        return await support_reply(payload.question, payload.history)
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc