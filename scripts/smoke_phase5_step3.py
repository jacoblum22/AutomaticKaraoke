"""Phase 5 Step 3 gate — instrumental + lyrics → karaoke.mp4 (30s clip)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from render import RenderError, render_karaoke  # noqa: E402

PSYCHO = REPO_ROOT / "scripts" / "output" / "psychosomatic"
CLIP_END = 30.0
OUTPUT = REPO_ROOT / "scripts" / "output" / "karaoke_30s.mp4"


def main() -> int:
    instrumental = PSYCHO / "instrumental.wav"
    lyrics = PSYCHO / "lyrics.json"

    if not instrumental.is_file() or not lyrics.is_file():
        print("FAIL: need psychosomatic instrumental + lyrics", file=sys.stderr)
        print("Run Phase 3 Step 7 and Phase 4 Step 5.", file=sys.stderr)
        return 1

    print(f"instrumental: {instrumental.name}")
    print(f"lyrics:       {lyrics.name}")
    print(f"clip:         0–{CLIP_END:.0f}s")
    print(f"output:       {OUTPUT}")

    t0 = time.perf_counter()
    try:
        out = render_karaoke(
            instrumental,
            lyrics,
            OUTPUT,
            clip_end=CLIP_END,
        )
    except RenderError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - t0
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"written:  {out} ({size_mb:.2f} MB)")
    print(f"elapsed: {elapsed:.1f}s")
    if elapsed > 60:
        print(f"WARN: render took >60s ({elapsed:.1f}s)", file=sys.stderr)
    print("Phase 5 Step 3 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
