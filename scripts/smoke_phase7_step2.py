#!/usr/bin/env python3
"""Phase 7 Step 2 — intent-based GPU warm-up.

1. POST /warm returns 202 quickly (no body).
2. Optional: compare E2E wall time cold vs warm (long; uses Psychosomatic).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"

WARM_RESPONSE_MAX_S = 5.0
DEFAULT_WARM_WAIT_S = 45


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def post_warm(base_url: str) -> dict:
    req = Request(f"{base_url.rstrip('/')}/warm", data=b"", method="POST")
    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"POST /warm failed: HTTP {exc.code} {detail}") from exc

    elapsed = time.perf_counter() - t0
    if status != 202:
        raise SystemExit(f"POST /warm expected 202, got {status}: {body}")

    if elapsed > WARM_RESPONSE_MAX_S:
        raise SystemExit(
            f"POST /warm took {elapsed:.2f}s (expected < {WARM_RESPONSE_MAX_S}s)"
        )

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {"raw": body}

    if payload.get("status") != "accepted":
        raise SystemExit(f"unexpected /warm body: {payload!r}")

    return {"elapsed_s": round(elapsed, 3), **payload}


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_e2e_compare(warm_wait_s: int, base_url: str) -> None:
    script = REPO_ROOT / "scripts" / "smoke_pipeline_modal.py"
    py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    print("\n[compare] cold E2E (no /warm) …")
    cold = subprocess.run(
        [str(py), str(script), "--base-url", base_url],
        cwd=REPO_ROOT,
        check=False,
    )
    if cold.returncode != 0:
        raise SystemExit("cold E2E failed")

    print(f"\n[compare] warm E2E (--warm, wait {warm_wait_s}s) …")
    warm = subprocess.run(
        [
            str(py),
            str(script),
            "--base-url",
            base_url,
            "--warm",
            "--warm-wait",
            str(warm_wait_s),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if warm.returncode != 0:
        raise SystemExit("warm E2E failed")
    print(
        "\nCompare wall times printed above. Warm should be lower when upload "
        "starts within ~2 min of /warm (scaledown_window=120)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 2 GPU warm-up smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
        help="Modal API base URL",
    )
    parser.add_argument(
        "--compare-e2e",
        action="store_true",
        help="Run cold then warm Psychosomatic E2E (very long)",
    )
    parser.add_argument(
        "--warm-wait",
        type=int,
        default=DEFAULT_WARM_WAIT_S,
        help="Seconds to wait after /warm before warm E2E (default 45)",
    )
    args = parser.parse_args()

    print(f"api: {args.base_url}")

    if args.deploy:
        run_deploy()

    print("\n[1/1] POST /warm …")
    result = post_warm(args.base_url)
    print(f"  status:   {result.get('status')}")
    print(f"  latency:  {result.get('elapsed_s')}s")

    if args.compare_e2e:
        run_e2e_compare(args.warm_wait, args.base_url)

    print("\nPhase 7 Step 2 OK (/warm)")
    print(
        "UI: select a file in UploadForm → network tab should show POST /warm "
        "(not on page load)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
