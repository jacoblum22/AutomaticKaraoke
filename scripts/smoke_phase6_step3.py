#!/usr/bin/env python3
"""Phase 6 Step 3 — Demucs separation inside the real pipeline.

POST /start-job, wait for separation to finish, verify stems on Volume.
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
MODAL_APP = "karaoke"
DEMUCS_PIPELINE_FN = "smoke_phase6_demucs_pipeline"
VERIFY_STEMS_FN = "verify_job_stems"
DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"

POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 900
POST_SEPARATION = frozenset({"transcribing", "aligning", "rendering", "failed", "done"})

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
        with urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"start-job failed: HTTP {exc.code} {detail}") from exc

    job_id = payload.get("job_id")
    if not job_id:
        raise SystemExit(f"start-job missing job_id: {payload!r}")
    return str(job_id)


def get_job_status(base_url: str, job_id: str) -> dict:
    query = urlencode({"job_id": job_id})
    req = Request(f"{base_url.rstrip('/')}/job-status?{query}", method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"job-status failed: HTTP {exc.code} {detail}") from exc


def poll_past_separation(base_url: str, job_id: str) -> dict:
    """Wait until Demucs finishes (job reaches transcribing or later)."""
    deadline = time.time() + POLL_TIMEOUT_S
    last_status: str | None = None

    while time.time() < deadline:
        job = get_job_status(base_url, job_id)
        status = job.get("status", "")
        if status != last_status:
            print(
                f"  {status} {job.get('progress', 0)} {job.get('message', '')}".strip(),
                flush=True,
            )
            last_status = status

        if status == "failed":
            raise SystemExit(f"pipeline failed: {job.get('error')}")

        if status in POST_SEPARATION:
            return job

        time.sleep(POLL_INTERVAL_S)

    raise SystemExit(
        f"timed out after {POLL_TIMEOUT_S}s waiting for separation "
        f"(last status={last_status})"
    )


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_modal_demucs_smoke() -> dict:
    import modal

    fn = modal.Function.from_name(MODAL_APP, DEMUCS_PIPELINE_FN)
    return fn.remote()


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 3 Demucs pipeline smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Also run POST /start-job + verify_job_stems (API path)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
        help="Modal API base URL",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=20.0,
        help="Expected minimum vocals duration (30s fixture)",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=35.0,
        help="Expected maximum vocals duration (30s fixture)",
    )
    args = parser.parse_args()

    fixture = find_fixture()
    print(f"fixture:  {fixture} ({fixture.stat().st_size} bytes)")
    print(f"api:      {args.base_url}")

    if args.deploy:
        run_deploy()

    print("\n[1/1] modal smoke_phase6_demucs_pipeline …")
    info = run_modal_demucs_smoke()
    print(f"vocals:       {info.get('vocals_path')}")
    print(f"instrumental: {info.get('instrumental_path')}")
    print(
        f"durations:    vocals={info.get('vocals_duration_s'):.2f}s "
        f"instrumental={info.get('instrumental_duration_s'):.2f}s"
    )
    print(
        f"sizes:        vocals={info.get('vocals_bytes')} B "
        f"instrumental={info.get('instrumental_bytes')} B"
    )

    if args.http:
        print("\n[optional] POST /start-job → verify_job_stems …")
        job_id = post_start_job(args.base_url, fixture)
        print(f"job_id:   {job_id}")
        poll_past_separation(args.base_url, job_id)
        import modal

        fn = modal.Function.from_name(MODAL_APP, VERIFY_STEMS_FN)
        http_info = fn.remote(
            job_id,
            min_duration_s=args.min_duration,
            max_duration_s=args.max_duration,
        )
        print(f"http verify: vocals={http_info.get('vocals_duration_s'):.2f}s")

    print("\nPhase 6 Step 3 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
