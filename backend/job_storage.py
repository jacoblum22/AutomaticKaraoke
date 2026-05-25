"""Per-job Modal Volume storage (Phase 6).

Layout: ``/jobs/{job_id}/input.{ext}``
"""

from __future__ import annotations

import shutil
from pathlib import Path

import modal

JOBS_VOLUME_NAME = "karaoke-job-data"
JOBS_MOUNT = "/jobs"

CONTENT_TYPE_EXT = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/flac": ".flac",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
}

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".mp4"}


def jobs_volume() -> modal.Volume:
    return modal.Volume.from_name(JOBS_VOLUME_NAME, create_if_missing=True)


def job_dir(job_id: str) -> Path:
    return Path(JOBS_MOUNT) / job_id


def input_basename(original_filename: str, content_type: str | None) -> str:
    """Return ``input{ext}`` for the uploaded file."""
    ext = ""
    name = original_filename or "upload"
    if "." in name:
        candidate = name[name.rfind(".") :].lower()
        if candidate in ALLOWED_EXTENSIONS:
            ext = candidate
    if not ext and content_type:
        ext = CONTENT_TYPE_EXT.get(content_type.split(";")[0].strip().lower(), "")
    if not ext:
        ext = ".mp3"
    return f"input{ext}"


def input_path(job_id: str, original_filename: str, content_type: str | None) -> Path:
    return job_dir(job_id) / input_basename(original_filename, content_type)


def find_job_input(job_id: str) -> Path | None:
    """First non-empty ``input.*`` under the job directory, if any."""
    directory = job_dir(job_id)
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.glob("input.*")):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def write_job_input(
    job_id: str,
    original_filename: str,
    content_type: str | None,
    data: bytes,
    *,
    volume: modal.Volume,
) -> Path:
    """Write upload bytes and commit to the shared Volume."""
    if not data:
        raise ValueError("upload is empty")
    dest = input_path(job_id, original_filename, content_type)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    volume.commit()
    return dest


def write_job_input_stream(
    job_id: str,
    original_filename: str,
    content_type: str | None,
    chunks: list[bytes],
    *,
    volume: modal.Volume,
) -> tuple[Path, int]:
    """Write chunked upload and commit."""
    total = sum(len(c) for c in chunks)
    if total == 0:
        raise ValueError("upload is empty")
    dest = input_path(job_id, original_filename, content_type)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        for chunk in chunks:
            handle.write(chunk)
    volume.commit()
    return dest, total


def delete_job_workspace(job_id: str, volume: modal.Volume) -> None:
    """Remove ``/jobs/{job_id}`` from the shared Volume."""
    directory = job_dir(job_id)
    if directory.is_dir():
        shutil.rmtree(directory)
        volume.commit()
