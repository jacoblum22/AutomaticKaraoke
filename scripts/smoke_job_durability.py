#!/usr/bin/env python3
"""Phase 2 Step 6 — job state survives polling; unknown job_id returns 404."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BACKEND = Path(__file__).resolve().parent.parent / "backend"
REPO_ROOT = BACKEND.parent

DEPLOYED_API_URL = "https://jacoblum22--karaoke-api.modal.run"
DEV_API_URL = "https://jacoblum22--karaoke-api-dev.modal.run"
POLL_INTERVAL_S = 1.5
POLL_TIMEOUT_S = 60
TERMINAL = frozenset({"done", "failed"})


def _configure_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _multipart_body() -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    data = b"\x00\x01\x02"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="audio"; filename="smoke.mp3"\r\n',
            b"Content-Type: audio/mpeg\r\n\r\n",
            data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def _http_json(method: str, url: str, *, body: bytes | None = None, headers: dict | None = None) -> tuple[int, object]:
    req = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def _resolve_base_url(base_url: str | None, use_env: bool) -> str:
    if base_url:
        return base_url.rstrip("/")
    if use_env and os.environ.get("MODAL_API_URL"):
        url = os.environ["MODAL_API_URL"].rstrip("/")
        if "-dev" in url:
            print(
                "Note: -dev URL only works while `modal serve app.py` is running in backend/.",
                file=sys.stderr,
            )
        return url
    return DEPLOYED_API_URL


def _start_job(base: str) -> str:
    body, ctype = _multipart_body()
    status, data = _http_json(
        "POST",
        f"{base}/start-job",
        body=body,
        headers={"Content-Type": ctype},
    )
    if status != 200 or not isinstance(data, dict) or "job_id" not in data:
        hint = ""
        if status == 404 and "stopped" in str(data).lower():
            hint = (
                f"\n\nAPI endpoint is stopped at {base}.\n"
                f"  Production (always on): {DEPLOYED_API_URL}\n"
                f"  Dev (needs modal serve): {DEV_API_URL}\n"
                "  Fix: Remove-Item Env:MODAL_API_URL -ErrorAction SilentlyContinue\n"
                "        or: --base-url https://jacoblum22--karaoke-api.modal.run"
            )
        raise SystemExit(f"start-job failed: {status} {data!r}{hint}")
    return data["job_id"]


def _job_status(base: str, job_id: str) -> tuple[int, dict | str]:
    q = urlencode({"job_id": job_id})
    return _http_json("GET", f"{base}/job-status?{q}")


def _poll_until_terminal(base: str, job_id: str, *, redeploy_mid: bool) -> None:
    redeployed = False
    poll_count = 0
    last_status: str | None = None
    deadline = time.time() + POLL_TIMEOUT_S

    while time.time() < deadline:
        poll_count += 1
        status, data = _job_status(base, job_id)
        if status != 200 or not isinstance(data, dict):
            raise SystemExit(f"poll #{poll_count} failed: HTTP {status} {data!r}")

        st = data.get("status")
        if st != last_status:
            print(f"poll #{poll_count}: {st} {data.get('progress', 0)}")
            last_status = st

        if (
            redeploy_mid
            and not redeployed
            and st in ("separating", "transcribing", "aligning")
            and poll_count >= 2
        ):
            print("modal deploy (mid-job) …")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(
                [*_modal_cmd(), "deploy", "app.py"],
                cwd=BACKEND,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                print(result.stdout or "", result.stderr or "", file=sys.stderr)
                raise SystemExit("modal deploy failed during durability test")
            redeployed = True
            print("redeploy done; resuming poll …")

        if st in TERMINAL:
            if st == "failed":
                raise SystemExit(f"job failed: {data.get('error')}")
            print(f"job finished after {poll_count} polls (redeploy_mid={redeployed})")
            return

        time.sleep(POLL_INTERVAL_S)

    raise SystemExit("poll timed out")


def _assert_unknown_job_404(base: str) -> None:
    fake_id = str(uuid.uuid4())
    status, data = _job_status(base, fake_id)
    if status != 404:
        raise SystemExit(f"expected 404 for unknown job_id, got {status}: {data!r}")
    print(f"unknown job_id → HTTP 404 ({data})")


def main() -> None:
    _configure_stdio_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        help=f"API base (default: production {DEPLOYED_API_URL})",
    )
    parser.add_argument(
        "--use-env",
        action="store_true",
        help="Use MODAL_API_URL from environment instead of production default",
    )
    parser.add_argument(
        "--redeploy-mid",
        action="store_true",
        help="Run modal deploy while job is in progress (slower, stronger gate)",
    )
    args = parser.parse_args()
    base = _resolve_base_url(args.base_url, args.use_env)

    print(f"API base: {base}")
    job_id = _start_job(base)
    print(f"job_id: {job_id}")

    _poll_until_terminal(base, job_id, redeploy_mid=args.redeploy_mid)
    _assert_unknown_job_404(base)
    print("job durability OK")


if __name__ == "__main__":
    main()
