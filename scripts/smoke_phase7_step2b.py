#!/usr/bin/env python3
"""Phase 7 Step 2b — early upload on file select + safe file replace.

1. Draft upload + finalize reaches processing.
2. Replace draft A with draft B before finalize — B wins, A discarded.
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

FILE_A = REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3"
FILE_B_CANDIDATES = (
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.wav",
)

POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 90


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def find_file_b() -> Path:
    for path in FILE_B_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    raise FileNotFoundError("Need Psychosomatic.mp3 or sample_30s.wav for replace test")


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


def post_json(base_url: str, path: str, method: str = "POST") -> dict:
    req = Request(f"{base_url.rstrip('/')}{path}", data=b"", method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {path} failed: HTTP {exc.code} {detail}") from exc


def upload_draft(base_url: str, job_id: str, fixture: Path) -> None:
    data = fixture.read_bytes()
    ctype = "audio/mpeg" if fixture.suffix.lower() == ".mp3" else "application/octet-stream"
    body, multipart = _multipart_body(fixture.name, data, ctype)
    req = Request(
        f"{base_url.rstrip('/')}/draft-job/{job_id}/upload",
        data=body,
        headers={"Content-Type": multipart},
        method="POST",
    )
    try:
        with urlopen(req, timeout=300) as resp:
            if resp.status < 200 or resp.status >= 300:
                raise SystemExit(f"upload failed: HTTP {resp.status}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"upload failed: HTTP {exc.code} {detail}") from exc


def delete_draft(base_url: str, job_id: str) -> None:
    req = Request(
        f"{base_url.rstrip('/')}/draft-job/{job_id}",
        data=b"",
        method="DELETE",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            resp.read()
    except HTTPError as exc:
        if exc.code != 404:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"delete failed: HTTP {exc.code} {detail}") from exc


def finalize_job(base_url: str, job_id: str) -> None:
    q = urlencode({"job_id": job_id})
    req = Request(f"{base_url.rstrip('/')}/finalize-job?{q}", data=b"", method="POST")
    try:
        with urlopen(req, timeout=60) as resp:
            resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"finalize failed: HTTP {exc.code} {detail}") from exc


def get_job_status(base_url: str, job_id: str) -> dict:
    q = urlencode({"job_id": job_id})
    req = Request(f"{base_url.rstrip('/')}/job-status?{q}", method="GET")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def poll_until_processing(base_url: str, job_id: str) -> None:
    deadline = time.time() + POLL_TIMEOUT_S
    last = None
    while time.time() < deadline:
        job = get_job_status(base_url, job_id)
        status = job.get("status")
        if status != last:
            print(f"  {status} {job.get('message', '')}".strip())
            last = status
        if status == "failed":
            raise SystemExit(f"job failed: {job.get('error')}")
        if status in ("separating", "transcribing", "aligning", "rendering", "done"):
            return
        time.sleep(POLL_INTERVAL_S)
    raise SystemExit(f"timed out (last status={last})")


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 2b early upload smoke")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
    )
    args = parser.parse_args()

    if not FILE_A.is_file():
        raise SystemExit(f"missing fixture: {FILE_A}")

    file_b = find_file_b()
    print(f"api:     {args.base_url}")
    print(f"file A:  {FILE_A.name}")
    print(f"file B:  {file_b.name}")

    if args.deploy:
        run_deploy()

    print("\n[1/2] replace draft A → B, finalize B …")
    draft_a = post_json(args.base_url, "/draft-job")["job_id"]
    upload_draft(args.base_url, draft_a, FILE_A)
    print(f"  draft A uploaded: {draft_a}")

    draft_b = post_json(args.base_url, "/draft-job")["job_id"]
    delete_draft(args.base_url, draft_a)
    print(f"  draft A deleted")

    upload_draft(args.base_url, draft_b, file_b)
    print(f"  draft B uploaded: {draft_b}")

    finalize_job(args.base_url, draft_b)
    poll_until_processing(args.base_url, draft_b)

    try:
        get_job_status(args.base_url, draft_a)
        raise SystemExit("draft A should be deleted from job Dict")
    except HTTPError as exc:
        if exc.code != 404:
            raise SystemExit(f"unexpected status for deleted draft A: {exc.code}") from exc
    print("  draft A not found in job-status (discarded)")

    print("\nPhase 7 Step 2b OK")
    print("UI: drop file → draft upload + /warm; submit → finalize-job (fast)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
