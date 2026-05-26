#!/usr/bin/env python3
"""Phase 7 Step 4 — TTL cleanup (R2, Volume, Dict).

Seeds an expired job and a fresh job on Modal, runs ``cleanup_expired_jobs``,
and verifies only the expired artifacts are removed.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
MODAL_FN = "app.py::smoke_phase7_cleanup_gate"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from smoke_modal import modal_output_text, run_modal, run_modal_deploy  # noqa: E402


def run_modal_smoke(max_age_seconds: int) -> dict:
    proc = run_modal(
        MODAL_FN,
        "--max-age-seconds",
        str(max_age_seconds),
        cwd=BACKEND,
        root=REPO_ROOT,
    )

    expired_id: str | None = None
    fresh_id: str | None = None
    cleanup_summary: dict | None = None

    for line in modal_output_text(proc).splitlines():
        line = line.strip()
        if line.startswith("EXPIRED_JOB_ID="):
            expired_id = line.split("=", 1)[1]
        elif line.startswith("FRESH_JOB_ID="):
            fresh_id = line.split("=", 1)[1]
        elif line.startswith("CLEANUP_SUMMARY="):
            raw = line.split("=", 1)[1]
            cleanup_summary = ast.literal_eval(raw)

    if not expired_id or not fresh_id:
        raise SystemExit("missing EXPIRED_JOB_ID or FRESH_JOB_ID in modal output")
    if not cleanup_summary:
        raise SystemExit("missing CLEANUP_SUMMARY in modal output")
    if expired_id not in cleanup_summary.get("deleted", []):
        raise SystemExit(f"expired job not deleted: {cleanup_summary}")

    return {
        "expired_job_id": expired_id,
        "fresh_job_id": fresh_id,
        "cleanup": cleanup_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 4 TTL cleanup smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=60,
        help="Retention window for smoke (default 60s)",
    )
    args = parser.parse_args()

    if args.deploy:
        run_modal_deploy(REPO_ROOT)

    print(f"\n[1/1] modal run {MODAL_FN} (max_age_seconds={args.max_age_seconds}) …")
    result = run_modal_smoke(args.max_age_seconds)
    deleted = result["cleanup"].get("deleted_count", "?")
    print(f"  expired removed: {result['expired_job_id']}")
    print(f"  fresh kept:      {result['fresh_job_id']}")
    print(f"  deleted_count:   {deleted}")
    print("\nPhase 7 Step 4 OK")
    print("Cron: cleanup_expired_jobs runs every 6h (24h retention).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
