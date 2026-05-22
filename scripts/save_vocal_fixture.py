"""Phase 3 Step 4 — copy Demucs vocal stem to fixtures/vocals_30s.wav for Phase 4."""

from __future__ import annotations

import shutil
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "scripts" / "output" / "vocals.wav"
DEST = REPO_ROOT / "scripts" / "fixtures" / "vocals_30s.wav"


def validate_wav(path: Path) -> tuple[float, int]:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        channels = wf.getnchannels()
        duration = frames / rate if rate else 0.0
    return duration, channels


def main() -> int:
    if not SOURCE.is_file() or SOURCE.stat().st_size == 0:
        print(f"FAIL: missing {SOURCE}", file=sys.stderr)
        print("Run: python scripts/test_demucs_local.py", file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, DEST)

    duration, channels = validate_wav(DEST)
    size_mb = DEST.stat().st_size / (1024 * 1024)
    print(f"copied: {SOURCE.name} → {DEST}")
    print(f"size: {size_mb:.2f} MB, duration: {duration:.1f}s, channels: {channels}")

    if duration < 5:
        print("WARN: duration under 5s — unexpected for 30s fixture input", file=sys.stderr)

    print("Phase 3 Step 4 OK — Phase 4 default input ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
