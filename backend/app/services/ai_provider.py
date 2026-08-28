"""
AI provider interface — Sprint 3.

``OllamaLocalProvider`` runs a local LLM (e.g. ``llama3`` / ``qwen2``) to turn
open-ended natural-language space descriptions into the same ``PlanData``
geometry contract the CAD pipeline emits. Results are always parsed into typed
models — the LLM never owns safety-critical numbers on its own.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger("imad.ai")


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIProviderError(Exception):
    """Raised when an AI request fails."""


class BaseMessage:
    __slots__ = ("role", "content")

    def __init__(self, role: Role, content: str):
        self.role = role
        self.content = content


class AIProvider(ABC):
    """Adapter base — implement ``chat_json`` per provider."""

    provider_name: str = "generic"

    @abstractmethod
    async def chat_json(self, messages: List[BaseMessage], temperature: float = 0.2) -> Dict[str, Any]:
        """Return a JSON object (dictionary) for the transcript."""


class OllamaLocalProvider(AIProvider):
    """Talk to a local Ollama endpoint (default http://localhost:11434)."""

    provider_name = "ollama"

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL")
                         or "http://localhost:11434").rstrip("/")
        # Model resolution: explicit arg → OLLAMA_MODEL env → safe 0.5b default.
        self.model = model or os.getenv("OLLAMA_MODEL") or "qwen2.5:0.5b"

    def chat(
        self, messages: List[BaseMessage], temperature: float = 0.2
    ) -> str:
        """Blocking call to Ollama's ``/api/generate`` with JSON format."""
        payload = {
            "model": self.model,
            "prompt": "\n".join(m.content for m in messages),
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            log.error("Ollama request failed: %s", exc)
            raise AIProviderError(f"Ollama request failed: {exc}") from exc
        text = (body.get("response") or "").strip()
        return text

    async def chat_json(
        self, messages: List[BaseMessage], temperature: float = 0.2
    ) -> Dict[str, Any]:
        # Run the blocking urllib call off the event loop so long Ollama
        # generations (up to the 120s urllib timeout) don't stall other requests.
        import asyncio
        raw = await asyncio.to_thread(self.chat, messages, temperature=temperature)
        return _extract_json_dict(raw)


def _extract_json_dict(text: str) -> Dict[str, Any]:
    """Robustly pull the first JSON object from an LLM reply."""
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise AIProviderError("Model did not return a JSON object.")