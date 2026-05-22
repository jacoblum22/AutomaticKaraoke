"""Transcription + alignment on vocal stem — Phase 4 local CLI.

Default: psychosomatic or other real vocal stem → scripts/output/lyrics.json

Typical runtime (30s clip, CPU): transcribe ~1–2 min + align ~1–3 min (first run downloads models).
Full ~3 min song on CPU: tens of minutes; use Modal GPU in Phase 4 Step 6+.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from transcribe import (  # noqa: E402
    TranscriptionError,
    log_lyrics_summary,
    transcribe_and_align,
)

DEFAULT_INPUT = REPO_ROOT / "scripts" / "fixtures" / "vocals_30s.wav"
DEFAULT_OUTPUT = REPO_ROOT / "scripts" / "output" / "lyrics.json"
VOCAL_ALTERNATES = (
    REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav",
    REPO_ROOT / "scripts" / "output" / "vocals.wav",
)
MIN_PEAK_FOR_SPEECH = 0.02


def wav_peak(path: Path) -> float:
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        n = wf.getnframes()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(n)
    if sw != 2:
        raise ValueError(f"unsupported sample width: {sw}")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    return float(np.max(np.abs(audio)))


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        return wf.getnframes() / rate if rate else 0.0


def resolve_input(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    if DEFAULT_INPUT.is_file() and wav_peak(DEFAULT_INPUT) >= MIN_PEAK_FOR_SPEECH:
        return DEFAULT_INPUT
    for path in VOCAL_ALTERNATES:
        if path.is_file() and wav_peak(path) >= MIN_PEAK_FOR_SPEECH:
            return path
    return DEFAULT_INPUT


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe + align vocals → lyrics.json (Phase 4)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
        help="Vocal stem WAV (default: speech-capable fixture path)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output lyrics.json path",
    )
    parser.add_argument(
        "--model",
        default="medium",
        help="faster-whisper model size",
    )
    parser.add_argument(
        "--device",
        "-d",
        default=None,
        help="Device for transcribe + align (default: cuda if available)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language code for transcribe + wav2vec2 align",
    )
    parser.add_argument(
        "--clip-end",
        type=float,
        default=None,
        metavar="SEC",
        help="Only process first SEC seconds (smoke / quick tests)",
    )
    parser.add_argument(
        "--no-clip",
        action="store_true",
        help="Process entire vocal stem (Phase 4 Step 5 full song)",
    )
    args = parser.parse_args()

    input_path = resolve_input(args.input)
    if not input_path.is_file():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        print("Run Phase 3 Demucs, e.g. scripts/smoke_phase3_step7.py", file=sys.stderr)
        return 1

    peak = wav_peak(input_path)
    if peak < MIN_PEAK_FOR_SPEECH:
        print(
            f"ERROR: {input_path} has no detectable speech (peak={peak:.4f}).",
            file=sys.stderr,
        )
        print(
            "Use real vocals, e.g. scripts/output/psychosomatic/vocals.wav",
            file=sys.stderr,
        )
        return 1

    duration = wav_duration(input_path)
    if args.no_clip:
        clip_end = None
    else:
        clip_end = args.clip_end
        if clip_end is None and duration > 35:
            clip_end = 30.0
            print(
                f"note: clipping to first {clip_end:.0f}s of {duration:.0f}s stem "
                "(use --no-clip for full song)"
            )

    print(f"input:    {input_path}")
    print(f"output:   {args.output}")
    print(f"model:    {args.model}")
    print(f"device:   {args.device or 'auto'}")
    print(f"language: {args.language}")
    if clip_end is not None:
        print(f"clip:     0–{clip_end:.1f}s")

    t0 = time.perf_counter()
    try:
        out_path = transcribe_and_align(
            input_path,
            args.output,
            model_size=args.model,
            device=args.device,
            language=args.language,
            clip_end=clip_end,
        )
        lyrics = json.loads(out_path.read_text(encoding="utf-8"))
    except TranscriptionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - t0
    log_lyrics_summary(lyrics)
    print(f"written:  {out_path} ({out_path.stat().st_size} bytes)")
    print(f"done in {elapsed:.1f}s")
    print("Phase 4 local transcribe+align OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
