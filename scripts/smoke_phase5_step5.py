"""Phase 5 Step 5 gate — full-song psychosomatic karaoke.mp4 (local CPU)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PSYCHO = REPO_ROOT / "scripts" / "output" / "psychosomatic"
INSTRUMENTAL = PSYCHO / "instrumental.wav"
LYRICS = PSYCHO / "lyrics.json"
OUTPUT = PSYCHO / "karaoke.mp4"

# Full song ~3 min; allow slack for encode + instrumental tail
MIN_DURATION_S = 170.0
MAX_DURATION_S = 210.0
MAX_RENDER_S = 300.0


def ffprobe_duration(path: Path) -> float | None:
    exe = shutil.which("ffprobe")
    if exe is None:
        return None
    proc = subprocess.run(
        [
            exe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def main() -> int:
    if not INSTRUMENTAL.is_file() or not LYRICS.is_file():
        print("FAIL: need psychosomatic instrumental + lyrics", file=sys.stderr)
        print("Run Phase 3 Step 7 and Phase 4 Step 5.", file=sys.stderr)
        return 1

    lyrics = json.loads(LYRICS.read_text(encoding="utf-8"))
    segments = lyrics.get("segments") or []
    if not segments:
        print("FAIL: lyrics.json has no segments", file=sys.stderr)
        return 1
    last_word_end = max(w["end"] for s in segments for w in s["words"])
    print(f"instrumental: {INSTRUMENTAL.name}")
    print(f"lyrics:       {LYRICS.name} ({len(segments)} segments, span ~{last_word_end:.0f}s)")
    print(f"output:       {OUTPUT}")

    py = sys.executable
    test = REPO_ROOT / "scripts" / "test_render_local.py"
    import time

    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            py,
            str(test),
            "--instrumental",
            str(INSTRUMENTAL),
            "--lyrics",
            str(LYRICS),
            "--output",
            str(OUTPUT),
            "--no-clip",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        return proc.returncode

    if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
        print(f"FAIL: missing or empty output: {OUTPUT}", file=sys.stderr)
        return 1

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    duration = ffprobe_duration(OUTPUT)
    print(f"written:  {OUTPUT} ({size_mb:.2f} MB)")
    print(f"elapsed:  {elapsed:.1f}s")
    if duration is not None:
        print(f"duration: {duration:.1f}s")
        if duration < MIN_DURATION_S or duration > MAX_DURATION_S:
            print(
                f"WARN: duration {duration:.1f}s outside expected "
                f"{MIN_DURATION_S:.0f}–{MAX_DURATION_S:.0f}s",
                file=sys.stderr,
            )
    else:
        print("note: ffprobe unavailable — skip duration check")

    if elapsed > MAX_RENDER_S:
        print(f"WARN: render took >{MAX_RENDER_S:.0f}s ({elapsed:.1f}s)", file=sys.stderr)

    print("Phase 5 Step 5 OK — manual QA: play MP4, spot-check sync on chorus + verse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
