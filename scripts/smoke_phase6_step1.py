#!/usr/bin/env python3
"""Phase 6 Step 1 — upload persisted to Modal Volume before pipeline spawn.

POST /start-job with a real audio fixture, then verify ``/jobs/{job_id}/input.*``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
MODAL_APP = "karaoke"
VERIFY_FN = "verify_job_input"
DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"

FIXTURE_CANDIDATES = (
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.wav",
)


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def find_fixture() -> Path:
    for path in FIXTURE_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    raise FileNotFoundError(
        "No audio fixture found. Add scripts/fixtures/sample_30s.mp3 or run "
        "scripts/generate_sample_fixture.py"
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


def _content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
    }.get(ext, "application/octet-stream")


def post_start_job(base_url: str, fixture: Path) -> str:
    data = fixture.read_bytes()
    body, ctype = _multipart_body(fixture.name, data, _content_type(fixture))
    req = Request(
        f"{base_url.rstrip('/')}/start-job",
        data=body,
        headers={"Content-Type": ctype},
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"start-job failed: HTTP {exc.code} {detail}") from exc

    job_id = payload.get("job_id")
    if not job_id:
        raise SystemExit(f"start-job missing job_id: {payload!r}")
    return str(job_id)


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 1 job upload smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
        help="Modal API base URL",
    )
    args = parser.parse_args()

    fixture = find_fixture()
    print(f"fixture:  {fixture} ({fixture.stat().st_size} bytes)")
    print(f"api:      {args.base_url}")

    if args.deploy:
        run_deploy()

    job_id = post_start_job(args.base_url, fixture)
    print(f"job_id:   {job_id}")

    import modal

    fn = modal.Function.from_name(MODAL_APP, VERIFY_FN)
    result = fn.remote(job_id, expected_bytes=fixture.stat().st_size)
    print(f"input:    {result.get('input_path')}")
    print(f"size:     {result.get('size_bytes')} bytes")
    print("Phase 6 Step 1 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
