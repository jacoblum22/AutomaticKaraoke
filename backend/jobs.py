"""Job state in modal.Dict (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

import modal

DICT_NAME = "karaoke-jobs"

JOBS = modal.Dict.from_name(DICT_NAME, create_if_missing=True)

JobStatus = Literal[
    "queued",
    "separating",
    "transcribing",
    "aligning",
    "rendering",
    "done",
    "failed",
]


class JobRecord(TypedDict, total=False):
    job_id: str
    status: JobStatus
    progress: int
    message: str
    video_url: str
    error: str
    created_at: str
    stage_timings: dict[str, float]
    is_draft: bool
    r2_upload_key: str
    upload_content_type: str
    upload_filename: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(job_id: str, *, is_draft: bool = False) -> None:
    """Insert a new job in queued state."""
    record: JobRecord = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Waiting for upload…" if is_draft else "Queued…",
        "created_at": _utc_now_iso(),
    }
    if is_draft:
        record["is_draft"] = True
    JOBS[job_id] = record


def get_job(job_id: str) -> JobRecord | None:
    """Return job record or None if missing."""
    raw = JOBS.get(job_id)
    if raw is None:
        return None
    return dict(raw)


def update_job(job_id: str, **fields: Any) -> None:
    """Merge fields into an existing job record."""
    job = get_job(job_id)
    if job is None:
        raise KeyError(f"Unknown job_id: {job_id}")
    job.update(fields)
    JOBS[job_id] = job


def set_failed(job_id: str, error: str) -> None:
    """Mark job failed with an error message."""
    update_job(
        job_id,
        status="failed",
        error=error,
        message="Processing failed",
        progress=0,
    )


def delete_job(job_id: str) -> bool:
    """Remove a job (smoke tests / cleanup). Returns True if it existed."""
    try:
        del JOBS[job_id]
        return True
    except KeyError:
        return False


def iter_jobs() -> list[tuple[str, JobRecord]]:
    """Return all ``(job_id, record)`` pairs from the shared Dict."""
    pairs: list[tuple[str, JobRecord]] = []
    for job_id in JOBS.keys():
        raw = JOBS.get(job_id)
        if raw is not None:
            pairs.append((str(job_id), dict(raw)))
    return pairs
