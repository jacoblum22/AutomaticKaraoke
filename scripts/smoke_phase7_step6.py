#!/usr/bin/env python3
"""Phase 7 Step 6 — presigned R2 upload path.

1. Modal: presigned PUT → sync to Volume.
2. HTTP: draft → upload-url → PUT → sync-upload → finalize → pipeline start.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"

MODAL_FN = "app.py::smoke_phase7_r2_upload_gate"

OK_FIXTURES = (
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
)

POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 120

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from smoke_api import api_key_header, request_json  # noqa: E402
from smoke_modal import run_modal, run_modal_deploy  # noqa: E402


def run_modal_smoke() -> None:
    run_modal(MODAL_FN, cwd=BACKEND, root=REPO_ROOT)
    if "R2_UPLOAD_GATE_OK" not in proc.stdout:
        raise SystemExit("missing R2_UPLOAD_GATE_OK in modal output")


def find_fixture() -> Path:
    for path in OK_FIXTURES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    raise FileNotFoundError("Need sample_30s.mp3 or Psychosomatic.mp3 under scripts/fixtures/")


def put_presigned(url: str, fixture: Path, content_type: str) -> None:
    from urllib.request import Request, urlopen

    data = fixture.read_bytes()
    req = Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": content_type},
    )
    with urlopen(req, timeout=300) as resp:
        if resp.status not in (200, 201, 204):
            raise SystemExit(f"presigned PUT failed: HTTP {resp.status}")


def poll_processing(base_url: str, job_id: str) -> None:
    deadline = time.time() + POLL_TIMEOUT_S
    last = None
    while time.time() < deadline:
        status, job = request_json(
            f"{base_url.rstrip('/')}/job-status?job_id={job_id}",
            timeout=30,
        )
        if status != 200 or not isinstance(job, dict):
            raise SystemExit(f"job-status failed: {status} {job}")
        name = job.get("status")
        if name != last:
            print(f"  {name} {job.get('message', '')}".strip())
            last = name
        if name == "failed":
            raise SystemExit(f"job failed: {job.get('error')}")
        if name in ("separating", "transcribing", "aligning", "rendering", "done"):
            return
        time.sleep(POLL_INTERVAL_S)
    raise SystemExit(f"timed out (last={last})")


def test_http_r2_path(base_url: str) -> None:
    print("\n[2/2] HTTP presigned upload → finalize …")
    status, cfg = request_json(f"{base_url.rstrip('/')}/config")
    if status != 200 or not isinstance(cfg, dict):
        raise SystemExit(f"config failed: {status} {cfg}")
    if not cfg.get("r2_upload"):
        raise SystemExit("server config r2_upload=false — check karaoke-r2 secret")

    fixture = find_fixture()
    content_type = "audio/mpeg" if fixture.suffix.lower() == ".mp3" else "application/octet-stream"

    status, draft = request_json(
        f"{base_url.rstrip('/')}/draft-job",
        method="POST",
        data=b"",
    )
    if status != 200 or not isinstance(draft, dict):
        raise SystemExit(f"draft-job failed: {status} {draft}")
    job_id = draft.get("job_id")
    if not job_id:
        raise SystemExit(f"draft-job missing job_id: {draft}")

    body = json.dumps(
        {
            "job_id": job_id,
            "filename": fixture.name,
            "content_type": content_type,
            "size": fixture.stat().st_size,
        }
    ).encode()
    status, upload_meta = request_json(
        f"{base_url.rstrip('/')}/upload-url",
        method="POST",
        data=body,
        headers={"Content-Type": "application/json", **api_key_header()},
    )
    if status != 200 or not isinstance(upload_meta, dict):
        raise SystemExit(f"upload-url failed: {status} {upload_meta}")

    upload_url = upload_meta.get("upload_url")
    signed_type = upload_meta.get("content_type", content_type)
    if not upload_url:
        raise SystemExit(f"upload-url missing upload_url: {upload_meta}")

    print(f"  PUT {fixture.name} → R2 …")
    put_presigned(str(upload_url), fixture, str(signed_type))

    status, sync = request_json(
        f"{base_url.rstrip('/')}/draft-job/{job_id}/sync-upload",
        method="POST",
        data=b"",
    )
    if status != 200:
        raise SystemExit(f"sync-upload failed: {status} {sync}")

    from urllib.parse import urlencode

    q = urlencode({"job_id": job_id})
    status, _final = request_json(
        f"{base_url.rstrip('/')}/finalize-job?{q}",
        method="POST",
        data=b"",
    )
    if status == 429:
        raise SystemExit("finalize rate limited — reset rate limits and retry")
    if status != 200:
        raise SystemExit(f"finalize failed: {status} {_final}")

    print(f"  job_id: {job_id}")
    poll_processing(base_url, str(job_id))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 6 presigned R2 smoke")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
    )
    parser.add_argument("--modal-only", action="store_true", help="Skip HTTP E2E")
    args = parser.parse_args()

    print(f"api: {args.base_url}")

    if args.deploy:
        run_modal_deploy(REPO_ROOT)

    print("\n[1/2] modal run smoke_phase7_r2_upload_gate …")
    run_modal_smoke()

    if not args.modal_only:
        try:
            run_modal(
                "app.py::smoke_phase7_rate_limit_reset",
                cwd=BACKEND,
                root=REPO_ROOT,
                echo_cmd=False,
            )
        except SystemExit:
            pass
        test_http_r2_path(args.base_url)

    print("\nPhase 7 Step 6 OK")
    print("Browser: enable R2 CORS — see docs/r2-cors.example.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
