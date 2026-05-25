"""R2/S3 upload and public URL for finished karaoke MP4 (Phase 6)."""

from __future__ import annotations

import os
from pathlib import Path

KARAOKE_KEY_PREFIX = "karaoke"


class StorageError(RuntimeError):
    """R2 upload or URL configuration failed."""


def karaoke_object_key(job_id: str) -> str:
    return f"{KARAOKE_KEY_PREFIX}/{job_id}/karaoke.mp4"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise StorageError(f"Missing environment variable: {name}")
    return value


def public_video_url(object_key: str) -> str:
    """Build HTTPS URL for an object key using ``R2_PUBLIC_BASE_URL``."""
    base = _require_env("R2_PUBLIC_BASE_URL").rstrip("/")
    return f"{base}/{object_key.lstrip('/')}"


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=_require_env("R2_ENDPOINT_URL"),
        aws_access_key_id=_require_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def upload_file(local_path: Path | str, object_key: str) -> str:
    """Upload a local file to R2 and return its public HTTPS URL."""
    path = Path(local_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise StorageError(f"upload source missing or empty: {path}")

    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    try:
        client.upload_file(
            str(path),
            bucket,
            object_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
    except Exception as exc:
        raise StorageError(f"R2 upload failed: {exc}") from exc

    return public_video_url(object_key)


def upload_karaoke_mp4(local_path: Path | str, job_id: str) -> str:
    """Upload ``karaoke.mp4`` for a job; returns the public ``video_url``."""
    return upload_file(local_path, karaoke_object_key(job_id))


def delete_object(object_key: str) -> None:
    """Remove one object from R2 (no-op if the key is already gone)."""
    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=object_key)
    except Exception as exc:
        raise StorageError(f"R2 delete failed: {exc}") from exc


def delete_karaoke_mp4(job_id: str) -> None:
    """Delete ``karaoke/{job_id}/karaoke.mp4`` from R2."""
    delete_object(karaoke_object_key(job_id))
