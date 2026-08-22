"""
Append-only audit log.

Every user action (login, upload, run analysis, generate design, export, …)
is recorded immutably. Logs are SHA-256 chained to the previous entry so any
tampering is detectable — a lightweight, dependency-free hash chain. This backs
the Sprint 10 AuditTrail requirement.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import storage_root


def _audit_dir() -> Path:
    p = storage_root() / "audit"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _chain_file() -> Path:
    return _audit_dir() / "_chain"


def _append(entry: Dict[str, Any]) -> Dict[str, Any]:
    prev_hash = ""
    chain = _chain_file()
    if chain.exists():
        prev_hash = chain.read_text(encoding="utf-8").strip()

    payload = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    entry_hash = hashlib.sha256(payload).hexdigest()
    digest = hashlib.sha256(f"{prev_hash}{entry_hash}".encode("utf-8")).hexdigest()

    record = {**entry, "hash": digest, "prev_hash": prev_hash}
    (chain.write_text(digest, encoding="utf-8"))
    with open(_audit_dir() / f"{entry['entry_id']}.json", "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return record


def log_action(
    action: str,
    actor_id: Optional[int] = None,
    project_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    actor_role: str = "engineer",
) -> Dict[str, Any]:
    """Record an audit action. Returns the immutable entry."""
    import secrets
    entry = {
        "action": action,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "project_id": project_id,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry_id": f"a{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3)}",
    }
    return _append(entry)


def list_log(project_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """Return audit entries, optionally filtered by project (most recent last)."""
    entries: List[Dict[str, Any]] = []
    for file in _audit_dir().glob("*.json"):
        try:
            entries.append(json.loads(file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    entries.sort(key=lambda e: e.get("timestamp", ""))
    if project_id is not None:
        entries = [e for e in entries if e.get("project_id") == project_id]
    return entries[-limit:]


def verify_chain() -> Dict[str, Any]:
    """Replay the hash chain and report whether any entry was tampered with."""
    entries = []
    for file in _audit_dir().glob("*.json"):
        try:
            entries.append(json.loads(file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    entries.sort(key=lambda e: e.get("timestamp", ""))
    prev = ""
    valid = True
    for e in entries:
        payload = json.dumps(
            {k: v for k, v in e.items() if k not in ("hash", "prev_hash")},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        entry_hash = hashlib.sha256(payload).hexdigest()
        expected = hashlib.sha256(f"{e['prev_hash']}{entry_hash}".encode("utf-8")).hexdigest()
        if expected != e["hash"] or e["prev_hash"] != prev:
            valid = False
            break
        prev = e["hash"]
    return {"valid": valid, "entries": len(entries)}