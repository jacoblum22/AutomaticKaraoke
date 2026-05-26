#!/usr/bin/env python3
"""Phase 7 Step 1 — structured logging and per-stage timing.

1. Local check: ``log_job_event`` emits parseable JSON.
2. Modal: skeleton pipeline records ``stage_timings`` for separating /
   transcribing / rendering.

For full E2E log lines (including upload), run ``smoke_pipeline_modal.py``
then inspect ``modal app logs karaoke`` filtered by ``job_id``.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
MODAL_FN = "app.py::smoke_phase7_stage_logs"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from smoke_modal import modal_output_text, run_modal, run_modal_deploy  # noqa: E402


def test_log_job_event_local() -> None:
    sys.path.insert(0, str(BACKEND))
    from job_logging import log_job_event  # noqa: WPS433

    buf = io.StringIO()
    with redirect_stdout(buf):
        log_job_event(
            "test-job",
            "separating",
            "stage_start",
            input_duration_s=30.0,
        )
    line = buf.getvalue().strip()
    payload = json.loads(line)
    if payload.get("job_id") != "test-job":
        raise SystemExit(f"unexpected job_id in log line: {payload}")
    if payload.get("stage") != "separating":
        raise SystemExit(f"unexpected stage in log line: {payload}")
    if payload.get("event") != "stage_start":
        raise SystemExit(f"unexpected event in log line: {payload}")
    print(f"  local JSON log OK: {line}")


def run_modal_smoke() -> dict:
    proc = run_modal(MODAL_FN, cwd=BACKEND, root=REPO_ROOT)

    timings: dict[str, float] = {}
    job_id: str | None = None
    saw_pipeline_done = False

    for raw_line in modal_output_text(proc).splitlines():
        raw_line = raw_line.strip()
        if raw_line.startswith("JOB_ID="):
            job_id = raw_line.split("=", 1)[1]
            continue
        if not raw_line.startswith("{"):
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "stage_end" and "elapsed_s" in payload:
            stage = payload.get("stage")
            if isinstance(stage, str):
                timings[stage] = float(payload["elapsed_s"])
        if payload.get("stage") == "pipeline" and payload.get("event") == "done":
            saw_pipeline_done = True

    required = ("separating", "transcribing", "rendering")
    missing = [stage for stage in required if stage not in timings]
    if missing:
        text = modal_output_text(proc)
        raise SystemExit(f"missing stage_end logs for {missing}; stdout:\n{text}")
    if not saw_pipeline_done:
        text = modal_output_text(proc)
        raise SystemExit(f"missing pipeline done log; stdout:\n{text}")

    return {"job_id": job_id or "?", "stage_timings": timings}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 7 Step 1 structured logging smoke"
    )
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Run local JSON helper test only (skip Modal)",
    )
    args = parser.parse_args()

    print("[1/2] local log_job_event JSON …")
    test_log_job_event_local()

    if args.local_only:
        print("\nPhase 7 Step 1 OK (local only)")
        return 0

    if args.deploy:
        run_modal_deploy(REPO_ROOT)

    print("\n[2/2] modal run smoke_phase7_stage_logs …")
    result = run_modal_smoke()
    timings = result.get("stage_timings") or {}
    job_id = result.get("job_id", "?")
    print(f"  job_id:         {job_id}")
    for stage in ("separating", "transcribing", "rendering"):
        print(f"  {stage:14s} {timings.get(stage, '?')}s")

    print(
        "\nE2E logs: run scripts/smoke_pipeline_modal.py, then "
        "modal app logs karaoke (filter by job_id for upload stage)."
    )
    print("\nPhase 7 Step 1 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
