"""Modal app entrypoint. Phase 2: web endpoints; Phase 6: orchestration."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import modal

from job_storage import JOBS_MOUNT, jobs_volume
from jobs import create_job, delete_job, get_job, set_failed, update_job
from orchestrator import (
    SIMULATED_FAIL_MESSAGE,
    STUB_VIDEO_URL,
    run_real_pipeline as _run_real_pipeline,
    run_stub_pipeline as _run_stub_pipeline,
)

app = modal.App("karaoke")

JOBS_VOL = jobs_volume()

R2_SECRET = modal.Secret.from_name("karaoke-r2")
API_KEY_SECRET = modal.Secret.from_name("karaoke-api-key")

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_FIXTURE_MP3 = _REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3"
_PSYCHO_MP3 = _REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3"
_VOCAL_SMOKE_WAV = _REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav"
_PSYCHO_INSTRUMENTAL = _REPO_ROOT / "scripts" / "output" / "psychosomatic" / "instrumental.wav"
_PSYCHO_LYRICS = _REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json"
_PSYCHO_KARAOKE = _REPO_ROOT / "scripts" / "output" / "psychosomatic" / "karaoke.mp4"

_backend_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install_from_requirements(_BACKEND_DIR / "requirements.txt")
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
)
if _FIXTURE_MP3.is_file():
    _backend_image = _backend_image.add_local_file(
        _FIXTURE_MP3, remote_path="/fixtures/sample_30s.mp3"
    )
if _PSYCHO_MP3.is_file():
    _backend_image = _backend_image.add_local_file(
        _PSYCHO_MP3, remote_path="/fixtures/Psychosomatic.mp3"
    )
if _VOCAL_SMOKE_WAV.is_file():
    _backend_image = _backend_image.add_local_file(
        _VOCAL_SMOKE_WAV, remote_path="/fixtures/vocals_smoke.wav"
    )
if _PSYCHO_INSTRUMENTAL.is_file():
    _backend_image = _backend_image.add_local_file(
        _PSYCHO_INSTRUMENTAL, remote_path="/fixtures/instrumental_smoke.wav"
    )
if _PSYCHO_LYRICS.is_file():
    _backend_image = _backend_image.add_local_file(
        _PSYCHO_LYRICS, remote_path="/fixtures/lyrics_smoke.json"
    )
if _PSYCHO_KARAOKE.is_file():
    _backend_image = _backend_image.add_local_file(
        _PSYCHO_KARAOKE, remote_path="/fixtures/karaoke_smoke.mp4"
    )
_BACKEND_IMAGE = _backend_image

# Phase 3 — Demucs only (keep web/API image lean)
_demucs_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install_from_requirements(_BACKEND_DIR / "requirements-demucs.txt")
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
    .add_local_file(_FIXTURE_MP3, remote_path="/fixtures/sample_30s.mp3")
)
if _PSYCHO_MP3.is_file():
    _demucs_image = _demucs_image.add_local_file(
        _PSYCHO_MP3, remote_path="/fixtures/Psychosomatic.mp3"
    )
_DEMUCS_IMAGE = _demucs_image

# Phase 4 — faster-whisper + WhisperX (separate from API + Demucs images)
_whisper_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install_from_requirements(_BACKEND_DIR / "requirements-whisper.txt")
    .run_commands(
        'python -c "import nltk; nltk.download(\'punkt_tab\', quiet=True); '
        "nltk.download('punkt', quiet=True)\""
    )
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
)
if _VOCAL_SMOKE_WAV.is_file():
    _whisper_image = _whisper_image.add_local_file(
        _VOCAL_SMOKE_WAV, remote_path="/fixtures/vocals_smoke.wav"
    )
_WHISPER_IMAGE = _whisper_image

# Phase 5 — FFmpeg render (CPU only; no torch / whisper)
_render_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install_from_requirements(_BACKEND_DIR / "requirements-render.txt")
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
)
if _PSYCHO_INSTRUMENTAL.is_file() and _PSYCHO_LYRICS.is_file():
    _render_image = _render_image.add_local_file(
        _PSYCHO_INSTRUMENTAL, remote_path="/fixtures/instrumental_smoke.wav"
    ).add_local_file(_PSYCHO_LYRICS, remote_path="/fixtures/lyrics_smoke.json")
_RENDER_IMAGE = _render_image

TERMINAL = frozenset({"done", "failed"})
POLL_INTERVAL_S = 1
POLL_TIMEOUT_S = 45


def _poll_job(
    job_id: str,
    *,
    expect_failed: bool = False,
    timeout_s: float = POLL_TIMEOUT_S,
) -> dict:
    deadline = time.time() + timeout_s
    last_status: str | None = None
    while time.time() < deadline:
        job = get_job(job_id)
        if job is None:
            raise RuntimeError(f"job not found in Dict: {job_id}")
        status = job["status"]
        if status != last_status:
            print(
                f"{status} {job.get('progress', 0)} {job.get('message', '')}".strip(),
                flush=True,
            )
            last_status = status
        if status in TERMINAL:
            if expect_failed:
                if status != "failed":
                    raise RuntimeError(f"expected failed, got {status}")
                if not job.get("error"):
                    raise RuntimeError("failed without error")
            else:
                if status != "done":
                    raise RuntimeError(f"expected done, got {status}: {job.get('error')}")
                if job.get("video_url") != STUB_VIDEO_URL:
                    raise RuntimeError(f"unexpected video_url: {job.get('video_url')}")
            return dict(job)
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"job {job_id} did not finish within {timeout_s}s")


@app.function(image=_BACKEND_IMAGE)
def run_stub_pipeline(job_id: str, simulate_fail: bool = False) -> None:
    """Background stub pipeline (Phase 2 regression smokes)."""
    _run_stub_pipeline(job_id, simulate_fail=simulate_fail)


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL}, secrets=[R2_SECRET])
def run_real_pipeline(
    job_id: str,
    simulate_fail: bool = False,
    fail_at: str = "transcribing",
) -> None:
    """Phase 6 pipeline (spawned from start-job)."""
    from storage import upload_karaoke_mp4

    _run_real_pipeline(
        job_id,
        simulate_fail=simulate_fail,
        fail_at=fail_at,  # type: ignore[arg-type]
        volume=JOBS_VOL,
        separate_stems_fn=separate_stems,
        transcribe_vocals_fn=transcribe_vocals_modal,
        render_karaoke_fn=render_karaoke_modal,
        upload_karaoke_fn=upload_karaoke_mp4,
    )


SKELETON_TERMINAL = frozenset({"rendering", "failed"})


def _poll_job_skeleton(
    job_id: str,
    *,
    expect_failed: bool = False,
    timeout_s: float = 900,
) -> dict:
    """Poll until skeleton pipeline stops at rendering or failed."""
    deadline = time.time() + timeout_s
    last_status: str | None = None
    while time.time() < deadline:
        job = get_job(job_id)
        if job is None:
            raise RuntimeError(f"job not found in Dict: {job_id}")
        status = job["status"]
        if status != last_status:
            print(
                f"{status} {job.get('progress', 0)} {job.get('message', '')}".strip(),
                flush=True,
            )
            last_status = status
        if status in SKELETON_TERMINAL:
            if expect_failed:
                if status != "failed":
                    raise RuntimeError(f"expected failed, got {status}")
                if not job.get("error"):
                    raise RuntimeError("failed without error")
                if SIMULATED_FAIL_MESSAGE not in str(job.get("error", "")):
                    raise RuntimeError(f"unexpected error: {job.get('error')}")
            else:
                if status != "rendering":
                    raise RuntimeError(f"expected rendering, got {status}: {job.get('error')}")
                if job.get("progress") != 80:
                    raise RuntimeError(f"expected progress 80, got {job.get('progress')}")
                if job.get("video_url"):
                    raise RuntimeError("skeleton must not set video_url")
            return dict(job)
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"job {job_id} did not reach skeleton terminal within {timeout_s}s")


# --- Phase 2 Step 3 — HTTP API ---


@app.function(
    image=_BACKEND_IMAGE,
    volumes={JOBS_MOUNT: JOBS_VOL},
    secrets=[R2_SECRET, API_KEY_SECRET],
)
@modal.asgi_app(label="karaoke-api")
def karaoke_api():
    from web import create_api

    return create_api(
        spawn_pipeline=lambda job_id: run_real_pipeline.spawn(job_id),
        spawn_warm=lambda: warm_gpu_pipeline.spawn(),
        jobs_volume=JOBS_VOL,
    )


# --- Phase 6 Step 1 — job upload on Volume ---


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def verify_job_mp4(job_id: str, *, min_bytes: int = 1024) -> dict:
    """Confirm ``karaoke.mp4`` on Volume (Phase 6 Step 5 smoke)."""
    from job_storage import job_dir
    from pipeline_render import karaoke_mp4_path, verify_karaoke_mp4

    JOBS_VOL.reload()
    return verify_karaoke_mp4(karaoke_mp4_path(job_dir(job_id)), min_bytes=min_bytes)


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def verify_job_lyrics(job_id: str) -> dict:
    """Confirm ``lyrics.json`` on Volume (Phase 6 Step 4 smoke)."""
    from job_storage import job_dir
    from pipeline_lyrics import verify_lyrics_json

    JOBS_VOL.reload()
    return verify_lyrics_json(job_dir(job_id) / "lyrics.json")


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def verify_job_stems(
    job_id: str,
    *,
    min_duration_s: float = 20.0,
    max_duration_s: float = 35.0,
) -> dict:
    """Confirm Demucs stems on Volume (Phase 6 Step 3 smoke)."""
    from job_storage import job_dir
    from pipeline_stems import verify_stem_outputs

    JOBS_VOL.reload()
    info = verify_stem_outputs(job_dir(job_id))
    vocals_dur = float(info["vocals_duration_s"])
    if vocals_dur < min_duration_s or vocals_dur > max_duration_s:
        raise ValueError(
            f"vocals duration {vocals_dur:.2f}s outside "
            f"[{min_duration_s}, {max_duration_s}]"
        )
    return info


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def verify_job_input(job_id: str, *, expected_bytes: int | None = None) -> dict:
    """Confirm ``/jobs/{job_id}/input.*`` exists (Phase 6 Step 1 smoke)."""
    from job_storage import find_job_input

    JOBS_VOL.reload()

    path = find_job_input(job_id)
    if path is None:
        raise FileNotFoundError(f"no input file for job {job_id} under {JOBS_MOUNT}")

    size = path.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise RuntimeError(f"size mismatch: {size} != expected {expected_bytes}")

    return {
        "job_id": job_id,
        "input_path": str(path),
        "size_bytes": size,
    }


# --- Phase 2 Step 1 smoke ---


@app.function(image=_BACKEND_IMAGE)
def smoke_jobs_write() -> str:
    """Phase 2 Step 1 — create/update job in Dict; return job_id."""
    job_id = str(uuid.uuid4())
    create_job(job_id)
    update_job(
        job_id,
        status="separating",
        progress=20,
        message="Separating vocals…",
    )
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == "separating"
    assert job["progress"] == 20
    print(f"JOB_ID={job_id}", flush=True)
    return job_id


@app.function(image=_BACKEND_IMAGE)
def smoke_jobs_read(job_id: str) -> dict:
    """Phase 2 Step 1 — read job in a fresh container (Dict persistence)."""
    job = get_job(job_id)
    if job is None:
        raise RuntimeError(f"job not found in Dict: {job_id}")
    if job.get("status") != "separating":
        raise RuntimeError(f"unexpected status: {job.get('status')}")
    return dict(job)


@app.function(image=_BACKEND_IMAGE)
def smoke_jobs_failed() -> str:
    """Phase 2 Step 1 — set_failed + delete_job."""
    job_id = str(uuid.uuid4())
    create_job(job_id)
    set_failed(job_id, "smoke test failure")
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == "failed"
    assert job.get("error") == "smoke test failure"
    delete_job(job_id)
    assert get_job(job_id) is None
    return job_id


# --- Phase 2 Step 2 smoke ---


@app.function(image=_BACKEND_IMAGE)
def smoke_orchestrator_happy() -> str:
    """Spawn stub pipeline and poll until done."""
    job_id = str(uuid.uuid4())
    create_job(job_id)
    run_stub_pipeline.spawn(job_id)
    _poll_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return job_id


# --- Phase 7 Step 2 — intent-based GPU warm-up ---

GPU_SCALEDOWN_WINDOW = 120  # seconds idle before scale-to-zero


@app.function(image=_BACKEND_IMAGE, timeout=120)
def warm_gpu_pipeline() -> dict[str, str | list[str]]:
    """Spawn Demucs + Whisper on bundled fixtures to warm production GPU containers."""
    work_id = uuid.uuid4().hex[:8]
    spawned: list[str] = []

    demucs_fixture = Path("/fixtures/sample_30s.mp3")
    if demucs_fixture.is_file():
        separate_stems.spawn(
            str(demucs_fixture),
            f"/tmp/warm_demucs_{work_id}",
            device="cuda",
        )
        spawned.append("demucs")
    else:
        print("WARM_SKIP demucs fixture missing", flush=True)

    vocals_fixture = Path("/fixtures/vocals_smoke.wav")
    if vocals_fixture.is_file():
        transcribe_vocals_modal.spawn(
            str(vocals_fixture),
            f"/tmp/warm_whisper_{work_id}.json",
            clip_end=1.0,
            model_size="large-v3",
        )
        spawned.append("whisper")
    else:
        print("WARM_SKIP whisper fixture missing", flush=True)

    print(f"WARM_SPAWNED work_id={work_id} targets={spawned}", flush=True)
    return {"status": "accepted", "spawned": spawned}


# --- Phase 3 — Demucs GPU ---


@app.function(
    image=_DEMUCS_IMAGE,
    gpu="T4",
    timeout=1200,
    scaledown_window=GPU_SCALEDOWN_WINDOW,
    volumes={JOBS_MOUNT: JOBS_VOL},
)
def separate_stems(
    input_path: str,
    output_dir: str,
    *,
    device: str = "cuda",
) -> tuple[str, str]:
    """Run Demucs on GPU; returns (vocals_path, instrumental_path)."""
    from separate import separate_audio

    JOBS_VOL.reload()
    vocals_path, instrumental_path = separate_audio(
        input_path,
        output_dir,
        device=device,
        progress=True,
    )
    JOBS_VOL.commit()
    return str(vocals_path), str(instrumental_path)


@app.function(image=_DEMUCS_IMAGE, gpu="T4", timeout=600)
def smoke_demucs_separate() -> dict:
    """Phase 3 Step 5 — GPU separation on bundled 30s fixture."""
    import time
    from pathlib import Path

    from separate import separate_audio

    input_path = Path("/fixtures/sample_30s.mp3")
    if not input_path.is_file():
        raise FileNotFoundError(f"fixture missing in image: {input_path}")

    output_dir = Path("/tmp/smoke_demucs_out")
    t0 = time.perf_counter()
    vocals_path, instrumental_path = separate_audio(
        input_path,
        output_dir,
        device="cuda",
        progress=True,
    )
    elapsed = time.perf_counter() - t0

    for label, path in ("vocals", vocals_path), ("instrumental", instrumental_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"{label} output missing or empty: {path}")

    print(f"VOCALS_PATH={vocals_path}", flush=True)
    print(f"INSTRUMENTAL_PATH={instrumental_path}", flush=True)
    print(f"ELAPSED_S={elapsed:.1f}", flush=True)
    return {
        "vocals": str(vocals_path),
        "instrumental": str(instrumental_path),
        "elapsed_s": elapsed,
    }


@app.function(image=_DEMUCS_IMAGE, gpu="T4", timeout=1200)
def smoke_demucs_psychosomatic() -> dict:
    """Phase 3 Step 7 — GPU separation on ~3 min song (if fixture baked into image)."""
    import time
    from pathlib import Path

    from separate import separate_audio

    input_path = Path("/fixtures/Psychosomatic.mp3")
    if not input_path.is_file():
        raise FileNotFoundError(
            "Psychosomatic.mp3 not in image — copy to scripts/fixtures/ and redeploy"
        )

    output_dir = Path("/tmp/smoke_demucs_psychosomatic")
    t0 = time.perf_counter()
    vocals_path, instrumental_path = separate_audio(
        input_path,
        output_dir,
        device="cuda",
        progress=True,
    )
    elapsed = time.perf_counter() - t0

    print(f"VOCALS_PATH={vocals_path}", flush=True)
    print(f"INSTRUMENTAL_PATH={instrumental_path}", flush=True)
    print(f"ELAPSED_S={elapsed:.1f}", flush=True)
    return {
        "vocals": str(vocals_path),
        "instrumental": str(instrumental_path),
        "elapsed_s": elapsed,
    }


# --- Phase 4 — Whisper GPU ---


@app.function(
    image=_WHISPER_IMAGE,
    gpu="T4",
    timeout=1200,
    scaledown_window=GPU_SCALEDOWN_WINDOW,
    volumes={JOBS_MOUNT: JOBS_VOL},
)
def transcribe_vocals_modal(
    input_path: str,
    output_json: str,
    *,
    clip_end: float | None = None,
    model_size: str = "large-v3",
    language: str = "en",
) -> str:
    """Transcribe + align on GPU; returns path to lyrics.json."""
    from transcribe import transcribe_and_align

    JOBS_VOL.reload()
    out = transcribe_and_align(
        input_path,
        output_json,
        model_size=model_size,
        device="cuda",
        compute_type="float16",
        language=language,
        clip_end=clip_end,
        vad_filter=False,
    )
    JOBS_VOL.commit()
    return str(out)


@app.function(image=_WHISPER_IMAGE, gpu="T4", timeout=1200)
def smoke_whisper_fixture(
    *,
    clip_end: float | None = 30.0,
    model_size: str = "large-v3",
) -> dict:
    """GPU transcribe+align on bundled vocal stem.

    Default ``clip_end=30`` for smokes; pass ``clip_end=None`` for full song (Step 5).
    """
    import json
    import time
    from pathlib import Path

    from transcribe import log_lyrics_summary, transcribe_and_align

    vocal = Path("/fixtures/vocals_smoke.wav")
    if not vocal.is_file():
        raise FileNotFoundError(
            "vocals_smoke.wav not in image — run Phase 3 on Psychosomatic and redeploy "
            "(expects scripts/output/psychosomatic/vocals.wav at deploy time)"
        )

    output = Path("/tmp/lyrics_smoke.json")
    t0 = time.perf_counter()
    transcribe_and_align(
        vocal,
        output,
        model_size=model_size,
        device="cuda",
        compute_type="float16",
        clip_end=clip_end,
    )
    elapsed = time.perf_counter() - t0

    lyrics = json.loads(output.read_text(encoding="utf-8"))
    log_lyrics_summary(lyrics)

    segments = lyrics.get("segments") or []
    word_count = sum(len(s.get("words") or []) for s in segments)
    if not segments or word_count == 0:
        raise RuntimeError("smoke produced empty lyrics")

    all_words = [w for s in segments for w in s["words"]]
    print(f"LYRICS_PATH={output}", flush=True)
    print(f"ELAPSED_S={elapsed:.1f}", flush=True)

    return {
        "lyrics_path": str(output),
        "elapsed_s": elapsed,
        "language": lyrics.get("language", "en"),
        "segments": len(segments),
        "words": word_count,
        "first_word": all_words[0]["word"],
        "first_start": all_words[0]["start"],
        "last_word": all_words[-1]["word"],
        "last_end": all_words[-1]["end"],
        "lyrics": lyrics,
    }


# --- Phase 5 — FFmpeg render CPU ---


@app.function(
    image=_RENDER_IMAGE,
    timeout=600,
    volumes={JOBS_MOUNT: JOBS_VOL},
)
def render_karaoke_modal(
    instrumental_path: str,
    lyrics_path: str,
    output_mp4: str,
    *,
    clip_end: float | None = None,
) -> str:
    """Render karaoke MP4 on CPU; returns path to output file."""
    from render import render_karaoke

    JOBS_VOL.reload()
    out = render_karaoke(
        instrumental_path,
        lyrics_path,
        output_mp4,
        clip_end=clip_end,
    )
    JOBS_VOL.commit()
    return str(out)


@app.function(image=_RENDER_IMAGE, timeout=1200)
def smoke_render_fixture(*, clip_end: float | None = 30.0) -> dict:
    """CPU render on bundled psychosomatic pair.

    Default ``clip_end=30`` for smokes; pass ``clip_end=None`` for full song.
    """
    import time
    from pathlib import Path

    from render import render_karaoke

    instrumental = Path("/fixtures/instrumental_smoke.wav")
    lyrics = Path("/fixtures/lyrics_smoke.json")
    if not instrumental.is_file() or not lyrics.is_file():
        raise FileNotFoundError(
            "render fixtures missing from image — run Phase 3–4 on Psychosomatic and redeploy "
            "(expects scripts/output/psychosomatic/instrumental.wav + lyrics.json)"
        )

    output = Path("/tmp/karaoke_smoke.mp4")
    t0 = time.perf_counter()
    render_karaoke(instrumental, lyrics, output, clip_end=clip_end)
    elapsed = time.perf_counter() - t0

    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"render produced missing or empty MP4: {output}")

    size_bytes = output.stat().st_size
    print(f"MP4_PATH={output}", flush=True)
    print(f"ELAPSED_S={elapsed:.1f}", flush=True)
    print(f"SIZE_BYTES={size_bytes}", flush=True)

    return {
        "mp4_path": str(output),
        "elapsed_s": elapsed,
        "size_bytes": size_bytes,
        "clip_end": clip_end,
    }


@app.function(image=_BACKEND_IMAGE)
def smoke_orchestrator_fail() -> str:
    """Spawn failing stub pipeline and poll until failed."""
    job_id = str(uuid.uuid4())
    create_job(job_id)
    run_stub_pipeline.spawn(job_id, simulate_fail=True)
    _poll_job(job_id, expect_failed=True)
    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return job_id


# --- Phase 6 Step 2 — skeleton orchestrator ---


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase6_skeleton_happy() -> str:
    """Write fixture upload, run skeleton pipeline, stop at rendering."""
    from job_storage import write_job_input

    fixture = Path("/fixtures/sample_30s.mp3")
    if not fixture.is_file():
        raise FileNotFoundError(f"fixture missing in image: {fixture}")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    write_job_input(
        job_id,
        "sample_30s.mp3",
        "audio/mpeg",
        fixture.read_bytes(),
        volume=JOBS_VOL,
    )
    run_real_pipeline.spawn(job_id)
    _poll_job_skeleton(job_id)
    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return job_id


# --- Phase 7 Step 1 — structured logging ---


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase7_stage_logs() -> dict:
    """Skeleton pipeline with per-stage timing logs (no ML)."""
    from job_storage import delete_job_workspace, write_job_input

    fixture = Path("/fixtures/sample_30s.mp3")
    if not fixture.is_file():
        raise FileNotFoundError(f"fixture missing in image: {fixture}")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    write_job_input(
        job_id,
        "sample_30s.mp3",
        "audio/mpeg",
        fixture.read_bytes(),
        volume=JOBS_VOL,
    )
    _run_real_pipeline(job_id, volume=JOBS_VOL)

    job = get_job(job_id)
    if job is None:
        raise RuntimeError(f"job missing after pipeline: {job_id}")

    if job.get("status") != "rendering":
        raise RuntimeError(
            f"expected rendering, got {job.get('status')}: {job.get('error')}"
        )

    timings = dict(job.get("stage_timings") or {})
    required = ("separating", "transcribing", "rendering")
    missing = [stage for stage in required if stage not in timings]
    if missing:
        raise RuntimeError(f"missing stage_timings for {missing}: {timings}")

    for stage in required:
        elapsed = timings[stage]
        if not isinstance(elapsed, (int, float)) or elapsed <= 0:
            raise RuntimeError(f"invalid elapsed for {stage}: {elapsed!r}")

    delete_job(job_id)
    delete_job_workspace(job_id, JOBS_VOL)

    print(f"JOB_ID={job_id}", flush=True)
    return {"job_id": job_id, "stage_timings": timings}


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase6_demucs_pipeline() -> dict:
    """Phase 6 Step 3 — upload + real Demucs on Volume (no HTTP)."""
    from job_storage import job_dir, write_job_input
    from pipeline_stems import verify_stem_outputs

    fixture = Path("/fixtures/sample_30s.mp3")
    if not fixture.is_file():
        raise FileNotFoundError(f"fixture missing in image: {fixture}")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    write_job_input(
        job_id,
        "sample_30s.mp3",
        "audio/mpeg",
        fixture.read_bytes(),
        volume=JOBS_VOL,
    )
    # Demucs only — no transcribe/render.
    _run_real_pipeline(
        job_id,
        volume=JOBS_VOL,
        separate_stems_fn=separate_stems,
        transcribe_vocals_fn=None,
    )

    JOBS_VOL.reload()
    info = verify_stem_outputs(job_dir(job_id))
    vocals_dur = float(info["vocals_duration_s"])
    if vocals_dur < 20.0 or vocals_dur > 35.0:
        raise ValueError(f"unexpected vocals duration: {vocals_dur:.2f}s")

    job = get_job(job_id)
    if job is None or job.get("status") == "failed":
        raise RuntimeError(f"pipeline failed: {job}")

    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return info


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase6_transcribe_pipeline() -> dict:
    """Phase 6 Step 4 — transcribe/align on Volume (Demucs or seeded vocal stem)."""
    from job_storage import job_dir, write_job_input
    from pipeline_lyrics import verify_lyrics_json
    from pipeline_stems import OUTPUT_VOCALS

    psycho_mp3 = Path("/fixtures/Psychosomatic.mp3")
    vocals_fixture = Path("/fixtures/vocals_smoke.wav")
    sample_mp3 = Path("/fixtures/sample_30s.mp3")
    if not sample_mp3.is_file():
        raise FileNotFoundError("sample_30s.mp3 missing in backend image")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    workdir = job_dir(job_id)
    separate_fn = separate_stems
    clip_end: float | None = 30.0

    if psycho_mp3.is_file():
        write_job_input(
            job_id,
            "Psychosomatic.mp3",
            "audio/mpeg",
            psycho_mp3.read_bytes(),
            volume=JOBS_VOL,
        )
        clip_end = 30.0
    elif vocals_fixture.is_file():
        # sample_30s is a tone — seed real vocals for Whisper (from Phase 3 output).
        write_job_input(
            job_id,
            "sample_30s.mp3",
            "audio/mpeg",
            sample_mp3.read_bytes(),
            volume=JOBS_VOL,
        )
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / OUTPUT_VOCALS).write_bytes(vocals_fixture.read_bytes())
        JOBS_VOL.commit()
        separate_fn = None
        clip_end = 30.0
    else:
        raise FileNotFoundError(
            "Need Psychosomatic.mp3 or vocals_smoke.wav in image — run Phase 3 on "
            "Psychosomatic and redeploy"
        )

    _run_real_pipeline(
        job_id,
        volume=JOBS_VOL,
        separate_stems_fn=separate_fn,
        transcribe_vocals_fn=transcribe_vocals_modal,
        render_karaoke_fn=None,
        clip_end=clip_end,
    )

    JOBS_VOL.reload()
    workdir = job_dir(job_id)
    lyrics_info = verify_lyrics_json(workdir / "lyrics.json")

    job = get_job(job_id)
    if job is None or job.get("status") == "failed":
        raise RuntimeError(f"pipeline failed: {job}")

    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return lyrics_info


def _seed_phase6_stems(
    job_id: str,
    workdir: Path,
    *,
    vocals_fixture: Path,
    instrumental_fixture: Path,
    lyrics_fixture: Path | None = None,
) -> None:
    from job_storage import write_job_input
    from pipeline_lyrics import LYRICS_JSON
    from pipeline_stems import OUTPUT_INSTRUMENTAL, OUTPUT_VOCALS

    sample_mp3 = Path("/fixtures/sample_30s.mp3")
    if not sample_mp3.is_file():
        raise FileNotFoundError("sample_30s.mp3 missing in backend image")

    write_job_input(
        job_id,
        "sample_30s.mp3",
        "audio/mpeg",
        sample_mp3.read_bytes(),
        volume=JOBS_VOL,
    )
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / OUTPUT_VOCALS).write_bytes(vocals_fixture.read_bytes())
    (workdir / OUTPUT_INSTRUMENTAL).write_bytes(instrumental_fixture.read_bytes())
    if lyrics_fixture is not None:
        (workdir / LYRICS_JSON).write_bytes(lyrics_fixture.read_bytes())
    JOBS_VOL.commit()


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase6_render_pipeline() -> dict:
    """Phase 6 Step 5 — transcribe + render on Volume (seeded psychosomatic stems)."""
    from job_storage import job_dir
    from pipeline_render import karaoke_mp4_path, verify_karaoke_mp4

    vocals_fixture = Path("/fixtures/vocals_smoke.wav")
    instrumental_fixture = Path("/fixtures/instrumental_smoke.wav")
    if not vocals_fixture.is_file() or not instrumental_fixture.is_file():
        raise FileNotFoundError(
            "Need vocals_smoke.wav and instrumental_smoke.wav — run Phase 3–4 on "
            "Psychosomatic and redeploy"
        )

    job_id = str(uuid.uuid4())
    create_job(job_id)
    workdir = job_dir(job_id)
    _seed_phase6_stems(
        job_id,
        workdir,
        vocals_fixture=vocals_fixture,
        instrumental_fixture=instrumental_fixture,
    )

    _run_real_pipeline(
        job_id,
        volume=JOBS_VOL,
        separate_stems_fn=None,
        transcribe_vocals_fn=transcribe_vocals_modal,
        render_karaoke_fn=render_karaoke_modal,
        upload_karaoke_fn=None,
        clip_end=30.0,
    )

    JOBS_VOL.reload()
    mp4_info = verify_karaoke_mp4(karaoke_mp4_path(workdir))

    job = get_job(job_id)
    if job is None or job.get("status") == "failed":
        raise RuntimeError(f"pipeline failed: {job}")
    if job.get("status") != "rendering":
        raise RuntimeError(f"expected rendering, got {job.get('status')}")

    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return mp4_info


def _assert_https_video_url(url: str) -> int:
    """Verify URL is HTTPS and returns a video content type or byte range."""
    import urllib.error
    import urllib.request

    if not url.startswith("https://"):
        raise ValueError(f"video_url must be HTTPS: {url}")
    if STUB_VIDEO_URL in url or "sample.mp4" in url:
        raise ValueError(f"video_url must not be stub: {url}")

    # R2 public r2.dev URLs often reject HEAD; a small ranged GET is reliable.
    req = urllib.request.Request(
        url, headers={"Range": "bytes=0-1023"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 206):
                raise ValueError(f"unexpected HTTP {resp.status} for {url}")
            content_type = resp.headers.get("Content-Type", "")
            if content_type and "video" not in content_type and "octet" not in content_type:
                print(f"note: Content-Type={content_type!r}", flush=True)
            size = resp.headers.get("Content-Length", "?")
            return int(size) if str(size).isdigit() else 0
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"video_url not accessible: HTTP {exc.code} for {url}"
        ) from exc


def _smoke_cleanup_job(
    job_id: str,
    *,
    r2: bool = True,
    volume: modal.Volume | None = None,
) -> None:
    """Drop smoke artifacts (R2 object, optional Volume dir, job Dict row)."""
    if r2:
        from storage import StorageError, delete_karaoke_mp4

        try:
            delete_karaoke_mp4(job_id)
            print(f"R2_CLEANED={job_id}", flush=True)
        except StorageError as exc:
            print(f"note: R2 cleanup ({job_id}): {exc}", flush=True)
    if volume is not None:
        from job_storage import delete_job_workspace

        delete_job_workspace(job_id, volume)
        print(f"VOLUME_CLEANED={job_id}", flush=True)
    delete_job(job_id)


@app.function(image=_BACKEND_IMAGE, secrets=[R2_SECRET])
def smoke_phase6_cleanup(job_id: str, volume: bool = False) -> None:
    """Remove R2 + optional Volume workspace for a smoke ``job_id``."""
    vol = JOBS_VOL if volume else None
    _smoke_cleanup_job(job_id, r2=True, volume=vol)


@app.function(image=_BACKEND_IMAGE, secrets=[R2_SECRET])
def smoke_phase6_r2_upload(cleanup: bool = True) -> dict:
    """Phase 6 Step 6 — upload bundled MP4 to R2 and verify HTTPS URL."""
    from storage import karaoke_object_key, upload_karaoke_mp4

    mp4 = Path("/fixtures/karaoke_smoke.mp4")
    if not mp4.is_file():
        raise FileNotFoundError(
            "karaoke_smoke.mp4 missing — run Phase 5 render on Psychosomatic and redeploy"
        )

    job_id = str(uuid.uuid4())
    try:
        video_url = upload_karaoke_mp4(mp4, job_id)
        print(f"JOB_ID={job_id}", flush=True)
        print(f"VIDEO_URL={video_url}", flush=True)
        # Verify from the smoke script on your machine — r2.dev often 403s Modal egress.
        return {
            "job_id": job_id,
            "video_url": video_url,
            "object_key": karaoke_object_key(job_id),
            "size_bytes": mp4.stat().st_size,
        }
    finally:
        if cleanup:
            _smoke_cleanup_job(job_id, r2=True, volume=None)


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL}, secrets=[R2_SECRET])
def smoke_phase6_deliver_pipeline(cleanup: bool = True) -> dict:
    """Phase 6 Step 6 — full pipeline through R2 upload → done + video_url."""
    from job_storage import job_dir
    from storage import upload_karaoke_mp4

    vocals_fixture = Path("/fixtures/vocals_smoke.wav")
    instrumental_fixture = Path("/fixtures/instrumental_smoke.wav")
    if not vocals_fixture.is_file() or not instrumental_fixture.is_file():
        raise FileNotFoundError("stem fixtures missing from image")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    try:
        workdir = job_dir(job_id)
        _seed_phase6_stems(
            job_id,
            workdir,
            vocals_fixture=vocals_fixture,
            instrumental_fixture=instrumental_fixture,
        )

        _run_real_pipeline(
            job_id,
            volume=JOBS_VOL,
            separate_stems_fn=None,
            transcribe_vocals_fn=transcribe_vocals_modal,
            render_karaoke_fn=render_karaoke_modal,
            upload_karaoke_fn=upload_karaoke_mp4,
            clip_end=30.0,
        )

        job = get_job(job_id)
        if job is None or job.get("status") != "done":
            raise RuntimeError(f"expected done, got {job}")
        video_url = job.get("video_url")
        if not video_url:
            raise RuntimeError("done without video_url")

        print(f"JOB_ID={job_id}", flush=True)
        print(f"VIDEO_URL={video_url}", flush=True)
        return {"job_id": job_id, "video_url": video_url}
    finally:
        if cleanup:
            _smoke_cleanup_job(job_id, r2=True, volume=JOBS_VOL)


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase6_render_fail() -> str:
    """Phase 6 Step 5 — simulate_fail at rendering → job failed."""
    from job_storage import job_dir

    vocals_fixture = Path("/fixtures/vocals_smoke.wav")
    instrumental_fixture = Path("/fixtures/instrumental_smoke.wav")
    lyrics_fixture = Path("/fixtures/lyrics_smoke.json")
    if not vocals_fixture.is_file() or not instrumental_fixture.is_file():
        raise FileNotFoundError("render smoke fixtures missing from image")
    if not lyrics_fixture.is_file():
        raise FileNotFoundError("lyrics_smoke.json missing from image")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    workdir = job_dir(job_id)
    _seed_phase6_stems(
        job_id,
        workdir,
        vocals_fixture=vocals_fixture,
        instrumental_fixture=instrumental_fixture,
        lyrics_fixture=lyrics_fixture,
    )

    _run_real_pipeline(
        job_id,
        volume=JOBS_VOL,
        separate_stems_fn=None,
        transcribe_vocals_fn=None,
        render_karaoke_fn=render_karaoke_modal,
        simulate_fail=True,
        fail_at="rendering",
        clip_end=30.0,
    )

    job = get_job(job_id)
    if job is None or job.get("status") != "failed":
        raise RuntimeError(f"expected failed, got {job}")
    if SIMULATED_FAIL_MESSAGE not in str(job.get("error", "")):
        raise RuntimeError(f"unexpected error: {job.get('error')}")

    mp4_path = workdir / "karaoke.mp4"
    if mp4_path.is_file() and mp4_path.stat().st_size > 0:
        raise RuntimeError(f"render should not have run: {mp4_path}")

    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return job_id


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL})
def smoke_phase6_skeleton_fail() -> str:
    """Skeleton pipeline with simulate_fail → failed in Dict."""
    from job_storage import write_job_input

    fixture = Path("/fixtures/sample_30s.mp3")
    if not fixture.is_file():
        raise FileNotFoundError(f"fixture missing in image: {fixture}")

    job_id = str(uuid.uuid4())
    create_job(job_id)
    write_job_input(
        job_id,
        "sample_30s.mp3",
        "audio/mpeg",
        fixture.read_bytes(),
        volume=JOBS_VOL,
    )
    run_real_pipeline.spawn(job_id, simulate_fail=True)
    _poll_job_skeleton(job_id, expect_failed=True)
    delete_job(job_id)
    print(f"JOB_ID={job_id}", flush=True)
    return job_id


# --- Phase 7 Step 4 — TTL cleanup (R2, Volume, Dict) ---


@app.function(
    image=_BACKEND_IMAGE,
    volumes={JOBS_MOUNT: JOBS_VOL},
    secrets=[R2_SECRET],
    schedule=modal.Period(hours=6),
)
def cleanup_expired_jobs(max_age_hours: int = 24) -> dict:
    """Scheduled sweep of jobs older than ``max_age_hours`` (default 24h)."""
    from cleanup import cleanup_expired_jobs as _cleanup_expired_jobs

    return _cleanup_expired_jobs(volume=JOBS_VOL, max_age_hours=max_age_hours)


@app.function(image=_BACKEND_IMAGE, volumes={JOBS_MOUNT: JOBS_VOL}, secrets=[R2_SECRET])
def smoke_phase7_cleanup_gate(max_age_seconds: int = 60) -> dict:
    """Seed expired + fresh jobs; run cleanup; verify artifacts and Dict rows."""
    from datetime import datetime, timedelta, timezone

    from cleanup import cleanup_expired_jobs as _cleanup_expired_jobs
    from job_storage import find_job_input, job_dir, write_job_input
    from storage import karaoke_mp4_exists, upload_karaoke_mp4

    mp4_fixture = Path("/fixtures/karaoke_smoke.mp4")
    audio_fixture = Path("/fixtures/sample_30s.mp3")
    if not audio_fixture.is_file():
        raise FileNotFoundError(f"fixture missing in image: {audio_fixture}")

    now = datetime.now(timezone.utc)
    expired_at = (now - timedelta(hours=25)).isoformat()
    fresh_at = now.isoformat()

    expired_id = str(uuid.uuid4())
    create_job(expired_id)
    update_job(
        expired_id,
        status="done",
        progress=100,
        message="Done",
        created_at=expired_at,
        video_url="https://example.invalid/smoke",
    )
    write_job_input(
        expired_id,
        "sample_30s.mp3",
        "audio/mpeg",
        audio_fixture.read_bytes(),
        volume=JOBS_VOL,
    )
    if mp4_fixture.is_file():
        upload_karaoke_mp4(mp4_fixture, expired_id)
    print(f"EXPIRED_JOB_ID={expired_id}", flush=True)

    fresh_id = str(uuid.uuid4())
    create_job(fresh_id, is_draft=True)
    update_job(fresh_id, created_at=fresh_at)
    write_job_input(
        fresh_id,
        "sample_30s.mp3",
        "audio/mpeg",
        audio_fixture.read_bytes(),
        volume=JOBS_VOL,
    )
    print(f"FRESH_JOB_ID={fresh_id}", flush=True)

    summary = _cleanup_expired_jobs(
        volume=JOBS_VOL,
        max_age_hours=24,
        max_age_seconds=max_age_seconds,
    )
    if expired_id not in summary.get("deleted", []):
        raise RuntimeError(
            f"expected expired job in deleted list: {summary.get('deleted')}"
        )
    if fresh_id in summary.get("deleted", []):
        raise RuntimeError("fresh job must not be deleted")

    if get_job(expired_id) is not None:
        raise RuntimeError(f"expired Dict row still present: {expired_id}")
    if get_job(fresh_id) is None:
        raise RuntimeError(f"fresh Dict row missing: {fresh_id}")

    JOBS_VOL.reload()
    if find_job_input(expired_id) is not None:
        raise RuntimeError(f"expired Volume input still present: {expired_id}")
    if find_job_input(fresh_id) is None:
        raise RuntimeError(f"fresh Volume input missing: {fresh_id}")
    if job_dir(expired_id).is_dir():
        raise RuntimeError(f"expired workspace dir still present: {expired_id}")

    if mp4_fixture.is_file() and karaoke_mp4_exists(expired_id):
        raise RuntimeError(f"expired R2 object still present: {expired_id}")

    from cleanup import delete_job_artifacts

    delete_job_artifacts(fresh_id, JOBS_VOL, r2=True)
    print(f"JOB_ID={fresh_id}", flush=True)
    return {
        "expired_job_id": expired_id,
        "fresh_job_id": fresh_id,
        "cleanup": summary,
    }


# --- Phase 7 Step 5 — rate limiting ---


@app.function(image=_BACKEND_IMAGE)
def smoke_phase7_rate_limit_reset() -> int:
    """Clear all rate-limit Dict entries (smoke setup/teardown)."""
    from rate_limit import reset_all_rate_limits

    removed = reset_all_rate_limits()
    print(f"RATE_LIMIT_RESET count={removed}", flush=True)
    return removed


@app.function(image=_BACKEND_IMAGE)
def smoke_phase7_rate_limit_module() -> None:
    """Module gate: sixth consume in the same window raises RateLimitExceeded."""
    from rate_limit import (
        RateLimitExceeded,
        consume_job_start_slot,
        reset_rate_limit,
    )

    test_ip = "smoke-module-test"
    reset_rate_limit(test_ip)
    for _ in range(5):
        consume_job_start_slot(test_ip, limit=5, window_s=3600)
    try:
        consume_job_start_slot(test_ip, limit=5, window_s=3600)
    except RateLimitExceeded:
        print("RATE_LIMIT_MODULE_OK", flush=True)
        reset_rate_limit(test_ip)
        return
    raise RuntimeError("expected RateLimitExceeded on 6th consume")


# --- Phase 7 Step 6 — presigned R2 upload smoke ---


@app.function(
    image=_BACKEND_IMAGE,
    volumes={JOBS_MOUNT: JOBS_VOL},
    secrets=[R2_SECRET, API_KEY_SECRET],
)
def smoke_phase7_r2_upload_gate() -> dict:
    """Presigned PUT → sync-upload → input on Volume (no HTTP / pipeline)."""
    from job_storage import find_job_input
    from storage import (
        StorageError,
        presigned_put_upload,
        r2_configured,
        upload_object_exists,
    )

    if not r2_configured():
        raise RuntimeError("R2 is not configured")

    fixture = Path("/fixtures/sample_30s.mp3")
    if not fixture.is_file():
        raise FileNotFoundError(f"fixture missing in image: {fixture}")

    job_id = str(uuid.uuid4())
    create_job(job_id, is_draft=True)
    data = fixture.read_bytes()
    content_type = "audio/mpeg"

    payload = presigned_put_upload(
        job_id,
        filename="sample_30s.mp3",
        content_type=content_type,
        size=len(data),
        max_bytes=50 * 1024 * 1024,
    )
    update_job(job_id, r2_upload_key=payload["object_key"])

    import urllib.request

    req = urllib.request.Request(
        payload["upload_url"],
        data=data,
        method="PUT",
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"presigned PUT failed: HTTP {resp.status}")

    if not upload_object_exists(payload["object_key"]):
        raise RuntimeError("upload missing in R2 after PUT")

    from web import _ingest_r2_upload  # noqa: PLC2701

    _ingest_r2_upload(job_id, jobs_volume=JOBS_VOL, object_key=payload["object_key"])
    JOBS_VOL.reload()
    if find_job_input(job_id) is None:
        raise RuntimeError("input not on Volume after sync")

    from cleanup import delete_job_artifacts

    delete_job_artifacts(
        job_id,
        JOBS_VOL,
        r2=True,
        r2_upload_key=payload["object_key"],
    )
    print(f"JOB_ID={job_id}", flush=True)
    print("R2_UPLOAD_GATE_OK", flush=True)
    return {"job_id": job_id, "object_key": payload["object_key"]}


# --- Phase 7 Step 7 — API key smoke ---


@app.function(image=_BACKEND_IMAGE, secrets=[API_KEY_SECRET])
def smoke_phase7_auth_status() -> dict:
    """Report whether API_KEY is configured in the container."""
    from auth import api_key_configured

    configured = api_key_configured()
    print(f"API_KEY_CONFIGURED={configured}", flush=True)
    return {"api_key_configured": configured}
