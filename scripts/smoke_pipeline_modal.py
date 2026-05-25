#!/usr/bin/env python3
"""Phase 6 Step 7 — E2E smoke against deployed Modal API.

POST real audio to ``/start-job``, poll ``/job-status`` until ``done``, assert a real
R2 ``video_url`` (not the Phase 2 stub), verify download locally, then clean up.
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

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from smoke_phase6_step6 import cleanup_smoke_jobs, run_deploy, verify_video_url_local

DEPLOYED_API = "https://jacoblum22--karaoke-api.modal.run"
STUB_VIDEO = "https://automatic-karaoke.vercel.app/sample.mp4"

FIXTURE_CANDIDATES = (
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
)

POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 1800
TARGET_WALL_S = 90


def find_fixture(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.is_file() or explicit.stat().st_size == 0:
            raise FileNotFoundError(f"fixture missing or empty: {explicit}")
        return explicit
    for path in FIXTURE_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            if path.name == "sample_30s.mp3":
                print(
                    "warning:  sample_30s.mp3 is a tone — Whisper will fail. "
                    "Add scripts/fixtures/Psychosomatic.mp3 for E2E.",
                    file=sys.stderr,
                )
            return path
    raise FileNotFoundError(
        "No audio fixture found. Copy Psychosomatic.mp3 to scripts/fixtures/ "
        "(see scripts/copy_psychosomatic_fixture.py)."
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
    return {".mp3": "audio/mpeg", ".wav": "audio/wav"}.get(
        path.suffix.lower(), "application/octet-stream"
    )


def post_warm(base_url: str) -> None:
    req = Request(f"{base_url.rstrip('/')}/warm", data=b"", method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status != 202:
                body = resp.read().decode("utf-8", errors="replace")
                raise SystemExit(f"POST /warm expected 202, got {resp.status}: {body}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"POST /warm failed: HTTP {exc.code} {detail}") from exc


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


def poll_job_status(base_url: str, job_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_S
    last_status: str | None = None
    while time.time() < deadline:
        q = urlencode({"job_id": job_id})
        req = Request(f"{base_url.rstrip('/')}/job-status?{q}", method="GET")
        try:
            with urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"job-status failed: HTTP {exc.code} {detail}") from exc

        status = payload.get("status")
        if status != last_status:
            print(
                f"  {status} {payload.get('progress', 0)} "
                f"{payload.get('message', '')}".strip()
            )
            last_status = status

        if status == "failed":
            raise SystemExit(f"job failed: {payload.get('error')}")
        if status == "done":
            return payload
        time.sleep(POLL_INTERVAL_S)

    raise SystemExit(f"poll timed out after {POLL_TIMEOUT_S}s")


def assert_real_video_url(video_url: str, job_id: str) -> None:
    if not video_url:
        raise SystemExit("done without video_url")
    if video_url == STUB_VIDEO or "sample.mp4" in video_url:
        raise SystemExit(f"video_url is still stub: {video_url}")
    if not video_url.startswith("https://"):
        raise SystemExit(f"video_url must be HTTPS: {video_url}")
    if job_id not in video_url:
        raise SystemExit(f"video_url should include job_id {job_id}: {video_url}")
    if "/karaoke/" not in video_url:
        raise SystemExit(f"video_url missing karaoke path: {video_url}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 7 E2E API smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODAL_API_URL", DEPLOYED_API),
        help="Modal API base URL",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Audio file to upload (default: Psychosomatic.mp3 if present)",
    )
    parser.add_argument(
        "--warm",
        action="store_true",
        help="POST /warm before start-job (Phase 7 file-select simulation)",
    )
    parser.add_argument(
        "--warm-wait",
        type=int,
        default=45,
        help="Seconds to wait after /warm before upload (default 45)",
    )
    args = parser.parse_args()

    fixture = find_fixture(args.fixture)
    print(f"fixture:  {fixture.name} ({fixture.stat().st_size} bytes)")
    print(f"api:      {args.base_url}")
    print(
        "note:     Requires Modal secret karaoke-r2 on deployed app. "
        f"Poll timeout {POLL_TIMEOUT_S}s."
    )

    if args.deploy:
        run_deploy()

    if args.warm:
        print(f"\nPOST /warm (wait {args.warm_wait}s before upload) …")
        post_warm(args.base_url)
        time.sleep(args.warm_wait)

    job_id = ""
    cleanup_queue: list[tuple[str, bool]] = []
    try:
        t0 = time.time()
        print("\nPOST /start-job …")
        job_id = post_start_job(args.base_url, fixture)
        cleanup_queue.append((job_id, True))
        print(f"job_id:   {job_id}")

        print("\nPolling /job-status …")
        result = poll_job_status(args.base_url, job_id)
        elapsed = time.time() - t0

        video_url = str(result.get("video_url", ""))
        print(f"\nwall time: {elapsed:.1f}s")
        if elapsed > TARGET_WALL_S:
            print(
                f"note:     exceeded {TARGET_WALL_S}s target (cold GPU starts are normal on "
                "first run; log per-stage times in Modal logs for tuning)"
            )

        assert_real_video_url(video_url, job_id)
        print(f"video_url: {video_url}")
        print("\nVerifying download from this machine …")
        verify_video_url_local(video_url)
        print("\nPhase 6 Step 7 OK")
        return 0
    finally:
        cleanup_smoke_jobs(cleanup_queue)


if __name__ == "__main__":
    raise SystemExit(main())
