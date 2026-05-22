"""Phase 3 Step 4 gate — vocals_30s.wav exists and is valid WAV."""

from __future__ import annotations

import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAL_FIXTURE = REPO_ROOT / "scripts" / "fixtures" / "vocals_30s.wav"


def main() -> int:
    if not VOCAL_FIXTURE.is_file() or VOCAL_FIXTURE.stat().st_size == 0:
        print("FAIL: missing scripts/fixtures/vocals_30s.wav", file=sys.stderr)
        print("Run:", file=sys.stderr)
        print("  python scripts/test_demucs_local.py", file=sys.stderr)
        print("  python scripts/save_vocal_fixture.py", file=sys.stderr)
        return 1

    with wave.open(str(VOCAL_FIXTURE), "rb") as wf:
        duration = wf.getnframes() / wf.getframerate()
        channels = wf.getnchannels()
        rate = wf.getframerate()

    print(f"fixture: {VOCAL_FIXTURE}")
    print(f"size: {VOCAL_FIXTURE.stat().st_size} bytes")
    print(f"duration: {duration:.1f}s, {channels} ch @ {rate} Hz")
    print("Phase 4 default: scripts/test_whisper_local.py → vocals_30s.wav")
    print("Phase 3 Step 4 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
