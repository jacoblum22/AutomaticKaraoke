#!/usr/bin/env python3
"""Phase 6 Step 6 — R2 upload + deliverable video_url.

Requires Modal secret ``karaoke-r2`` with R2 credentials and ``R2_PUBLIC_BASE_URL``.
Smoke runs delete R2 objects and Volume workspaces when finished.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
MODAL_APP = "karaoke"
R2_UPLOAD_FN = "smoke_phase6_r2_upload"
DELIVER_PIPELINE_FN = "smoke_phase6_deliver_pipeline"
CLEANUP_FN = "smoke_phase6_cleanup"


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def verify_video_url_local(url: str) -> None:
    """GET from the developer machine (r2.dev may block cloud egress)."""
    import urllib.error
    import urllib.request

    if not url.startswith("https://"):
        raise SystemExit(f"video_url must be HTTPS: {url}")
    if "sample.mp4" in url:
        raise SystemExit(f"video_url must not be stub: {url}")

    req = urllib.request.Request(
        url,
        headers={"Range": "bytes=0-1023", "User-Agent": "AutomaticKaraoke-smoke/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 206):
                raise SystemExit(f"video_url returned HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"video_url not accessible from this machine: HTTP {exc.code}\n{url}"
        ) from exc


def cleanup_smoke_jobs(jobs: list[tuple[str, bool]]) -> None:
    """Remove R2 (and optionally Volume) artifacts for smoke job ids."""
    import modal

    if not jobs:
        return
    fn = modal.Function.from_name(MODAL_APP, CLEANUP_FN)
    print("\nCleaning up smoke storage …")
    for job_id, had_volume in jobs:
        print(f"  {job_id}" + (" (+ volume)" if had_volume else ""))
        fn.remote(job_id, volume=had_volume)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 6 R2 upload smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--upload-only",
        action="store_true",
        help="Only run smoke_phase6_r2_upload (skip full deliver pipeline)",
    )
    args = parser.parse_args()

    print(
        "note:     Requires Modal secret karaoke-r2 "
        "(R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_ENDPOINT_URL, "
        "R2_PUBLIC_BASE_URL)."
    )

    if args.deploy:
        run_deploy()

    import modal

    cleanup_queue: list[tuple[str, bool]] = []
    info: dict[str, Any] = {}
    try:
        if args.upload_only:
            print("\n[1/1] modal smoke_phase6_r2_upload …")
            info = modal.Function.from_name(MODAL_APP, R2_UPLOAD_FN).remote(cleanup=False)
            cleanup_queue.append((str(info["job_id"]), False))
        else:
            print("\n[1/2] modal smoke_phase6_r2_upload …")
            upload_info = modal.Function.from_name(MODAL_APP, R2_UPLOAD_FN).remote(cleanup=False)
            cleanup_queue.append((str(upload_info["job_id"]), False))
            print(f"  object:   {upload_info.get('object_key')}")
            print(f"  url:      {upload_info.get('video_url')}")

            print("\n[2/2] modal smoke_phase6_deliver_pipeline …")
            info = modal.Function.from_name(MODAL_APP, DELIVER_PIPELINE_FN).remote(
                cleanup=False
            )
            cleanup_queue.append((str(info["job_id"]), True))

        video_url = str(info.get("video_url", ""))
        print(f"\njob_id:     {info.get('job_id')}")
        print(f"video_url:  {video_url}")
        print("\nVerifying download from this machine …")
        verify_video_url_local(video_url)
        print("\nPhase 6 Step 6 OK")
        return 0
    finally:
        cleanup_smoke_jobs(cleanup_queue)


if __name__ == "__main__":
    raise SystemExit(main())
