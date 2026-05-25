#!/usr/bin/env python3
"""Phase 7 Step 3 — max audio duration (8 minutes).

1. Reject >8 min fixture with HTTP 400 and readable error.
2. Accept short fixture (Psychosomatic or sample_30s) — job reaches processing.
"""

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

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"

LONG_FIXTURE = REPO_ROOT / "scripts" / "fixtures" / "over_8min.mp3"
OK_FIXTURES = (
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
)

POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 60


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def ensure_long_fixture() -> Path:
    if LONG_FIXTURE.is_file() and LONG_FIXTURE.stat().st_size > 0:
        return LONG_FIXTURE
    script = REPO_ROOT / "scripts" / "generate_long_fixture.py"
    print("+", sys.executable, str(script))
    proc = subprocess.run([sys.executable, str(script)], check=False)
    if proc.returncode != 0 or not LONG_FIXTURE.is_file():
        raise SystemExit(
            "Missing over_8min.mp3 — install ffmpeg and run scripts/generate_long_fixture.py"
        )
    return LONG_FIXTURE


def find_ok_fixture() -> Path:
    for path in OK_FIXTURES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    raise FileNotFoundError(
        "No short fixture found. Add Psychosomatic.mp3 or sample_30s.mp3 under scripts/fixtures/"
    )


def _multipart_body(filename: str, data: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode(),
            data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def post_start_job(base_url: str, fixture: Path) -> tuple[int, str, dict | None]:
    """Returns (status_code, body_text, json_or_none)."""
    data = fixture.read_bytes()
    ctype = "audio/mpeg" if fixture.suffix.lower() == ".mp3" else "application/octet-stream"
    body, multipart = _multipart_body(fixture.name, data, ctype)
    req = Request(
        f"{base_url.rstrip('/')}/start-job",
        data=body,
        headers={"Content-Type": multipart},
        method="POST",
    )
    try:
        with urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = None
            return resp.status, raw, payload
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = None
        return exc.code, raw, payload


def get_job_status(base_url: str, job_id: str) -> dict:
    query = urlencode({"job_id": job_id})
    req = Request(f"{base_url.rstrip('/')}/job-status?{query}", method="GET")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 3 max duration smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
        help="Modal API base URL",
    )
    parser.add_argument(
        "--skip-ok",
        action="store_true",
        help="Only test rejection (skip short fixture upload)",
    )
    args = parser.parse_args()

    print(f"api: {args.base_url}")

    if args.deploy:
        run_deploy()

    long_fixture = ensure_long_fixture()
    print(f"\n[1/2] reject >8 min ({long_fixture.name}) …")
    status, raw, payload = post_start_job(args.base_url, long_fixture)
    if status != 400:
        raise SystemExit(f"expected HTTP 400, got {status}: {raw[:500]}")

    detail = ""
    if isinstance(payload, dict) and payload.get("detail"):
        detail = str(payload["detail"])
    elif raw:
        detail = raw
    if "8" not in detail and "minute" not in detail.lower():
        raise SystemExit(f"expected readable duration error, got: {detail!r}")
    print(f"  HTTP {status}: {detail}")

    if args.skip_ok:
        print("\nPhase 7 Step 3 OK (reject only)")
        return 0

    ok_fixture = find_ok_fixture()
    print(f"\n[2/2] accept short file ({ok_fixture.name}) …")
    status, raw, payload = post_start_job(args.base_url, ok_fixture)
    if status != 200:
        raise SystemExit(f"expected HTTP 200, got {status}: {raw[:500]}")
    job_id = (payload or {}).get("job_id")
    if not job_id:
        raise SystemExit(f"start-job missing job_id: {payload!r}")
    print(f"  job_id: {job_id}")

    deadline = time.time() + POLL_TIMEOUT_S
    last_status = None
    while time.time() < deadline:
        job = get_job_status(args.base_url, str(job_id))
        status_name = job.get("status")
        if status_name != last_status:
            print(f"  {status_name} {job.get('message', '')}".strip())
            last_status = status_name
        if status_name == "failed":
            raise SystemExit(f"short fixture failed: {job.get('error')}")
        if status_name in ("separating", "transcribing", "aligning", "rendering", "done"):
            print("\nPhase 7 Step 3 OK")
            return 0
        time.sleep(POLL_INTERVAL_S)

    raise SystemExit(f"timed out waiting for pipeline start (last={last_status})")


if __name__ == "__main__":
    raise SystemExit(main())
