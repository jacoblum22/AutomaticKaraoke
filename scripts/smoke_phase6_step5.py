#!/usr/bin/env python3
"""Phase 6 Step 5 — FFmpeg render inside the real pipeline.

Produces karaoke.mp4 on the job Volume (no R2 yet).
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
RENDER_PIPELINE_FN = "smoke_phase6_render_pipeline"
RENDER_FAIL_FN = "smoke_phase6_render_fail"


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_modal(target: str) -> None:
    cmd = [*_modal_cmd(), "run", target]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 5 render pipeline smoke")
    parser.add_argument("--deploy", action="store_true", help="modal deploy before smoke")
    parser.add_argument(
        "--skip-fail",
        action="store_true",
        help="Skip render failure smoke",
    )
    args = parser.parse_args()

    print(
        "note:     Whisper + FFmpeg on Modal (~2–6 min). Requires vocals_smoke.wav and "
        "instrumental_smoke.wav baked into the image."
    )

    if args.deploy:
        run_deploy()

    print("\n[1/2] modal smoke_phase6_render_pipeline …")
    import modal

    fn = modal.Function.from_name(MODAL_APP, RENDER_PIPELINE_FN)
    info = fn.remote()
    print(f"mp4:        {info.get('mp4_path')}")
    print(f"size:       {info.get('size_bytes')} bytes")

    if not args.skip_fail:
        print("\n[2/2] modal smoke_phase6_render_fail …")
        run_modal("app.py::smoke_phase6_render_fail")

    print("\nPhase 6 Step 5 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
