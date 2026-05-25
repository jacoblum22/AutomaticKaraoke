"""Max audio duration guardrail (Phase 7 Step 3)."""

from __future__ import annotations

from pathlib import Path

from job_logging import probe_media_duration_s

MAX_AUDIO_DURATION_S = 480  # 8 minutes


def format_max_duration_error(duration_s: float) -> str:
    """User-visible message when audio exceeds the limit."""
    limit_min = MAX_AUDIO_DURATION_S / 60
    actual_min = duration_s / 60
    return (
        f"Audio is too long ({actual_min:.1f} min). "
        f"Maximum length is {limit_min:.0f} minutes."
    )


def max_duration_violation(input_path: Path) -> str | None:
    """Return an error message if ``input_path`` exceeds the limit, else None."""
    duration_s = probe_media_duration_s(input_path)
    if duration_s is None:
        return None
    if duration_s > MAX_AUDIO_DURATION_S:
        return format_max_duration_error(duration_s)
    return None
