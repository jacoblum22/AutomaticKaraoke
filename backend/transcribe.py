"""faster-whisper + WhisperX alignment on vocal stem (Phase 4).

Input: vocals.wav (from Demucs — never the full mix)
Output: lyrics.json with word-level timestamps (after align in Step 3+)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import torch as th

DEFAULT_MODEL_SIZE = "medium"
DEFAULT_LANGUAGE = "en"


class TranscriptionError(RuntimeError):
    """Whisper transcription failed."""


class WordSegment(TypedDict):
    word: str
    start: float
    end: float


class RawSegment(TypedDict):
    start: float
    end: float
    text: str
    words: list[WordSegment]


def _resolve_device(device: str | None) -> str:
    if device is not None:
        return device
    return "cuda" if th.cuda.is_available() else "cpu"


def _resolve_compute_type(device: str, compute_type: str | None) -> str:
    if compute_type is not None:
        return compute_type
    return "float16" if device == "cuda" else "int8"


def _segment_to_dict(segment: Any) -> RawSegment:
    words: list[WordSegment] = []
    if segment.words:
        for w in segment.words:
            words.append(
                {
                    "word": w.word.strip(),
                    "start": float(w.start),
                    "end": float(w.end),
                }
            )
    return {
        "start": float(segment.start),
        "end": float(segment.end),
        "text": segment.text.strip(),
        "words": words,
    }


def transcribe_vocals(
    vocals_path: Path | str,
    *,
    model_size: str = DEFAULT_MODEL_SIZE,
    device: str | None = None,
    compute_type: str | None = None,
    language: str = DEFAULT_LANGUAGE,
    clip_end: float | None = None,
) -> list[RawSegment]:
    """Transcribe isolated vocal stem with faster-whisper (rough word times).

    Returns segment dicts suitable for WhisperX ``align()`` in Step 3.

    ``clip_end``: if set, only transcribe ``0``–``clip_end`` seconds (smoke / short tests).
    """
    vocals_path = Path(vocals_path)
    if not vocals_path.is_file():
        raise TranscriptionError(f"Vocal file not found: {vocals_path}")
    if vocals_path.stat().st_size == 0:
        raise TranscriptionError(f"Vocal file is empty: {vocals_path}")

    dev = _resolve_device(device)
    ctype = _resolve_compute_type(dev, compute_type)

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise TranscriptionError(
            "faster-whisper not installed; pip install -r backend/requirements-whisper.txt"
        ) from e

    try:
        model = WhisperModel(model_size, device=dev, compute_type=ctype)
        transcribe_kwargs: dict[str, Any] = {
            "language": language,
            "word_timestamps": True,
            "vad_filter": True,
        }
        if clip_end is not None:
            transcribe_kwargs["clip_timestamps"] = f"0,{clip_end}"
        raw_segments, _info = model.transcribe(str(vocals_path), **transcribe_kwargs)
        segments = [_segment_to_dict(s) for s in raw_segments]
    except TranscriptionError:
        raise
    except Exception as e:
        raise TranscriptionError(f"Transcription failed: {e}") from e

    if not segments:
        raise TranscriptionError("No speech segments detected in vocal stem")

    if not any(seg["words"] for seg in segments):
        raise TranscriptionError("Segments have no word timestamps (check word_timestamps=True)")

    return segments


def log_transcription_summary(segments: list[RawSegment]) -> None:
    """Print segment count and first/last word times (Step 2 debug)."""
    word_count = sum(len(s["words"]) for s in segments)
    all_words = [w for s in segments for w in s["words"]]
    first = all_words[0]
    last = all_words[-1]
    print(f"segments: {len(segments)}")
    print(f"words:    {word_count}")
    print(
        f"first:    {first['word']!r} {first['start']:.2f}s–{first['end']:.2f}s"
    )
    print(f"last:     {last['word']!r} {last['start']:.2f}s–{last['end']:.2f}s")
    print(f"span:     {segments[0]['start']:.2f}s – {segments[-1]['end']:.2f}s")


def align_lyrics(
    vocals_path: Path | str,
    segments: list[RawSegment],
    *,
    device: str | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> list[RawSegment]:
    """WhisperX forced alignment — implemented in Phase 4 Step 3."""
    raise NotImplementedError("align_lyrics: Phase 4 Step 3")


def transcribe_and_align(
    vocals_path: Path | str,
    output_json: Path | str,
    **opts: Any,
) -> Path:
    """Full transcribe + align + write lyrics.json — Phase 4 Step 3+."""
    raise NotImplementedError("transcribe_and_align: Phase 4 Step 3")
