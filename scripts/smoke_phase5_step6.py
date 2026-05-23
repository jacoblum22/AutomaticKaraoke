"""Phase 5 Step 6 gate — Modal CPU render via modal run (ephemeral).

Bakes psychosomatic instrumental + lyrics into _RENDER_IMAGE when present locally.
Default: 30s clip (clip_end=30).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
INSTRUMENTAL = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "instrumental.wav"
LYRICS = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json"
SMOKE_FN = "smoke_render_fixture"
MAX_ELAPSED_30S = 90.0
MAX_ELAPSED_FULL = 180.0


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 Step 6 Modal CPU render smoke")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Render full song (clip_end=None); slower",
    )
    args = parser.parse_args()

    if not INSTRUMENTAL.is_file() or not LYRICS.is_file():
        print("FAIL: need psychosomatic instrumental + lyrics", file=sys.stderr)
        print("Run Phase 3 Step 7 and Phase 4 Step 5.", file=sys.stderr)
        return 1

    clip = "None" if args.full else "30.0"
    cmd = [*_modal_cmd(), "run", f"app.py::{SMOKE_FN}", "--clip-end", clip]
    print("+", " ".join(cmd))
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=env)
    if proc.returncode != 0:
        return proc.returncode

    label = "full song" if args.full else "30s clip"
    limit = MAX_ELAPSED_FULL if args.full else MAX_ELAPSED_30S
    print(f"Phase 5 Step 6 OK (Modal CPU render, {label}, expected <{limit:.0f}s warm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
