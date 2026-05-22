"""Modal app entrypoint. Phase 2: web endpoints; Phase 6: orchestration."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import modal

from jobs import create_job, delete_job, get_job, set_failed, update_job
from orchestrator import STUB_VIDEO_URL, run_stub_pipeline as _run_stub_pipeline

app = modal.App("karaoke")

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_FIXTURE_MP3 = _REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3"
_PSYCHO_MP3 = _REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3"

_BACKEND_IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(_BACKEND_DIR / "requirements.txt")
    .add_local_dir(_BACKEND_DIR, remote_path="/root")
)

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
    """Background stub pipeline (spawned from start-job in Step 3)."""
    _run_stub_pipeline(job_id, simulate_fail=simulate_fail)


# --- Phase 2 Step 3 — HTTP API ---


@app.function(image=_BACKEND_IMAGE)
@modal.asgi_app(label="karaoke-api")
def karaoke_api():
    from web import create_api

    return create_api(spawn_pipeline=lambda job_id: run_stub_pipeline.spawn(job_id))


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


# --- Phase 3 — Demucs GPU ---


@app.function(image=_DEMUCS_IMAGE, gpu="T4", timeout=1200)
def separate_stems(
    input_path: str,
    output_dir: str,
    *,
    device: str = "cuda",
) -> tuple[str, str]:
    """Run Demucs on GPU; returns (vocals_path, instrumental_path)."""
    from separate import separate_audio

    vocals_path, instrumental_path = separate_audio(
        input_path,
        output_dir,
        device=device,
        progress=True,
    )
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
