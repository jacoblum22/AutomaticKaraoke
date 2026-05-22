"""Stub pipeline (Phase 2) — sleep + Dict updates; no ML."""

from __future__ import annotations

import time

from jobs import JobStatus, set_failed, update_job

STUB_VIDEO_URL = "https://automatic-karaoke.vercel.app/sample.mp4"

STAGE_SLEEP_S = 2

# After create_job (queued), advance through these stages then done.
PIPELINE_STAGES: list[tuple[JobStatus, int, str]] = [
    ("separating", 20, "Separating vocals…"),
    ("transcribing", 40, "Transcribing vocals…"),
    ("aligning", 60, "Aligning lyrics…"),
    ("rendering", 80, "Rendering karaoke video…"),
]


def run_stub_pipeline(job_id: str, *, simulate_fail: bool = False) -> None:
    """Advance job through stub stages. Caller must create_job first."""
    try:
        for status, progress, message in PIPELINE_STAGES:
            if simulate_fail and status == "transcribing":
                raise RuntimeError("stub pipeline simulated failure")
            update_job(job_id, status=status, progress=progress, message=message)
            time.sleep(STAGE_SLEEP_S)

        update_job(
            job_id,
            status="done",
            progress=100,
            message="Complete!",
            video_url=STUB_VIDEO_URL,
        )
    except Exception as exc:
        set_failed(job_id, str(exc))
