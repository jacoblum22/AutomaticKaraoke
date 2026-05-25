"""Lyrics output checks for the Phase 6 pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from lyrics_contract import validate_lyrics

LYRICS_JSON = "lyrics.json"


def lyrics_json_path(workdir: Path) -> Path:
    return workdir / LYRICS_JSON


def verify_lyrics_json(path: Path) -> dict[str, int | str | float]:
    """Load lyrics.json and validate contract."""
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"lyrics.json missing or empty: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    validate_lyrics(data, path=str(path))

    segments = data["segments"]
    word_count = sum(len(s["words"]) for s in segments)
    return {
        "lyrics_path": str(path),
        "segments": len(segments),
        "words": word_count,
        "language": str(data.get("language", "en")),
        "lyrics_bytes": path.stat().st_size,
    }
