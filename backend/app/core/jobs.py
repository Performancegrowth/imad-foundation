"""
Background job / queue infrastructure.

Provides a lightweight in-process async task registry with persisted state on
disk (mirroring the results store). In production this maps to Redis + a worker
(see Sprint 14 scaling notes); the public API stays identical so swapping the
backend later is transparent.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

# Redis-backed queue contract shared by the API dispatcher and the worker.
# The worker (app/core/worker.py) consumes this key with BLPOP.
QUEUE = "imad:jobs"
_QUEUE_CLIENT = None


def queue_available() -> bool:
    """True when a reachable Redis broker is configured (production path)."""
    global _QUEUE_CLIENT
    if not os.getenv("REDIS_URL"):
        return False
    if _QUEUE_CLIENT is None:
        try:
            import redis  # type: ignore
            client = redis.Redis.from_url(os.getenv("REDIS_URL", ""))
            client.ping()
            _QUEUE_CLIENT = client
        except Exception:  # pragma: no cover — redis absent/unreachable
            _QUEUE_CLIENT = None
    return _QUEUE_CLIENT is not None


def enqueue_job(kind: str, payload: Dict[str, Any]) -> str:
    """Create a durable job record and push it to the Redis list queue."""
    # Ensure the broker connection exists even when callers skipped the
    # availability probe (e.g. explicit async opt-in on /analyze).
    if _QUEUE_CLIENT is None and not queue_available():
        raise RuntimeError("Redis queue is not available.")
    job_id = new_job(kind)
    record = {"job_id": job_id, "kind": kind, "payload": payload}
    try:
        _QUEUE_CLIENT.lpush(QUEUE, json.dumps(record, default=str))
    except Exception:  # pragma: no cover — surface enqueue failures
        update_job(job_id, status="failed", error="Failed to enqueue job.")
        raise
    return job_id


def jobs_dir() -> Path:
    from .storage import storage_root
    p = storage_root() / "jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_job(kind: str) -> str:
    job_id = f"job{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3)}"
    record = {
        "id": job_id,
        "kind": kind,
        "status": "queued",           # queued | running | completed | failed
        "progress": 0.0,              # 0..1
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write(job_id, record)
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    target = jobs_dir() / f"{job_id}.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def update_job(job_id: str, **fields: Any) -> Dict[str, Any]:
    record = get_job(job_id) or {"id": job_id}
    record.update(fields)
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write(job_id, record)
    return record


def _write(job_id: str, record: Dict[str, Any]) -> None:
    (jobs_dir() / f"{job_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")


def run_in_background(
    job_id: str,
    func: Callable[..., Any],
    *args: Any,
    async_func: Optional[Coroutine] = None,
    **kwargs: Any,
) -> None:
    """Dispatch a job to a background thread / asyncio task.

    The worker calls ``update_job`` to reflect progress and final state.
    ``func`` may itself call ``update_job`` for progress reporting.
    """
    def _worker() -> None:
        try:
            update_job(job_id, status="running")
            if kwargs.pop("is_async", False) or async_func is not None:
                target = async_func or func
                result = asyncio.run(target(*args, **kwargs))
            else:
                result = func(*args, **kwargs)
            update_job(job_id, status="completed", progress=1.0, result=result)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the job
            update_job(job_id, status="failed", error=str(exc))

    threading.Thread(target=_worker, daemon=True).start()
