"""
Sprint 9B — AI business agents (Sales, Marketing, Support).

All agents run on the local Ollama provider (free stack) and degrade to
deterministic professional templates when the model is unreachable — the
product never blocks on the LLM.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.ai_provider import BaseMessage, OllamaLocalProvider, Role

log = logging.getLogger("imad.agents")

SYSTEM_PERSONAS: Dict[str, str] = {
    "sales": (
        "You are Imad's sales engineer. Draft concise B2B emails (max 150 words) "
        "for structural engineering firms. Lead with engineering value: faster "
        "BOQ cycles, code-compliant designs, embodied-carbon reporting. "
        "Always end with a concrete call to action."
    ),
    "marketing": (
        "You are Imad's marketing technologist. Produce social posts (LinkedIn/X, "
        "max 220 chars) and blog outlines about generative structural design, "
        "SBC/ACI compliance automation and carbon-aware concrete. No hype words."
    ),
    "support": (
        "You are Imad's tier-1 support engineer. Answer product questions about "
        "CAD import, plan generation, analysis (OpenSees), BOQ/BBS, carbon LCA "
        "and subscriptions. Be precise; if unsure, say what to check next."
    ),
}


class AgentError(Exception):
    pass


async def _ask(agent: str, user_prompt: str, context: Dict[str, Any] | None) -> str:
    persona = SYSTEM_PERSONAS.get(agent)
    if not persona:
        raise AgentError(f"Unknown agent '{agent}'.")
    content = user_prompt
    if context:
        content += f"\n\nContext: {context}"
    try:
        provider = OllamaLocalProvider()
        reply = await provider.chat_json([
            BaseMessage(Role.SYSTEM,
                        persona + ' Reply as strict JSON {"text": "..."}'),
            BaseMessage(Role.USER, content),
        ])
        text = str(reply.get("text", "")).strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001 — templates keep the product alive
        log.info("Agent '%s' LLM fallback: %s", agent, exc)
    return _template(agent, user_prompt, context or {})


# ------------------------------------------------------------- fallbacks -----
def _template(agent: str, prompt: str, ctx: Dict[str, Any]) -> str:
    if agent == "sales":
        company = ctx.get("company", "your firm")
        return (
            f"Subject: Cut preliminary design cycles at {company}\n\n"
            "Hello,\n\nImad converts CAD or a plain-language brief into a "
            "code-checked structural model, a cutting-optimised BBS and an "
            "embodied-carbon LCA — typically compressing preliminary design "
            "from days to under an hour.\n\nWorth a 20-minute walkthrough this "
            "week? I can run it on one of your live projects.\n\n"
            "— Imad Engineering Team"
        )
    if agent == "marketing":
        return (
            "From DXF to priced, carbon-reported structure in one workflow. "
            "Imad's generative engine benchmarks cost, CO₂e and flexibility "
            "side-by-side before you commit a scheme. #structuralengineering"
        )
    return (
        "Thanks for reaching out. To help quickly: which module are you using "
        "(CAD import, Create Plan, Analysis, BOQ, Sustainability)? If an error "
        "appeared, paste the message and the job ID from the progress panel."
    )


async def sales_email(kind: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """kind: lead | followup | proposal"""
    prompts = {
        "lead": "Draft a first-contact email to a potential customer.",
        "followup": "Draft a polite follow-up after a demo, one week later.",
        "proposal": "Draft a short proposal summary email with next steps.",
    }
    text = await _ask("sales", prompts.get(kind, prompts["lead"]), context)
    return {"agent": "sales", "kind": kind, "text": text}


async def marketing_content(kind: str, topic: str) -> Dict[str, Any]:
    """kind: social | blog | newsletter"""
    prompts = {
        "social": f"Write one LinkedIn post about {topic}.",
        "blog": f"Outline a 5-section technical blog post about {topic}.",
        "newsletter": f"Draft a 120-word product-update blurb about {topic}.",
    }
    text = await _ask("marketing", prompts.get(kind, prompts["social"]), {"topic": topic})
    return {"agent": "marketing", "kind": kind, "topic": topic, "text": text}


async def support_reply(question: str, history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    text = await _ask("support", question, {"history": (history or [])[-4:]})
    return {"agent": "support", "answer": text}
