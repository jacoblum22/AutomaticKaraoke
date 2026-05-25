"""FastAPI HTTP API (Phase 2 Step 3)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from jobs import create_job, get_job, set_failed

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

    @api.post("/start-job")
    async def start_job(audio: UploadFile = File(...)) -> dict[str, str]:
        # Validate type from headers; size from Content-Length when present.
        declared = audio.size or 0
        filename = audio.filename or "upload"
        _validate_upload(filename, audio.content_type, declared)

        if jobs_volume is None:
            raise HTTPException(
                status_code=503,
                detail="Job storage not configured on this server",
            )

        job_id = str(uuid.uuid4())
        create_job(job_id)

        # Phase 6: persist upload before pipeline reads it (stay queued until spawn).
        chunks: list[bytes] = []
        total = 0
        try:
            while True:
                chunk = await audio.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
                        ),
                    )
                chunks.append(chunk)

            if declared == 0 and total > 0:
                _validate_upload(filename, audio.content_type, total)

            from job_storage import write_job_input_stream

            dest, written = write_job_input_stream(
                job_id,
                filename,
                audio.content_type,
                chunks,
                volume=jobs_volume,
            )
            print(
                f"JOB_INPUT job_id={job_id} path={dest} bytes={written}",
                flush=True,
            )
        except HTTPException:
            set_failed(job_id, "Upload rejected")
            raise
        except Exception as exc:
            set_failed(job_id, f"Upload save failed: {exc}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        spawn_pipeline(job_id)
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
