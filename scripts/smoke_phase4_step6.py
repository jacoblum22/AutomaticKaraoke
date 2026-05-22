"""Phase 4 Step 6 gate — Modal GPU smoke_whisper_fixture (ephemeral modal run)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
VOCAL_SMOKE = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav"


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def main() -> int:
    if not VOCAL_SMOKE.is_file():
        print(f"FAIL: {VOCAL_SMOKE} missing", file=sys.stderr)
        print("Run: python scripts/smoke_phase3_step7.py", file=sys.stderr)
        return 1

    cmd = [*_modal_cmd(), "run", "app.py::smoke_whisper_fixture"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False)
    if proc.returncode != 0:
        return proc.returncode
    print("Phase 4 Step 6 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
