"""Stem output checks for the Phase 6 pipeline."""

from __future__ import annotations

import wave
from pathlib import Path

OUTPUT_VOCALS = "vocals.wav"
OUTPUT_INSTRUMENTAL = "instrumental.wav"

MAX_STEM_DURATION_DELTA_S = 3.0


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        if rate <= 0:
            raise ValueError(f"invalid sample rate: {path}")
        return wf.getnframes() / float(rate)


def expected_stem_paths(workdir: Path) -> tuple[Path, Path]:
    return workdir / OUTPUT_VOCALS, workdir / OUTPUT_INSTRUMENTAL


def verify_stem_outputs(
    workdir: Path,
    *,
    max_stem_delta_s: float = MAX_STEM_DURATION_DELTA_S,
) -> dict[str, float | int]:
    """Ensure Demucs outputs exist, are non-empty, and have matching durations."""
    vocals_path, instrumental_path = expected_stem_paths(workdir)

    for label, path in ("vocals", vocals_path), ("instrumental", instrumental_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"{label} stem missing or empty: {path}")

    vocals_dur = wav_duration_seconds(vocals_path)
    instrumental_dur = wav_duration_seconds(instrumental_path)
    delta = abs(vocals_dur - instrumental_dur)
    if delta > max_stem_delta_s:
        raise ValueError(
            f"stem duration mismatch {delta:.2f}s > {max_stem_delta_s}s "
            f"(vocals={vocals_dur:.2f}s, instrumental={instrumental_dur:.2f}s)"
        )

    return {
        "vocals_path": str(vocals_path),
        "instrumental_path": str(instrumental_path),
        "vocals_duration_s": vocals_dur,
        "instrumental_duration_s": instrumental_dur,
        "vocals_bytes": vocals_path.stat().st_size,
        "instrumental_bytes": instrumental_path.stat().st_size,
    }
