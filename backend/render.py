"""ASS subtitle generation + FFmpeg MP4 burn-in (Phase 5).

Input: instrumental.wav, lyrics.json
Output: karaoke.mp4
"""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RenderError(RuntimeError):
    """ASS generation or FFmpeg render failed."""


@dataclass(frozen=True)
class AssStyle:
    """ASS style defaults for karaoke lines."""

    name: str = "Karaoke"
    font: str = "Arial"
    font_size: int = 48
    primary_colour: str = "&H00FFFFFF"  # white (BGR)
    secondary_colour: str = "&H0000FFFF"  # yellow highlight (BGR)
    outline_colour: str = "&H00000000"
    back_colour: str = "&H80000000"
    outline: int = 3
    shadow: int = 1
    alignment: int = 2  # bottom center
    margin_v: int = 40
    play_res_x: int = 1920
    play_res_y: int = 1080


def _escape_ass_text(text: str) -> str:
    """Escape plain text for ASS Dialogue lines (outside override blocks)."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def format_ass_time(seconds: float) -> str:
    """ASS timestamp H:MM:SS.cc (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _word_duration_cs(start: float, end: float) -> int:
    """Karaoke \\k duration in centiseconds (minimum 1)."""
    return max(1, int(round((end - start) * 100)))


def _segment_karaoke_text(words: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for word in words:
        w = str(word.get("word", "")).strip()
        if not w:
            continue
        start = float(word["start"])
        end = float(word["end"])
        k = _word_duration_cs(start, end)
        parts.append(f"{{\\k{k}}}{_escape_ass_text(w)}")
    if not parts:
        raise RenderError("segment has no words for ASS karaoke line")
    return " ".join(parts)


def _style_section(style: AssStyle) -> str:
    return f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {style.name},{style.font},{style.font_size},{style.primary_colour},{style.secondary_colour},{style.outline_colour},{style.back_colour},-1,0,0,0,100,100,0,0,1,{style.outline},{style.shadow},{style.alignment},20,20,{style.margin_v},1
"""


def lyrics_to_ass(lyrics: dict[str, Any], *, style: AssStyle | None = None) -> str:
    """Convert Phase 4 lyrics.json to ASS v4+ with karaoke {\\k} tags per word."""
    style = style or AssStyle()
    segments = lyrics.get("segments")
    if not isinstance(segments, list) or not segments:
        raise RenderError("lyrics must have non-empty 'segments'")

    header = f"""[Script Info]
Title: Automatic Karaoke
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {style.play_res_x}
PlayResY: {style.play_res_y}

{_style_section(style)}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogues: list[str] = []
    for seg in segments:
        if not isinstance(seg, dict):
            raise RenderError("each segment must be an object")
        words = seg.get("words")
        if not isinstance(words, list) or not words:
            raise RenderError("segment missing non-empty 'words'")
        start = float(seg["start"])
        end = float(seg["end"])
        if start >= end:
            raise RenderError(f"segment start must be < end ({start} >= {end})")
        text = _segment_karaoke_text(words)
        line = (
            f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},"
            f"{style.name},,0,0,0,,{text}"
        )
        dialogues.append(line)

    return header + "\n".join(dialogues) + "\n"


def write_ass(
    ass_path: Path | str,
    lyrics: dict[str, Any] | Path | str,
    *,
    style: AssStyle | None = None,
) -> Path:
    """Write ASS file from lyrics dict or path to lyrics.json."""
    ass_path = Path(ass_path)
    if isinstance(lyrics, (str, Path)):
        lyrics_path = Path(lyrics)
        if not lyrics_path.is_file():
            raise RenderError(f"lyrics file not found: {lyrics_path}")
        lyrics = json.loads(lyrics_path.read_text(encoding="utf-8"))

    content = lyrics_to_ass(lyrics, style=style)
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path.write_text(content, encoding="utf-8")
    if ass_path.stat().st_size == 0:
        raise RenderError(f"failed to write ASS: {ass_path}")
    return ass_path


def count_karaoke_tags(ass_content: str) -> int:
    """Count {\\kNN} tags (for smokes)."""
    import re

    return len(re.findall(r"\\k\d+", ass_content))


def _find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RenderError("ffmpeg not on PATH; run scripts/smoke_phase5_step1.py")
    return exe


def get_audio_duration(path: Path | str) -> float:
    """WAV duration via stdlib (sufficient for Phase 5)."""
    path = Path(path)
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        if rate <= 0:
            raise RenderError(f"invalid sample rate: {path}")
        return wf.getnframes() / rate


def _subtitles_filter_path(ass_path: Path) -> str:
    """Escape ASS path for FFmpeg subtitles filter (Windows-safe)."""
    s = ass_path.resolve().as_posix().replace("'", r"\'")
    if len(s) >= 2 and s[1] == ":":
        s = s[0] + r"\:" + s[2:]
    return f"subtitles='{s}'"


def filter_lyrics_to_clip(lyrics: dict[str, Any], clip_end: float) -> dict[str, Any]:
    """Trim segments/words to ``0``–``clip_end`` seconds for short renders."""
    out_segments: list[dict[str, Any]] = []
    for seg in lyrics.get("segments", []):
        if float(seg["start"]) >= clip_end:
            continue
        words = [
            w
            for w in seg.get("words", [])
            if float(w["start"]) < clip_end
        ]
        if not words:
            continue
        last = words[-1]
        word_end = min(float(last["end"]), clip_end)
        words[-1] = {**last, "end": word_end}
        out_segments.append(
            {
                "start": float(seg["start"]),
                "end": min(float(seg["end"]), clip_end),
                "text": seg.get("text", ""),
                "words": words,
            }
        )
    if not out_segments:
        raise RenderError(f"no lyrics content before {clip_end}s")
    return {**lyrics, "segments": out_segments}


def render_karaoke(
    instrumental_path: Path | str,
    lyrics_path: Path | str,
    output_mp4: Path | str,
    *,
    ass_path: Path | str | None = None,
    style: AssStyle | None = None,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 30,
    clip_end: float | None = None,
) -> Path:
    """Burn karaoke ASS over instrumental audio → MP4 (H.264 + AAC)."""
    instrumental_path = Path(instrumental_path)
    lyrics_path = Path(lyrics_path)
    output_mp4 = Path(output_mp4)

    if not instrumental_path.is_file():
        raise RenderError(f"instrumental not found: {instrumental_path}")
    if instrumental_path.stat().st_size == 0:
        raise RenderError(f"instrumental is empty: {instrumental_path}")
    if not lyrics_path.is_file():
        raise RenderError(f"lyrics not found: {lyrics_path}")

    lyrics = json.loads(lyrics_path.read_text(encoding="utf-8"))
    if clip_end is not None:
        lyrics = filter_lyrics_to_clip(lyrics, clip_end)

    if ass_path is None:
        ass_path = output_mp4.parent / "subtitles.ass"
    ass_path = write_ass(ass_path, lyrics, style=style)

    width, height = resolution
    vf = _subtitles_filter_path(ass_path)
    ffmpeg = _find_ffmpeg()

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [ffmpeg, "-y"]
    if clip_end is not None:
        cmd.extend(["-t", str(clip_end)])
    cmd.extend(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:r={fps}",
            "-i",
            str(instrumental_path.resolve()),
            "-vf",
            vf,
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            str(output_mp4.resolve()),
        ]
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RenderError("FFmpeg timed out after 600s") from e

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        raise RenderError(f"FFmpeg failed (exit {proc.returncode}):\n{tail}")

    if not output_mp4.is_file() or output_mp4.stat().st_size == 0:
        raise RenderError(f"MP4 missing or empty: {output_mp4}")

    return output_mp4
