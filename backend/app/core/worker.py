"""Background task processor for the Imad worker service (Docker).

Consumes jobs off a Redis list when the ``redis`` client is present; otherwise
it runs a lightweight placeholder loop so local development stays
dependency-free. In production this maps to a Celery worker (see
``docs/scaling.md``) — the queue contract (decode JSON, process, ack) is the
same, so job handlers remain reusable.
"""
from __future__ import annotations

import asyncio
import json
import os
import time

from app.core import jobs

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE = jobs.QUEUE


def run_task(kind: str, data) -> dict:
    """Resolve a queued ``kind`` to its worker-safe compute function."""
    if kind == "analysis":
        from app.api.analysis import run_analysis
        return run_analysis(data)
    if kind == "boq":
        from app.api.boq import run_boq
        return run_boq(data)
    if kind == "carbon":
        from app.api.sustainability import run_carbon
        return asyncio.run(run_carbon(data))
    raise ValueError(f"Unknown job kind: {kind!r}")


def process(payload) -> None:
    """Handle a single queued job payload (decode -> act -> record)."""
    job_id = payload.get("job_id")
    kind = payload.get("kind")
    data = payload.get("payload")
    if not job_id:
        raise ValueError("Job payload missing 'job_id'")

    jobs.update_job(job_id, status="running")
    try:
        result = run_task(kind, data)
    except Exception as exc:  # pragma: no cover — surface failures on the job
        jobs.update_job(job_id, status="failed", error=str(exc))
        print(f"[worker] {kind} job {job_id} failed: {exc}")
        return
    jobs.update_job(job_id, status="completed", progress=1.0, result=result)
    print(f"[worker] {kind} job {job_id} completed")


def main() -> None:
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(REDIS_URL)
        client.ping()
    except Exception as exc:  # pragma: no cover — redis not installed
        print(f"[worker] Redis unavailable ({exc}); running placeholder loop")
        while True:
            print("[worker] no queue — waiting...")
            time.sleep(10)
        return

    print(f"[worker] watching '{QUEUE}' on {REDIS_URL}")
    while True:
        item = client.blpop(QUEUE, timeout=5)
        if not item:
            continue
        try:
            process(json.loads(item[1]))
        except Exception as exc:  # pragma: no cover — surface failures
            print(f"[worker] failed to process: {exc}")


if __name__ == "__main__":
    main()