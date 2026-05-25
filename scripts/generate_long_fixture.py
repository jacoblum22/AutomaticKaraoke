#!/usr/bin/env python3
"""Generate a >8 minute test MP3 for Phase 7 Step 3 duration guardrail.

Creates scripts/fixtures/over_8min.mp3 (~9 min tone). Requires ffmpeg on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "scripts" / "fixtures" / "over_8min.mp3"

# Slightly over 8 minutes so ffprobe rejects under MAX_AUDIO_DURATION_S=480.
DURATION_S = 541


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not on PATH", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={DURATION_S}",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "6",
            str(OUT_PATH),
        ],
        check=True,
        capture_output=True,
    )
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size // 1024} KB, {DURATION_S}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
