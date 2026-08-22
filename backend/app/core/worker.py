"""Background task processor for the Imad worker service (Docker).

Consumes jobs off a Redis list when the ``redis`` client is present; otherwise
it runs a lightweight placeholder loop so local development stays
dependency-free. In production this maps to a Celery worker (see
``docs/scaling.md``) — the queue contract (decode JSON, process, ack) is the
same, so job handlers remain reusable.
"""
from __future__ import annotations

import json
import os
import time

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE = "imad:jobs"


def process(payload) -> None:
    """Handle a single queued job payload (decode → act)."""
    print(f"[worker] processed job: {json.dumps(payload, ensure_ascii=False)[:200]}")


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