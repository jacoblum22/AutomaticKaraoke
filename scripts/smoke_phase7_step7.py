#!/usr/bin/env python3
"""Phase 7 Step 7 — optional API key on protected routes.

When ``API_KEY`` is set on Modal (secret ``karaoke-api-key``):
  - request without ``X-API-Key`` → 401
  - request with matching key → not 401

Set ``KARAOKE_API_KEY`` in the environment for HTTP tests (same value as Modal).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from smoke_api import api_key_header, request_json  # noqa: E402
from smoke_modal import modal_output_text, run_modal, run_modal_deploy  # noqa: E402


def run_modal_auth_status() -> bool:
    proc = run_modal(
        "app.py::smoke_phase7_auth_status", cwd=BACKEND, root=REPO_ROOT
    )
    return "API_KEY_CONFIGURED=True" in modal_output_text(proc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 7 API key smoke")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
    )
    args = parser.parse_args()

    print(f"api: {args.base_url}")

    if args.deploy:
        run_modal_deploy(REPO_ROOT)

    print("\n[1/2] modal run smoke_phase7_auth_status …")
    configured = run_modal_auth_status()

    print("\n[2/2] HTTP protected route …")
    status, cfg = request_json(f"{args.base_url.rstrip('/')}/config")
    if status != 200:
        raise SystemExit(f"config failed: {status}")

    api_required = bool(isinstance(cfg, dict) and cfg.get("api_key_required"))
    if not api_required and not configured:
        print("  API_KEY not configured — auth disabled (OK for dev)")
        print("\nPhase 7 Step 7 OK (auth optional / disabled)")
        return 0

    if not api_required:
        print("  warning: Modal has API_KEY but /config says not required")

    fake_id = str(uuid.uuid4())
    q = urlencode({"job_id": fake_id})
    # Do not use request_json here — it would attach KARAOKE_API_KEY from the environment.
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    no_key_req = Request(
        f"{args.base_url.rstrip('/')}/finalize-job?{q}",
        data=b"",
        method="POST",
    )
    try:
        urlopen(no_key_req, timeout=30)
        raise SystemExit("expected 401 without key, got 2xx")
    except HTTPError as exc:
        status_no_key = exc.code
        raw_no = exc.read().decode("utf-8", errors="replace")
        try:
            body_no = json.loads(raw_no) if raw_no else None
        except json.JSONDecodeError:
            body_no = raw_no
    if status_no_key != 401:
        raise SystemExit(f"expected 401 without key, got {status_no_key}: {body_no}")

    detail = ""
    if isinstance(body_no, dict):
        detail = str(body_no.get("detail", ""))
    elif isinstance(body_no, str):
        detail = body_no
    if "api key" not in detail.lower():
        raise SystemExit(f"expected API key error, got: {detail!r}")
    print(f"  without key: HTTP {status_no_key}")

    karaoke_key = os.environ.get("KARAOKE_API_KEY", "").strip()
    if not karaoke_key:
        raise SystemExit(
            "API_KEY is enabled on Modal — set KARAOKE_API_KEY for the with-key test"
        )

    status_ok, body_ok = request_json(
        f"{args.base_url.rstrip('/')}/finalize-job?{q}",
        method="POST",
        data=b"",
        headers=api_key_header(),
    )
    if status_ok == 401:
        raise SystemExit("valid KARAOKE_API_KEY still got 401 — key mismatch with Modal secret")
    if status_ok not in (200, 404, 400):
        raise SystemExit(f"unexpected status with key: {status_ok} {body_ok}")
    print(f"  with key:    HTTP {status_ok} (not 401)")

    print("\nPhase 7 Step 7 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
