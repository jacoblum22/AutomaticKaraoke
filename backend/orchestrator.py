"""Job pipeline orchestration — stub (Phase 2) and real pipeline (Phase 6)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from job_storage import job_dir
from jobs import JobStatus, set_failed, update_job
from pipeline_stems import expected_stem_paths

STUB_VIDEO_URL = "https://automatic-karaoke.vercel.app/sample.mp4"

STUB_STAGE_SLEEP_S = 2
SKELETON_STAGE_SLEEP_S = 1.0

DEFAULT_TRANSCRIBE_MODEL = "large-v3"

# After create_job (queued), advance through these stages.
PIPELINE_STAGES: list[tuple[JobStatus, int, str]] = [
    ("separating", 20, "Separating vocals…"),
    ("transcribing", 40, "Transcribing vocals…"),
    ("aligning", 60, "Aligning lyrics…"),
    ("rendering", 80, "Rendering karaoke video…"),
]

POST_SEPARATION_STAGES = PIPELINE_STAGES[1:]
POST_TRANSCRIPTION_SKELETON_STAGES = PIPELINE_STAGES[3:]

SIMULATED_FAIL_MESSAGE = "pipeline simulated failure"


def _advance_stages(
    job_id: str,
    stages: list[tuple[JobStatus, int, str]],
    *,
    sleep_s: float,
    simulate_fail: bool,
    fail_at: JobStatus = "transcribing",
) -> None:
    for status, progress, message in stages:
        if simulate_fail and status == fail_at:
            raise RuntimeError(SIMULATED_FAIL_MESSAGE)
        update_job(job_id, status=status, progress=progress, message=message)
        time.sleep(sleep_s)


def run_stub_pipeline(job_id: str, *, simulate_fail: bool = False) -> None:
    """Advance job through stub stages. Caller must create_job first."""
    try:
        _advance_stages(
            job_id,
            PIPELINE_STAGES,
            sleep_s=STUB_STAGE_SLEEP_S,
            simulate_fail=simulate_fail,
        )
        update_job(
            job_id,
            status="done",
            progress=100,
            message="Complete!",
            video_url=STUB_VIDEO_URL,
        )
    except Exception as exc:
        set_failed(job_id, str(exc))


def _require_job_input(
    job_id: str,
    *,
    volume: object | None = None,
    attempts: int = 20,
    delay_s: float = 0.5,
) -> Path:
    """Wait for upload to appear on the shared Volume (spawn can race commit)."""
    from job_storage import find_job_input

    for _ in range(attempts):
        if volume is not None:
            volume.reload()  # type: ignore[attr-defined]
        path = find_job_input(job_id)
        if path is not None:
            return path
        time.sleep(delay_s)
    raise FileNotFoundError(f"No upload for job_id={job_id}")


def _run_separation(
    job_id: str,
    input_path: Path,
    *,
    separate_stems_fn: Callable[..., tuple[str, str]],
    volume: object | None,
) -> dict[str, float | int]:
    workdir = job_dir(job_id)
    update_job(job_id, status="separating", progress=20, message="Separating vocals…")

    separate_stems_fn.remote(str(input_path), str(workdir), device="cuda")

    if volume is not None:
        volume.reload()  # type: ignore[attr-defined]

    from pipeline_stems import verify_stem_outputs

    return verify_stem_outputs(workdir)


def _run_transcription(
    job_id: str,
    workdir: Path,
    *,
    transcribe_vocals_fn: Callable[..., str],
    volume: object | None,
    simulate_fail: bool,
    fail_at: JobStatus,
    model_size: str = DEFAULT_TRANSCRIBE_MODEL,
    clip_end: float | None = None,
) -> dict[str, int | str | float]:
    vocals_path, _ = expected_stem_paths(workdir)
    if not vocals_path.is_file():
        raise FileNotFoundError(f"vocals stem missing: {vocals_path}")

    update_job(job_id, status="transcribing", progress=40, message="Transcribing vocals…")
    if simulate_fail and fail_at == "transcribing":
        raise RuntimeError(SIMULATED_FAIL_MESSAGE)

    from pipeline_lyrics import lyrics_json_path, verify_lyrics_json

    lyrics_path = lyrics_json_path(workdir)
    update_job(job_id, status="aligning", progress=60, message="Aligning lyrics…")

    transcribe_vocals_fn.remote(
        str(vocals_path),
        str(lyrics_path),
        clip_end=clip_end,
        model_size=model_size,
    )

    if volume is not None:
        volume.reload()  # type: ignore[attr-defined]

    return verify_lyrics_json(lyrics_path)


def _run_render(
    job_id: str,
    workdir: Path,
    *,
    render_karaoke_fn: Callable[..., str],
    volume: object | None,
    simulate_fail: bool,
    fail_at: JobStatus,
    clip_end: float | None = None,
) -> dict[str, int | str]:
    _, instrumental_path = expected_stem_paths(workdir)
    if not instrumental_path.is_file():
        raise FileNotFoundError(f"instrumental stem missing: {instrumental_path}")

    from pipeline_lyrics import lyrics_json_path
    from pipeline_render import karaoke_mp4_path, verify_karaoke_mp4

    lyrics_path = lyrics_json_path(workdir)
    if not lyrics_path.is_file():
        raise FileNotFoundError(f"lyrics.json missing: {lyrics_path}")

    output_mp4 = karaoke_mp4_path(workdir)
    update_job(job_id, status="rendering", progress=80, message="Rendering karaoke video…")
    if simulate_fail and fail_at == "rendering":
        raise RuntimeError(SIMULATED_FAIL_MESSAGE)

    render_karaoke_fn.remote(
        str(instrumental_path),
        str(lyrics_path),
        str(output_mp4),
        clip_end=clip_end,
    )

    if volume is not None:
        volume.reload()  # type: ignore[attr-defined]

    return verify_karaoke_mp4(output_mp4)


def _run_upload(
    job_id: str,
    workdir: Path,
    upload_karaoke_fn: Callable[[str, str], str],
) -> str:
    from pipeline_render import karaoke_mp4_path, verify_karaoke_mp4

    mp4_path = karaoke_mp4_path(workdir)
    verify_karaoke_mp4(mp4_path)
    video_url = upload_karaoke_fn(str(mp4_path), job_id)
    update_job(
        job_id,
        status="done",
        progress=100,
        message="Complete!",
        video_url=video_url,
    )
    return video_url


def run_real_pipeline(
    job_id: str,
    *,
    simulate_fail: bool = False,
    fail_at: JobStatus = "transcribing",
    volume: object | None = None,
    separate_stems_fn: Any | None = None,
    transcribe_vocals_fn: Any | None = None,
    render_karaoke_fn: Any | None = None,
    upload_karaoke_fn: Callable[[str, str], str] | None = None,
    model_size: str = DEFAULT_TRANSCRIBE_MODEL,
    clip_end: float | None = None,
) -> None:
    """Real pipeline: Demucs → transcribe+align → render (wired incrementally)."""
    try:
        input_path = _require_job_input(job_id, volume=volume)
        workdir = job_dir(job_id)

        if separate_stems_fn is not None:
            _run_separation(
                job_id,
                input_path,
                separate_stems_fn=separate_stems_fn,
                volume=volume,
            )
            if volume is not None:
                volume.commit()  # type: ignore[attr-defined]
        else:
            update_job(
                job_id,
                status="separating",
                progress=20,
                message="Separating vocals…",
            )
            time.sleep(SKELETON_STAGE_SLEEP_S)

        if transcribe_vocals_fn is not None:
            _run_transcription(
                job_id,
                workdir,
                transcribe_vocals_fn=transcribe_vocals_fn,
                volume=volume,
                simulate_fail=simulate_fail,
                fail_at=fail_at,
                model_size=model_size,
                clip_end=clip_end,
            )
            if volume is not None:
                volume.commit()  # type: ignore[attr-defined]
        else:
            _advance_stages(
                job_id,
                POST_SEPARATION_STAGES,
                sleep_s=SKELETON_STAGE_SLEEP_S,
                simulate_fail=simulate_fail,
                fail_at=fail_at,
            )

        if render_karaoke_fn is not None:
            _run_render(
                job_id,
                workdir,
                render_karaoke_fn=render_karaoke_fn,
                volume=volume,
                simulate_fail=simulate_fail,
                fail_at=fail_at,
                clip_end=clip_end,
            )
            if volume is not None:
                volume.commit()  # type: ignore[attr-defined]
        else:
            _advance_stages(
                job_id,
                POST_TRANSCRIPTION_SKELETON_STAGES,
                sleep_s=SKELETON_STAGE_SLEEP_S,
                simulate_fail=False,
            )

        if upload_karaoke_fn is not None:
            if render_karaoke_fn is None:
                raise RuntimeError("upload requires render_karaoke_fn")
            _run_upload(job_id, workdir, upload_karaoke_fn)
    except Exception as exc:
        set_failed(job_id, str(exc))
