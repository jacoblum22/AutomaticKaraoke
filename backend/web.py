"""FastAPI HTTP API (Phase 2 Step 3)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from auth import api_key_configured, verify_api_key
from jobs import create_job, delete_job, get_job, set_failed, update_job
from rate_limit import check_rate_limit

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "audio/flac",
    "audio/ogg",
    "audio/webm",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".mp4"}

CORS_ORIGINS = [
    "https://automatic-karaoke.vercel.app",
    "http://localhost:5173",
    "http://localhost:5174",
]


def _validate_upload(filename: str, content_type: str | None, size: int) -> None:
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    ext = ""
    if "." in filename:
        ext = filename[filename.rfind(".") :].lower()
    if content_type and content_type in ALLOWED_CONTENT_TYPES:
        return
    if ext in ALLOWED_EXTENSIONS:
        return
    raise HTTPException(
        status_code=400,
        detail="Unsupported audio type. Use MP3, WAV, M4A, FLAC, or OGG.",
    )


async def _read_upload(audio: UploadFile) -> tuple[str, str | None, list[bytes], int]:
    """Drain multipart upload into chunks; return filename, content_type, chunks, total."""
    declared = audio.size or 0
    filename = audio.filename or "upload"
    _validate_upload(filename, audio.content_type, declared)

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await audio.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
            )
        chunks.append(chunk)

    if declared == 0 and total > 0:
        _validate_upload(filename, audio.content_type, total)

    return filename, audio.content_type, chunks, total


def _persist_upload(
    job_id: str,
    filename: str,
    content_type: str | None,
    chunks: list[bytes],
    *,
    jobs_volume: Any,
) -> Path:
    """Write upload to Volume and enforce max duration."""
    from job_storage import write_job_input_stream

    dest, written = write_job_input_stream(
        job_id,
        filename,
        content_type,
        chunks,
        volume=jobs_volume,
    )
    print(f"JOB_INPUT job_id={job_id} path={dest} bytes={written}", flush=True)

    jobs_volume.reload()  # type: ignore[attr-defined]
    from duration_guard import max_duration_violation

    duration_err = max_duration_violation(dest)
    if duration_err:
        set_failed(job_id, duration_err)
        print(
            f"JOB_REJECT_DURATION job_id={job_id} path={dest} error={duration_err}",
            flush=True,
        )
        raise HTTPException(status_code=400, detail=duration_err)

    return dest


class UploadUrlBody(BaseModel):
    job_id: str
    filename: str
    content_type: str | None = None
    size: int = Field(gt=0)


def _ingest_r2_upload(
    job_id: str,
    *,
    jobs_volume: Any,
    object_key: str | None = None,
) -> Path:
    """Copy presigned R2 upload into the job Volume and enforce duration."""
    from storage import (
        StorageError,
        download_upload_object,
        upload_object_exists,
    )

    job = get_job(job_id)
    key = object_key or (job.get("r2_upload_key") if job else None)
    if not key or not isinstance(key, str):
        raise HTTPException(status_code=400, detail="No R2 upload registered for job")

    if not upload_object_exists(key):
        raise HTTPException(status_code=400, detail="R2 upload not found — upload again")

    try:
        data, content_type = download_upload_object(key, max_bytes=MAX_UPLOAD_BYTES)
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = key.rsplit("/", 1)[-1]
    chunks = [data]
    return _persist_upload(
        job_id,
        filename,
        content_type,
        chunks,
        jobs_volume=jobs_volume,
    )


def create_api(
    *,
    spawn_pipeline: Any,
    jobs_volume: Any | None = None,
    spawn_warm: Any | None = None,
) -> FastAPI:
    """Build FastAPI app; spawn_pipeline(job_id) starts background work.

    When ``jobs_volume`` is set (Modal), uploads are persisted under
    ``/jobs/{job_id}/input.*`` before the pipeline is spawned.

    When ``spawn_warm`` is set, ``POST /warm`` queues GPU model warm-up (Phase 7).
    """
    api = FastAPI(title="Automatic Karaoke API", docs_url="/docs")

    api.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.get("/config")
    async def api_config() -> dict[str, bool]:
        from storage import r2_configured

        return {
            "r2_upload": r2_configured(),
            "api_key_required": api_key_configured(),
        }

    @api.post("/start-job")
    async def start_job(
        request: Request,
        audio: UploadFile | None = File(None),
        job_id: str | None = Query(None, alias="job_id"),
    ) -> dict[str, str]:
        """One-shot job start: multipart upload or spawn after R2/Volume ingest."""
        verify_api_key(request)
        check_rate_limit(request)
        if jobs_volume is None:
            raise HTTPException(
                status_code=503,
                detail="Job storage not configured on this server",
            )

        if audio is not None:
            job_id = str(uuid.uuid4())
            create_job(job_id)
            try:
                filename, content_type, chunks, _total = await _read_upload(audio)
                _persist_upload(
                    job_id,
                    filename,
                    content_type,
                    chunks,
                    jobs_volume=jobs_volume,
                )
            except HTTPException as exc:
                if exc.status_code != 400:
                    set_failed(job_id, "Upload rejected")
                raise
            except Exception as exc:
                set_failed(job_id, f"Upload save failed: {exc}")
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            spawn_pipeline(job_id)
            return {"job_id": job_id}

        if not job_id:
            raise HTTPException(
                status_code=400,
                detail="Provide multipart audio or job_id after upload is on Volume",
            )

        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")

        from job_storage import find_job_input

        jobs_volume.reload()  # type: ignore[attr-defined]
        if find_job_input(job_id) is None:
            try:
                _ingest_r2_upload(job_id, jobs_volume=jobs_volume)
            except HTTPException:
                set_failed(job_id, "Upload missing — select the file again")
                raise

        spawn_pipeline(job_id)
        return {"job_id": job_id}

    @api.post("/draft-job")
    async def draft_job(request: Request) -> dict[str, str]:
        """Create a draft job (upload via R2 presigned URL or ``/draft-job/{id}/upload``)."""
        verify_api_key(request)
        if jobs_volume is None:
            raise HTTPException(
                status_code=503,
                detail="Job storage not configured on this server",
            )
        job_id = str(uuid.uuid4())
        create_job(job_id, is_draft=True)
        return {"job_id": job_id}

    @api.post("/upload-url")
    async def upload_url(request: Request, body: UploadUrlBody) -> dict[str, Any]:
        """Presigned PUT URL for direct browser → R2 upload (Phase 7 Step 6)."""
        verify_api_key(request)
        from storage import StorageError, presigned_put_upload, r2_configured

        if not r2_configured():
            raise HTTPException(
                status_code=503,
                detail="Presigned R2 upload is not configured on this server",
            )
        if jobs_volume is None:
            raise HTTPException(status_code=503, detail="Job storage not configured")

        job = get_job(body.job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job.get("is_draft"):
            raise HTTPException(status_code=409, detail="Job is not a draft")

        _validate_upload(body.filename, body.content_type, body.size)
        content_type = body.content_type or "application/octet-stream"

        try:
            payload = presigned_put_upload(
                body.job_id,
                filename=body.filename,
                content_type=content_type,
                size=body.size,
                max_bytes=MAX_UPLOAD_BYTES,
            )
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        update_job(
            body.job_id,
            r2_upload_key=payload["object_key"],
            upload_content_type=content_type,
            upload_filename=body.filename,
            message="Upload to the presigned URL, then sync",
        )
        return payload

    @api.post("/draft-job/{job_id}/sync-upload")
    async def draft_sync_upload(request: Request, job_id: str) -> dict[str, str]:
        """Copy presigned R2 object onto the job Volume (duration check)."""
        verify_api_key(request)
        if jobs_volume is None:
            raise HTTPException(status_code=503, detail="Job storage not configured")

        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job.get("is_draft"):
            raise HTTPException(status_code=409, detail="Job is not a draft")

        try:
            _ingest_r2_upload(job_id, jobs_volume=jobs_volume)
            update_job(
                job_id,
                message="Upload complete — ready to process",
            )
        except HTTPException as exc:
            if exc.status_code != 400:
                set_failed(job_id, "Upload sync failed")
            raise

        return {"job_id": job_id, "status": "uploaded"}

    @api.post("/draft-job/{job_id}/upload")
    async def draft_job_upload(
        request: Request,
        job_id: str,
        audio: UploadFile = File(...),
    ) -> dict[str, str]:
        """Persist audio for a draft job via Modal multipart (legacy fallback)."""
        verify_api_key(request)
        if jobs_volume is None:
            raise HTTPException(status_code=503, detail="Job storage not configured")

        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job.get("is_draft"):
            raise HTTPException(status_code=409, detail="Job is not a draft")

        try:
            filename, content_type, chunks, _total = await _read_upload(audio)
            _persist_upload(
                job_id,
                filename,
                content_type,
                chunks,
                jobs_volume=jobs_volume,
            )
            update_job(
                job_id,
                message="Upload complete — ready to process",
            )
        except HTTPException as exc:
            if exc.status_code != 400:
                set_failed(job_id, "Upload rejected")
            raise
        except Exception as exc:
            set_failed(job_id, f"Upload save failed: {exc}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {"job_id": job_id, "status": "uploaded"}

    @api.delete("/draft-job/{job_id}")
    async def draft_job_delete(request: Request, job_id: str) -> dict[str, str]:
        """Discard a draft job and its Volume / R2 upload artifacts."""
        verify_api_key(request)
        if jobs_volume is None:
            raise HTTPException(status_code=503, detail="Job storage not configured")

        from job_storage import delete_job_workspace
        from storage import StorageError, delete_job_upload, r2_configured

        job = get_job(job_id)
        if job is not None:
            if r2_configured():
                upload_key = job.get("r2_upload_key")
                try:
                    delete_job_upload(
                        job_id,
                        upload_key if isinstance(upload_key, str) else None,
                    )
                except StorageError as exc:
                    print(f"note: draft R2 delete ({job_id}): {exc}", flush=True)
            delete_job(job_id)
        delete_job_workspace(job_id, jobs_volume)
        print(f"DRAFT_DELETE job_id={job_id}", flush=True)
        return {"job_id": job_id, "status": "deleted"}

    @api.post("/finalize-job")
    async def finalize_job(
        request: Request,
        job_id: str = Query(..., alias="job_id"),
    ) -> dict[str, str]:
        """Spawn pipeline for a draft job after upload is on Volume."""
        verify_api_key(request)
        check_rate_limit(request)
        if jobs_volume is None:
            raise HTTPException(status_code=503, detail="Job storage not configured")

        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.get("status") == "failed":
            raise HTTPException(
                status_code=400,
                detail=job.get("error") or "Job failed",
            )

        from job_storage import find_job_input

        jobs_volume.reload()  # type: ignore[attr-defined]
        input_path = find_job_input(job_id)
        if input_path is None:
            try:
                _ingest_r2_upload(job_id, jobs_volume=jobs_volume)
                input_path = find_job_input(job_id)
            except HTTPException:
                set_failed(job_id, "Upload missing — select the file again")
                raise
        if input_path is None:
            set_failed(job_id, "Upload missing — select the file again")
            raise HTTPException(status_code=400, detail="Upload not found for job")

        from duration_guard import max_duration_violation

        duration_err = max_duration_violation(input_path)
        if duration_err:
            set_failed(job_id, duration_err)
            raise HTTPException(status_code=400, detail=duration_err)

        update_job(
            job_id,
            status="queued",
            progress=0,
            message="Queued…",
            is_draft=False,
        )
        spawn_pipeline(job_id)
        print(f"JOB_FINALIZE job_id={job_id}", flush=True)
        return {"job_id": job_id}

    @api.get("/job-status")
    async def job_status(job_id: str = Query(..., alias="job_id")) -> dict[str, Any]:
        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(job)

    @api.post("/warm", status_code=202)
    async def warm_pipeline() -> dict[str, str]:
        """Intent-based GPU warm-up (file selected in UI). Idempotent; returns immediately."""
        if spawn_warm is None:
            raise HTTPException(
                status_code=503,
                detail="GPU warm-up not configured on this server",
            )
        spawn_warm()
        return {"status": "accepted"}

    return api
