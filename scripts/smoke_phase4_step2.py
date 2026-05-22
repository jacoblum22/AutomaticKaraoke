"""Phase 4 Step 2 gate — faster-whisper on vocal fixture (no WhisperX yet)."""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from transcribe import (  # noqa: E402
    TranscriptionError,
    log_transcription_summary,
    transcribe_vocals,
)

VOCAL_CANDIDATES = (
    REPO_ROOT / "scripts" / "fixtures" / "vocals_30s.wav",
    REPO_ROOT / "scripts" / "output" / "vocals.wav",
    REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav",
)
# Tone-only Demucs fixture (440 Hz) is ~silent; real stems are much louder.
MIN_PEAK_FOR_SPEECH = 0.02
SMOKE_CLIP_END = 30.0


def wav_peak(path: Path) -> float:
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        n = wf.getnframes()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(n)
    if sw == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        raise ValueError(f"unsupported sample width: {sw}")
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    return float(np.max(np.abs(audio)))


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        return wf.getnframes() / rate if rate else 0.0


def find_vocal_fixture() -> Path | None:
    best: Path | None = None
    best_peak = 0.0
    for path in VOCAL_CANDIDATES:
        if not path.is_file() or path.stat().st_size == 0:
            continue
        peak = wav_peak(path)
        if peak >= MIN_PEAK_FOR_SPEECH:
            return path
        if peak > best_peak:
            best_peak = peak
            best = path
    return best


def main() -> int:
    vocal = find_vocal_fixture()
    if vocal is None:
        print("FAIL: no vocal stem found.", file=sys.stderr)
        print("Expected one of:", file=sys.stderr)
        for p in VOCAL_CANDIDATES:
            print(f"  {p}", file=sys.stderr)
        print("Run Demucs on real vocals (not the 440 Hz tone fixture):", file=sys.stderr)
        print("  python scripts/smoke_phase3_step7.py", file=sys.stderr)
        return 1

    peak = wav_peak(vocal)
    duration = wav_duration(vocal)
    clip_end: float | None = None
    if peak < MIN_PEAK_FOR_SPEECH:
        print(
            f"FAIL: {vocal.name} peak={peak:.4f} — no detectable speech.",
            file=sys.stderr,
        )
        print(
            "fixtures/vocals_30s.wav from the tone-only sample has no lyrics.",
            file=sys.stderr,
        )
        print(
            "Use real vocals, e.g. scripts/output/psychosomatic/vocals.wav",
            file=sys.stderr,
        )
        return 1

    if duration > SMOKE_CLIP_END + 5:
        clip_end = SMOKE_CLIP_END
        print(f"input:  {vocal} ({vocal.stat().st_size // 1024} KB, clip 0–{clip_end:.0f}s)")
    else:
        print(f"input:  {vocal} ({vocal.stat().st_size // 1024} KB, {duration:.0f}s)")

    print("model:  medium (cpu int8 / cuda float16 auto)")

    t0 = time.perf_counter()
    try:
        segments = transcribe_vocals(vocal, clip_end=clip_end)
    except TranscriptionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - t0
    log_transcription_summary(segments)
    print(f"elapsed: {elapsed:.1f}s")
    print("Phase 4 Step 2 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
