"""Phase 4 Step 1 gate — vocal fixture + faster-whisper / whisperx importable."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAL_FIXTURE = REPO_ROOT / "scripts" / "fixtures" / "vocals_30s.wav"
VOCAL_ALTERNATES = (
    REPO_ROOT / "scripts" / "output" / "vocals.wav",
    REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav",
)


def find_vocal_fixture() -> Path | None:
    if VOCAL_FIXTURE.is_file() and VOCAL_FIXTURE.stat().st_size > 0:
        return VOCAL_FIXTURE
    for path in VOCAL_ALTERNATES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def main() -> int:
    vocal = find_vocal_fixture()
    if vocal is None:
        print("FAIL: no vocal stem found.", file=sys.stderr)
        print("Expected:", VOCAL_FIXTURE, file=sys.stderr)
        print("Run:", file=sys.stderr)
        print("  python scripts/test_demucs_local.py", file=sys.stderr)
        print("  python scripts/save_vocal_fixture.py", file=sys.stderr)
        return 1

    print(f"vocal fixture: {vocal} ({vocal.stat().st_size // 1024} KB)")

    try:
        from faster_whisper import WhisperModel  # noqa: F401
        import whisperx
        import torch
    except ImportError as e:
        print(f"FAIL: import error — {e}", file=sys.stderr)
        print("Install: pip install -r backend/requirements-whisper.txt", file=sys.stderr)
        return 1

    cuda = torch.cuda.is_available()
    print(f"faster-whisper: ok")
    print(f"whisperx: ok ({getattr(whisperx, '__version__', 'unknown')})")
    print(f"torch: ok ({torch.__version__}, cuda={cuda})")
    print("Phase 4 Step 1 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
