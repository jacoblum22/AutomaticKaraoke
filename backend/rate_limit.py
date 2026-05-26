"""Per-IP job-start rate limiting (Phase 7 Step 5)."""

from __future__ import annotations

import time
from typing import Any

import modal
from fastapi import HTTPException, Request

RATE_LIMIT_DICT_NAME = "karaoke-rate-limits"
JOBS_PER_HOUR = 5
WINDOW_SECONDS = 3600

RATE_LIMITS = modal.Dict.from_name(RATE_LIMIT_DICT_NAME, create_if_missing=True)


class RateLimitExceeded(Exception):
    """Raised when a client exceeds the job-start quota."""


def client_ip(request: Request) -> str:
    """Best-effort client IP from proxy headers or the ASGI client."""
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_key(client_key: str) -> str:
    return f"ip:{client_key}"


def consume_job_start_slot(
    client_key: str,
    *,
    limit: int = JOBS_PER_HOUR,
    window_s: int = WINDOW_SECONDS,
) -> None:
    """Increment the counter for ``client_key``; raise if over ``limit`` in ``window_s``."""
    key = _rate_limit_key(client_key)
    now = time.time()
    entry: dict[str, Any] = RATE_LIMITS.get(key) or {"count": 0, "window_start": now}
    window_start = float(entry.get("window_start", now))
    count = int(entry.get("count", 0))

    if now - window_start >= window_s:
        window_start = now
        count = 0

    if count >= limit:
        raise RateLimitExceeded(
            f"Rate limit exceeded: maximum {limit} karaoke jobs per hour per IP. "
            "Please wait and try again later."
        )

    RATE_LIMITS[key] = {"count": count + 1, "window_start": window_start}


def check_rate_limit(request: Request) -> None:
    """Enforce rate limit for job-start endpoints; raises HTTP 429."""
    try:
        consume_job_start_slot(client_ip(request))
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def reset_rate_limit(client_key: str) -> bool:
    """Clear counters for one IP (smoke tests)."""
    key = _rate_limit_key(client_key)
    try:
        del RATE_LIMITS[key]
        return True
    except KeyError:
        return False


def reset_all_rate_limits() -> int:
    """Clear all rate-limit entries (smoke cleanup)."""
    removed = 0
    for key in list(RATE_LIMITS.keys()):
        del RATE_LIMITS[key]
        removed += 1
    return removed
