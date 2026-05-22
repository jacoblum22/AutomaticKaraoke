#!/usr/bin/env python3
"""Phase 4 Step 7 — smoke Whisper on deployed Modal app `karaoke`.

Default: invoke deployed ``smoke_whisper_fixture`` via ``Function.from_name``.
Use ``--local-run`` for ephemeral ``modal run`` (Step 6).
Use ``--deploy`` to run ``modal deploy app.py`` first.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
VOCAL_SMOKE = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav"
MODAL_APP = "karaoke"
SMOKE_FN = "smoke_whisper_fixture"


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_local_smoke() -> None:
    cmd = [*_modal_cmd(), "run", f"app.py::{SMOKE_FN}"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_deployed_smoke() -> dict:
    import modal

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from validate_lyrics_json import validate_lyrics  # noqa: E402

    print(f"Deployed app: {MODAL_APP}  function: {SMOKE_FN}")
    fn = modal.Function.from_name(MODAL_APP, SMOKE_FN)
    result = fn.remote()
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected return type: {type(result)}")

    lyrics = result.get("lyrics")
    if not isinstance(lyrics, dict):
        raise RuntimeError(f"missing lyrics in result: {list(result.keys())}")

    validate_lyrics(lyrics, path="modal smoke_whisper_fixture")

    elapsed = result.get("elapsed_s")
    print(f"LYRICS_PATH={result.get('lyrics_path')}")
    print(f"ELAPSED_S={elapsed}")
    print(f"segments={result.get('segments')} words={result.get('words')}")
    print(
        f"first={result.get('first_word')!r} @{result.get('first_start')} "
        f"last={result.get('last_word')!r} @{result.get('last_end')}"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 Modal Whisper smoke")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Run modal deploy app.py before smoke",
    )
    parser.add_argument(
        "--local-run",
        action="store_true",
        help="Use modal run (ephemeral) instead of deployed function",
    )
    args = parser.parse_args()

    if not VOCAL_SMOKE.is_file():
        print(f"FAIL: vocal smoke fixture missing: {VOCAL_SMOKE}", file=sys.stderr)
        print("Run: python scripts/smoke_phase3_step7.py", file=sys.stderr)
        print("Redeploy after vocals exist so they are baked into _WHISPER_IMAGE.", file=sys.stderr)
        return 1

    if args.deploy:
        run_deploy()

    if args.local_run:
        run_local_smoke()
    else:
        run_deployed_smoke()

    label = "local run" if args.local_run else "deployed"
    print(f"Phase 4 Modal Whisper smoke OK ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
