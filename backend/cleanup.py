"""TTL cleanup for R2, Volume workspaces, and job Dict rows (Phase 7 Step 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import modal

from jobs import JobRecord, delete_job, iter_jobs

ACTIVE_STATUSES = frozenset(
    {"separating", "transcribing", "aligning", "rendering"}
)
DEFAULT_MAX_AGE_HOURS = 24


def _parse_created_at(created_at: str | None) -> datetime | None:
    if not created_at:
        return None
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _max_age_delta(
    *,
    max_age_hours: float,
    max_age_seconds: int | None,
) -> timedelta:
    if max_age_seconds is not None:
        return timedelta(seconds=max_age_seconds)
    return timedelta(hours=max_age_hours)


def job_is_expired(
    record: JobRecord,
    *,
    now: datetime,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    max_age_seconds: int | None = None,
) -> bool:
    """True when ``created_at`` is older than the retention window."""
    created = _parse_created_at(record.get("created_at"))
    if created is None:
        return True
    cutoff = now - _max_age_delta(
        max_age_hours=max_age_hours,
        max_age_seconds=max_age_seconds,
    )
    return created <= cutoff


def job_should_cleanup(
    record: JobRecord,
    *,
    now: datetime | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    max_age_seconds: int | None = None,
) -> bool:
    """Expired jobs are removed unless a GPU stage is still in flight."""
    if now is None:
        now = datetime.now(timezone.utc)
    if not job_is_expired(
        record,
        now=now,
        max_age_hours=max_age_hours,
        max_age_seconds=max_age_seconds,
    ):
        return False
    return record.get("status", "queued") not in ACTIVE_STATUSES


def delete_job_artifacts(
    job_id: str,
    volume: modal.Volume,
    *,
    r2: bool = True,
    dict_row: bool = True,
    r2_upload_key: str | None = None,
) -> dict[str, bool]:
    """Remove R2 MP4, presigned upload, Volume workspace, and optional Dict row."""
    result = {"r2": False, "r2_upload": False, "volume": False, "dict": False}
    if r2:
        from storage import StorageError, delete_job_upload, delete_karaoke_mp4

        try:
            delete_karaoke_mp4(job_id)
            result["r2"] = True
        except StorageError as exc:
            print(f"note: R2 cleanup ({job_id}): {exc}", flush=True)
        try:
            delete_job_upload(job_id, r2_upload_key)
            result["r2_upload"] = True
        except StorageError as exc:
            print(f"note: R2 upload cleanup ({job_id}): {exc}", flush=True)
    from job_storage import delete_job_workspace

    delete_job_workspace(job_id, volume)
    result["volume"] = True
    if dict_row:
        result["dict"] = delete_job(job_id)
    return result


def cleanup_expired_jobs(
    *,
    volume: modal.Volume,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    max_age_seconds: int | None = None,
    r2: bool = True,
) -> dict[str, Any]:
    """Sweep expired jobs from R2, Volume, and the job Dict."""
    now = datetime.now(timezone.utc)
    scanned = 0
    deleted: list[str] = []
    skipped_fresh = 0
    skipped_active = 0

    for job_id, record in iter_jobs():
        scanned += 1
        if not job_is_expired(
            record,
            now=now,
            max_age_hours=max_age_hours,
            max_age_seconds=max_age_seconds,
        ):
            skipped_fresh += 1
            continue
        if record.get("status", "queued") in ACTIVE_STATUSES:
            skipped_active += 1
            continue
        upload_key = record.get("r2_upload_key")
        delete_job_artifacts(
            job_id,
            volume,
            r2=r2,
            r2_upload_key=upload_key if isinstance(upload_key, str) else None,
        )
        deleted.append(job_id)

    summary: dict[str, Any] = {
        "scanned": scanned,
        "deleted": deleted,
        "deleted_count": len(deleted),
        "skipped_fresh": skipped_fresh,
        "skipped_active": skipped_active,
        "max_age_hours": max_age_hours,
        "max_age_seconds": max_age_seconds,
    }
    print(f"CLEANUP_SUMMARY={summary}", flush=True)
    return summary
