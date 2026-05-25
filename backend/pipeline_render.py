"""Karaoke MP4 output checks for the Phase 6 pipeline."""

from __future__ import annotations

from pathlib import Path

KARAOKE_MP4 = "karaoke.mp4"
MIN_MP4_BYTES = 1024


def karaoke_mp4_path(workdir: Path) -> Path:
    return workdir / KARAOKE_MP4


def verify_karaoke_mp4(path: Path, *, min_bytes: int = MIN_MP4_BYTES) -> dict[str, int | str]:
    if not path.is_file():
        raise FileNotFoundError(f"karaoke.mp4 missing: {path}")
    size_bytes = path.stat().st_size
    if size_bytes < min_bytes:
        raise ValueError(f"karaoke.mp4 too small: {size_bytes} bytes")
    return {"mp4_path": str(path), "size_bytes": size_bytes}
