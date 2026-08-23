"""
Filesystem-backed storage helpers.

Sprint 2–5 use a lightweight JSON + binary store on disk (uploads, design
results) so the full pipeline works without a live DB. A later sprint swaps
these for the ORM while keeping the same public functions.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def storage_root() -> Path:
    return Path(__file__).resolve().parents[2] / "storage"


def uploads_dir() -> Path:
    """Upload directory. Override with the ``UPLOAD_DIR`` env var for persistent
    volumes in Docker (see docker-compose.yml)."""
    override = os.getenv("UPLOAD_DIR")
    p = Path(override) if override else storage_root() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def results_dir() -> Path:
    """Design-results directory. Override with the ``RESULTS_DIR`` env var."""
    override = os.getenv("RESULTS_DIR")
    p = Path(override) if override else storage_root() / "results"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_upload(filename: str, content: bytes) -> Dict[str, Any]:
    """Persist an uploaded file + registry entry; return design-file metadata."""
    ext = Path(filename).suffix.lower()
    stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}{ext}"
    target = uploads_dir() / stored_name
    target.write_bytes(content)

    index_path = storage_root() / "uploads-index.json"
    index: Dict[str, Any] = {}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {}
    next_id = max([int(k) for k in index.keys()] or [0]) + 1
    index[str(next_id)] = {
        "stored_name": stored_name,
        "stored_path": str(target),
        "original_name": filename,
        "file_ext": ext,
        "size_bytes": len(content),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return {"file_id": next_id, **index[str(next_id)]}


def load_upload(file_id: int) -> Optional[Dict[str, Any]]:
    """Resolve a persisted file_id to its stored metadata/path."""
    index_path = storage_root() / "uploads-index.json"
    if not index_path.exists():
        return None
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    entry = index.get(str(file_id))
    if not entry or not Path(entry["stored_path"]).exists():
        return None
    return entry


def perform_ext(path: str):
    return Path(path).suffix.lower()


# ---- design results store ------------------------------------------------
def save_result(result_id: str, payload: Dict[str, Any], status: str = "completed") -> Dict[str, Any]:
    record = {
        "id": result_id,
        "status": status,
        "payload": payload,
        **({"error": payload.get("error")} if payload.get("error") else {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (results_dir() / f"{result_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    return record


def load_result(result_id: str) -> Optional[Dict[str, Any]]:
    target = results_dir() / f"{result_id}.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def result_id(prefix: str = "r") -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3)}"