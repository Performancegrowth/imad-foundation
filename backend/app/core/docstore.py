"""
Generic JSON document store (Sprints 6–14).

A lightweight, dependency-free persistence layer for business entities
(subscriptions, comments, approvals, suppliers, cost records, …). Collections
live under ``storage/db/<name>.json`` and are guarded by a per-collection
thread lock, matching the concurrency profile of the background job runner.

The public surface mirrors a tiny document DB so a later migration to
PostgreSQL is a drop-in swap of this module.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .storage import storage_root

_LOCKS: Dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(name: str) -> threading.RLock:
    with _LOCKS_GUARD:
        if name not in _LOCKS:
            _LOCKS[name] = threading.RLock()
        return _LOCKS[name]


def _path(name: str) -> Path:
    d = storage_root() / "db"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}.json"


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(5)}"


class DocumentStore:
    """One named collection of JSON documents."""

    def __init__(self, name: str):
        self.name = name

    # -- internals ---------------------------------------------------
    def _read_all(self) -> List[Dict[str, Any]]:
        p = _path(self.name)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _write_all(self, docs: List[Dict[str, Any]]) -> None:
        _path(self.name).write_text(
            json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- public API ----------------------------------------------------
    def list(self, filter_fn: Optional[Callable[[Dict], bool]] = None) -> List[Dict[str, Any]]:
        with _lock_for(self.name):
            docs = self._read_all()
        if filter_fn:
            docs = [d for d in docs if filter_fn(d)]
        return docs

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with _lock_for(self.name):
            return next((d for d in self._read_all() if d.get("id") == doc_id), None)

    def put(self, doc: Dict[str, Any], prefix: str = "doc") -> Dict[str, Any]:
        """Insert or replace by id; assigns id/timestamps when missing."""
        with _lock_for(self.name):
            docs = self._read_all()
            doc = dict(doc)
            doc.setdefault("id", new_id(prefix))
            doc.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            docs = [d for d in docs if d.get("id") != doc["id"]]
            docs.append(doc)
            self._write_all(docs)
            return doc

    def update(self, doc_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with _lock_for(self.name):
            docs = self._read_all()
            for i, d in enumerate(docs):
                if d.get("id") == doc_id:
                    docs[i] = {**d, **fields,
                               "updated_at": datetime.now(timezone.utc).isoformat()}
                    self._write_all(docs)
                    return docs[i]
            return None

    def delete(self, doc_id: str) -> bool:
        with _lock_for(self.name):
            docs = self._read_all()
            remaining = [d for d in docs if d.get("id") != doc_id]
            if len(remaining) == len(docs):
                return False
            self._write_all(remaining)
            return True


# Shared collections used across the platform modules.
COLLECTIONS = (
    "subscriptions", "apikeys", "whitelabels",
    "signature_requests", "compliance_checks", "submission_packages",
    "comments", "markups", "approvals", "tasks", "notifications", "webhooks",
    "design_snapshots", "cost_records", "suppliers", "consultants",
    "consultant_requests", "certifications", "tutorials",
)


def collection(name: str) -> DocumentStore:
    return DocumentStore(name)