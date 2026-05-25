"""lyrics.json schema validation (Phase 4 / 5 contract)."""

from __future__ import annotations

from typing import Any

SEGMENT_TIME_TOLERANCE_S = 0.15


class LyricsValidationError(ValueError):
    """lyrics.json failed schema or timing checks."""


def validate_lyrics(data: Any, *, path: str | None = None) -> dict[str, Any]:
    label = path or "lyrics.json"
    if not isinstance(data, dict):
        raise LyricsValidationError(f"{label}: root must be an object")

    segments = data.get("segments")
    if not isinstance(segments, list):
        raise LyricsValidationError(f"{label}: 'segments' must be an array")
    if not segments:
        raise LyricsValidationError(f"{label}: 'segments' must be non-empty")

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            raise LyricsValidationError(f"{label}: segment[{i}] must be an object")

        for key in ("start", "end", "text", "words"):
            if key not in seg:
                raise LyricsValidationError(f"{label}: segment[{i}] missing '{key}'")

        start = float(seg["start"])
        end = float(seg["end"])
        if start >= end:
            raise LyricsValidationError(
                f"{label}: segment[{i}] start ({start}) must be < end ({end})"
            )

        text = str(seg["text"]).strip()
        if not text:
            raise LyricsValidationError(f"{label}: segment[{i}] text is empty")

        words = seg["words"]
        if not isinstance(words, list) or not words:
            raise LyricsValidationError(f"{label}: segment[{i}] words must be non-empty")

        prev_end = -1.0
        for j, word in enumerate(words):
            if not isinstance(word, dict):
                raise LyricsValidationError(
                    f"{label}: segment[{i}] words[{j}] must be an object"
                )
            for key in ("word", "start", "end"):
                if key not in word:
                    raise LyricsValidationError(
                        f"{label}: segment[{i}] words[{j}] missing '{key}'"
                    )
            w_text = str(word["word"]).strip()
            if not w_text:
                raise LyricsValidationError(
                    f"{label}: segment[{i}] words[{j}] word is empty"
                )
            w_start = float(word["start"])
            w_end = float(word["end"])
            if w_start >= w_end:
                raise LyricsValidationError(
                    f"{label}: segment[{i}] words[{j}] start must be < end"
                )
            if w_start < prev_end - 0.001:
                raise LyricsValidationError(
                    f"{label}: segment[{i}] words[{j}] start not monotonic"
                )
            prev_end = w_end
            if w_start < start - SEGMENT_TIME_TOLERANCE_S:
                raise LyricsValidationError(
                    f"{label}: segment[{i}] words[{j}] starts before segment"
                )
            if w_end > end + SEGMENT_TIME_TOLERANCE_S:
                raise LyricsValidationError(
                    f"{label}: segment[{i}] words[{j}] ends after segment"
                )

    return data
