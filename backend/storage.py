"""R2/S3 upload and public URL for finished karaoke MP4 (Phase 6).

Phase 7 Step 6: presigned browser uploads to ``uploads/{job_id}/input.*``.
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any

KARAOKE_KEY_PREFIX = "karaoke"
UPLOAD_KEY_PREFIX = "uploads"
PRESIGNED_PUT_EXPIRES_S = 3600


class StorageError(RuntimeError):
    """R2 upload or URL configuration failed."""


def karaoke_object_key(job_id: str) -> str:
    return f"{KARAOKE_KEY_PREFIX}/{job_id}/karaoke.mp4"


def upload_object_key(job_id: str, input_name: str) -> str:
    """R2 key for a presigned input upload (``uploads/{job_id}/input.*``)."""
    return f"{UPLOAD_KEY_PREFIX}/{job_id}/{input_name}"


def r2_configured() -> bool:
    """True when R2 env vars are present (presigned upload available)."""
    try:
        _require_env("R2_BUCKET")
        _require_env("R2_ENDPOINT_URL")
        _require_env("R2_ACCESS_KEY_ID")
        _require_env("R2_SECRET_ACCESS_KEY")
        return True
    except StorageError:
        return False


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


def presigned_put_upload(
    job_id: str,
    *,
    filename: str,
    content_type: str,
    size: int,
    max_bytes: int,
) -> dict[str, Any]:
    """Return a presigned PUT URL and object key for a draft input upload."""
    from job_storage import input_basename

    if size <= 0 or size > max_bytes:
        raise StorageError(
            f"invalid upload size {size} (max {max_bytes // (1024 * 1024)} MB)"
        )

    input_name = input_basename(filename, content_type)
    object_key = upload_object_key(job_id, input_name)
    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    try:
        upload_url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGNED_PUT_EXPIRES_S,
        )
    except Exception as exc:
        raise StorageError(f"presigned URL failed: {exc}") from exc

    return {
        "job_id": job_id,
        "upload_url": upload_url,
        "object_key": object_key,
        "content_type": content_type,
        "max_bytes": max_bytes,
    }


def upload_object_exists(object_key: str) -> bool:
    from botocore.exceptions import ClientError

    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    try:
        client.head_object(Bucket=bucket, Key=object_key)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise StorageError(f"R2 head failed: {exc}") from exc


def download_upload_object(object_key: str, *, max_bytes: int) -> tuple[bytes, str | None]:
    """Download a presigned upload object; returns bytes and Content-Type."""
    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    try:
        head = client.head_object(Bucket=bucket, Key=object_key)
        size = int(head.get("ContentLength", 0))
        if size <= 0 or size > max_bytes:
            raise StorageError(f"upload object size invalid: {size}")
        buffer = BytesIO()
        client.download_fileobj(bucket, object_key, buffer)
        data = buffer.getvalue()
        if len(data) != size:
            raise StorageError(f"download size mismatch: {len(data)} vs {size}")
        content_type = head.get("ContentType")
        return data, content_type
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"R2 download failed: {exc}") from exc


def delete_upload_object(object_key: str) -> None:
    delete_object(object_key)


def delete_job_upload(job_id: str, object_key: str | None = None) -> None:
    """Delete presigned input object(s) for a job."""
    if object_key:
        try:
            delete_upload_object(object_key)
        except StorageError:
            pass
        return
    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    prefix = f"{UPLOAD_KEY_PREFIX}/{job_id}/"
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if key:
                    delete_object(key)
    except Exception as exc:
        raise StorageError(f"R2 upload prefix delete failed: {exc}") from exc


def karaoke_mp4_exists(job_id: str) -> bool:
    """Return True if the job's karaoke MP4 object exists in R2."""
    from botocore.exceptions import ClientError

    bucket = _require_env("R2_BUCKET")
    client = _s3_client()
    try:
        client.head_object(Bucket=bucket, Key=karaoke_object_key(job_id))
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise StorageError(f"R2 head failed: {exc}") from exc
