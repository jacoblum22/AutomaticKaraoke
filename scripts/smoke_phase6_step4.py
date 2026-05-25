#!/usr/bin/env python3
"""Phase 6 Step 4 — transcribe + align inside the real pipeline.

Runs Demucs then Whisper on the job Volume; validates lyrics.json contract.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
MODAL_APP = "karaoke"
TRANSCRIBE_PIPELINE_FN = "smoke_phase6_transcribe_pipeline"

FIXTURE_CANDIDATES = (
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3",
)


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def find_fixture() -> Path:
    for path in FIXTURE_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    raise FileNotFoundError("No audio fixture found under scripts/fixtures/")


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_modal_smoke() -> dict:
    import modal

    fn = modal.Function.from_name(MODAL_APP, TRANSCRIBE_PIPELINE_FN)
    return fn.remote()


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 4 transcribe pipeline smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    args = parser.parse_args()

    fixture = find_fixture()
    print(f"fixture:  {fixture} ({fixture.stat().st_size} bytes)")
    print(
        "note:     Whisper on T4 (~1–3 min). Uses vocals_smoke.wav or Psychosomatic.mp3 "
        "in the deployed image (not the 440 Hz tone fixture)."
    )

    if args.deploy:
        run_deploy()

    print("\n[1/1] modal smoke_phase6_transcribe_pipeline …")
    info = run_modal_smoke()
    print(f"lyrics:     {info.get('lyrics_path')}")
    print(f"segments:   {info.get('segments')}")
    print(f"words:      {info.get('words')}")
    print(f"language:   {info.get('language')}")
    print(f"size:       {info.get('lyrics_bytes')} bytes")
    print("\nPhase 6 Step 4 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
