"""FastAPI HTTP API (Phase 2 Step 3)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from jobs import create_job, get_job

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
) -> FastAPI:
    """Build FastAPI app; spawn_pipeline(job_id) starts background work."""
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
        body = await audio.read()
        _validate_upload(audio.filename or "upload", audio.content_type, len(body))

        job_id = str(uuid.uuid4())
        create_job(job_id)
        spawn_pipeline(job_id)

        return {"job_id": job_id}

    @api.get("/job-status")
    async def job_status(job_id: str = Query(..., alias="job_id")) -> dict[str, Any]:
        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(job)

    return api
