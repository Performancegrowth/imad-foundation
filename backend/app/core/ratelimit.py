"""
In-memory rate limiting for Imad.

Sliding-window limiter keyed by client IP. Backed by a plain dictionary so it
works with zero infrastructure; designed behind a narrow interface so a Redis
(counted) implementation can be dropped in later without touching routes:

    from app.core.ratelimit import rate_limit

    @router.get("/jobs")
    async def list_jobs(request: Request, _: None = Depends(rate_limit())):
        ...
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional

from fastapi import HTTPException, Request, status

# Client-address header handling.
FORWARDED_HEADERS = ("x-forwarded-for", "forwarded")


@dataclass
class Bucket:
    """Sliding window of request timestamps for a single client."""

    hits: Deque[float] = field(default_factory=deque)


class _SlidingWindowStore:
    """Thread-safe in-memory store of per-client sliding windows."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, Bucket] = {}

    def _prune(self, bucket: Bucket, window_seconds: float, now: float) -> None:
        cutoff = now - window_seconds
        while bucket.hits and bucket.hits[0] <= cutoff:
            bucket.hits.popleft()

    def allow(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: Optional[float] = None,
    ) -> bool:
        """Register a hit and report whether it stays under the limit."""
        now = now if now is not None else time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._buckets[key] = Bucket()
            self._prune(bucket, window_seconds, now)
            if len(bucket.hits) >= max_requests:
                return False
            bucket.hits.append(now)
            return True

    def retry_after(self, key: str, window_seconds: int) -> int:
        """Seconds until the oldest hit leaves the window (for the 429 header)."""
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or not bucket.hits:
                return window_seconds
            return max(0, int(window_seconds - (time.monotonic() - bucket.hits[0])) + 1)


# ────────────────────────────────────────────────────────────────────────────
# Rate limiter factory — the public, route-friendly dependency.
# ────────────────────────────────────────────────────────────────────────────
def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
    **_: Any,
) -> Callable[[Request], None]:
    """Build a FastAPI dependency enforcing ``max_requests`` per sliding window.

    Defaults to the global guard: 100 requests / 60s. Optional ``**`` params are
    reserved for a future Redis backend (e.g. ``key_prefix``) and ignored today.
    """
    store = _SlidingWindowStore()

    def dependency(request: Request) -> None:  # noqa: D401 — runtime guard
        key = get_client_ip(request)
        window = int(window_seconds)
        if not store.allow(key, int(max_requests), window):
            retry = store.retry_after(key, window)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Rate limit exceeded: "
                    f"more than {max_requests} requests in {window_seconds}s. "
                    "Please slow down and retry."
                ),
                headers={"Retry-After": str(retry)},
            )

    return dependency


# A global limiter applying the default of 100 requests / 60 seconds.
limit_global: Callable[[Request], None] = rate_limit()


# ────────────────────────────────────────────────────────────────────────────
# Client IP resolution helpers.
# ────────────────────────────────────────────────────────────────────────────
def get_client_ip(request: Request) -> str:
    """Best-effort client IP from forwarded headers, falling back to the socket.

    ``x-forwarded-for`` may list ``client, proxy1, proxy2`` — we take the
    leftmost real client address. Unknown values are rejected so a client can't
    trivially spoof a fresh identity.
    """
    for header in FORWARDED_HEADERS:
        value = request.headers.get(header)
        if not value:
            continue
        candidate = _first_usable(value)
        if candidate:
            return candidate
    client = request.client
    return client.host if client else "unknown"


def _first_usable(value: str) -> Optional[str]:
    """Return the first non-empty, non-suspicious address in a header list."""
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if any(bad in token.lower() for bad in ("unknown", "none", "null")):
            continue
        # Strip a trailing :port if present.
        return token.rsplit(":", 1)[0] if ":" in token else token
    return None


# Convenience alias retained for clarity in route signatures.
def default_limiter() -> None:
    """Placeholder for future Redis-backed global limiter (kept for parity)."""


# Re-exported for imports like ``from app.core.ratelimit import limit_global``.
__all__ = ["rate_limit", "get_client_ip", "limit_global", "default_limiter"]