"""Phase 5 Step 4 gate — repeatable local render CLI (30s clip default)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    py = sys.executable
    test = REPO_ROOT / "scripts" / "test_render_local.py"
    out = REPO_ROOT / "scripts" / "output" / "karaoke.mp4"

    psycho_i = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "instrumental.wav"
    psycho_l = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json"
    if not psycho_i.is_file() or not psycho_l.is_file():
        print("FAIL: need psychosomatic instrumental + lyrics", file=sys.stderr)
        print("Run Phase 3 Step 7 and Phase 4 Step 5.", file=sys.stderr)
        return 1

    print("Phase 5 Step 4 — test_render_local.py (psychosomatic pair, 30s clip)")
    proc = subprocess.run(
        [
            py,
            str(test),
            "--instrumental",
            str(psycho_i),
            "--lyrics",
            str(psycho_l),
            "--output",
            str(out),
            "--clip-end",
            "30",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if proc.returncode != 0:
        return proc.returncode

    if not out.is_file() or out.stat().st_size == 0:
        print(f"FAIL: missing or empty output: {out}", file=sys.stderr)
        return 1

    print(f"output: {out} ({out.stat().st_size // 1024} KB)")
    print("Phase 5 Step 4 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
