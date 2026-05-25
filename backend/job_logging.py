"""Structured job logging for Modal stdout (Phase 7 Step 1)."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from jobs import get_job, update_job


def log_job_event(job_id: str, stage: str, event: str, **fields: Any) -> None:
    """Emit one JSON line to stdout for Modal log aggregation."""
    payload = {"job_id": job_id, "stage": stage, "event": event, **fields}
    print(json.dumps(payload, sort_keys=True), flush=True)

    if event == "stage_end" and "elapsed_s" in fields:
        job = get_job(job_id)
        if job is not None:
            timings = dict(job.get("stage_timings") or {})
            timings[stage] = fields["elapsed_s"]
            update_job(job_id, stage_timings=timings)


@contextmanager
def stage_timer(job_id: str, stage: str) -> Iterator[None]:
    """Log stage_start / stage_end with elapsed_s."""
    log_job_event(job_id, stage, "stage_start")
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed_s = round(time.perf_counter() - t0, 3)
        log_job_event(job_id, stage, "stage_end", elapsed_s=elapsed_s)


def probe_media_duration_s(path: Path) -> float | None:
    """Return media duration in seconds via ffprobe, or None if unavailable."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError):
        return None
