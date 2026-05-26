"""Optional API key auth (Phase 7 Step 7)."""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request

API_KEY_HEADER = "x-api-key"


def api_key_configured() -> bool:
    """True when ``API_KEY`` is set in the environment (Modal secret)."""
    return bool(os.environ.get("API_KEY", "").strip())


def verify_api_key(request: Request) -> None:
    """Require ``X-API-Key`` when ``API_KEY`` is configured; no-op otherwise."""
    if not api_key_configured():
        return
    provided = request.headers.get(API_KEY_HEADER, "").strip()
    expected = os.environ.get("API_KEY", "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Send the X-API-Key header.",
        )
