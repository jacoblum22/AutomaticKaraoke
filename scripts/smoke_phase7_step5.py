#!/usr/bin/env python3
"""Phase 7 Step 5 — rate limit on job starts (start-job / finalize-job).

1. Modal module test: 6th consume in the same window raises.
2. HTTP burst: 6 finalize calls on missing jobs → 6th returns 429.
3. HTTP single start-job with short fixture → not 429 (reaches processing).
"""

from __future__ import annotations

import argparse
import json
import os
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

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from smoke_api import api_key_header, request_json  # noqa: E402
from smoke_modal import run_modal  # noqa: E402

MODAL_MODULE_FN = "app.py::smoke_phase7_rate_limit_module"
MODAL_RESET_FN = "app.py::smoke_phase7_rate_limit_reset"

OK_FIXTURES = (
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
)

POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 90


def run_deploy() -> None:
    from smoke_modal import run_modal_deploy

    run_modal_deploy(REPO_ROOT)


def post_finalize(base_url: str, job_id: str) -> tuple[int, str]:
    q = urlencode({"job_id": job_id})
    req = Request(
        f"{base_url.rstrip('/')}/finalize-job?{q}",
        data=b"",
        headers=api_key_header(),
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def find_ok_fixture() -> Path:
    for path in OK_FIXTURES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    raise FileNotFoundError(
        "No short fixture found. Add sample_30s.mp3 or Psychosomatic.mp3 under scripts/fixtures/"
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
    data = fixture.read_bytes()
    ctype = "audio/mpeg" if fixture.suffix.lower() == ".mp3" else "application/octet-stream"
    body, multipart = _multipart_body(fixture.name, data, ctype)
    req = Request(
        f"{base_url.rstrip('/')}/start-job",
        data=body,
        headers={**api_key_header(), "Content-Type": multipart},
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
    q = urlencode({"job_id": job_id})
    req = Request(
        f"{base_url.rstrip('/')}/job-status?{q}",
        headers=api_key_header(),
        method="GET",
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_burst_finalize(base_url: str, *, limit: int = 5) -> None:
    print(f"\n[2/3] HTTP burst finalize (limit={limit}) …")
    statuses: list[int] = []
    for i in range(limit + 1):
        job_id = str(uuid.uuid4())
        status, body = post_finalize(base_url, job_id)
        statuses.append(status)
        print(f"  request {i + 1}: HTTP {status}")
        if status == 429:
            detail = ""
            try:
                payload = json.loads(body)
                detail = str(payload.get("detail", ""))
            except json.JSONDecodeError:
                detail = body
            if "rate limit" not in detail.lower():
                raise SystemExit(f"expected rate limit message, got: {detail!r}")
            if i != limit:
                raise SystemExit(f"429 too early on request {i + 1}")
            return
    raise SystemExit(f"expected HTTP 429 on request {limit + 1}, got {statuses}")


def test_single_start_job(base_url: str) -> None:
    fixture = find_ok_fixture()
    print(f"\n[3/3] HTTP single start-job ({fixture.name}) …")
    status, raw, payload = post_start_job(base_url, fixture)
    if status == 429:
        raise SystemExit(f"unexpected 429 on single upload: {raw[:500]}")
    if status != 200:
        raise SystemExit(f"expected HTTP 200, got {status}: {raw[:500]}")
    job_id = (payload or {}).get("job_id")
    if not job_id:
        raise SystemExit(f"start-job missing job_id: {payload!r}")
    print(f"  job_id: {job_id}")

    deadline = time.time() + POLL_TIMEOUT_S
    last_status = None
    while time.time() < deadline:
        job = get_job_status(base_url, str(job_id))
        status_name = job.get("status")
        if status_name != last_status:
            print(f"  {status_name} {job.get('message', '')}".strip())
            last_status = status_name
        if status_name == "failed":
            raise SystemExit(f"job failed: {job.get('error')}")
        if status_name in ("separating", "transcribing", "aligning", "rendering", "done"):
            print("  not rate limited (pipeline started)")
            return
        time.sleep(POLL_INTERVAL_S)
    raise SystemExit(f"timed out waiting for pipeline start (last={last_status})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 5 rate limit smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
        help="Modal API base URL",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip single start-job test (burst + module only)",
    )
    args = parser.parse_args()

    print(f"api: {args.base_url}")

    if args.deploy:
        run_deploy()

    status, cfg = request_json(f"{args.base_url.rstrip('/')}/config")
    if status == 200 and isinstance(cfg, dict) and cfg.get("api_key_required"):
        if not os.environ.get("KARAOKE_API_KEY", "").strip():
            raise SystemExit(
                "API key required on deployed API. Set KARAOKE_API_KEY to the Modal "
                "secret karaoke-api-key value before running HTTP rate-limit tests."
            )

    print("\n[1/3] modal run smoke_phase7_rate_limit_module …")
    run_modal(MODAL_MODULE_FN, cwd=BACKEND, root=REPO_ROOT)

    print("\n  reset rate-limit Dict …")
    run_modal(MODAL_RESET_FN, cwd=BACKEND, root=REPO_ROOT)

    test_burst_finalize(args.base_url)

    run_modal(MODAL_RESET_FN, cwd=BACKEND, root=REPO_ROOT)

    if not args.skip_upload:
        test_single_start_job(args.base_url)

    print("\nPhase 7 Step 5 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
