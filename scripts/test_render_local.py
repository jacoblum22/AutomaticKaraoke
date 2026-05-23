"""Render karaoke MP4 from instrumental.wav + lyrics.json — Phase 5 local CLI.

Default: psychosomatic pair → scripts/output/karaoke.mp4 (clips to 30s if long).

Typical runtime (30s clip, CPU): ~10–40s FFmpeg encode.
Full ~3 min song: ~1–3 min depending on CPU.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from render import RenderError, get_audio_duration, render_karaoke  # noqa: E402

DEFAULT_INSTRUMENTAL = REPO_ROOT / "scripts" / "output" / "instrumental.wav"
DEFAULT_LYRICS = REPO_ROOT / "scripts" / "output" / "lyrics.json"
DEFAULT_OUTPUT = REPO_ROOT / "scripts" / "output" / "karaoke.mp4"
PSYCHO_DIR = REPO_ROOT / "scripts" / "output" / "psychosomatic"


def resolve_pair(
    instrumental: Path | None,
    lyrics: Path | None,
) -> tuple[Path, Path]:
    if instrumental is not None and lyrics is not None:
        return instrumental, lyrics
    psycho_i = PSYCHO_DIR / "instrumental.wav"
    psycho_l = PSYCHO_DIR / "lyrics.json"
    if psycho_i.is_file() and psycho_l.is_file():
        return psycho_i, psycho_l
    return DEFAULT_INSTRUMENTAL, DEFAULT_LYRICS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render lyrics + instrumental → karaoke.mp4 (Phase 5)"
    )
    parser.add_argument(
        "--instrumental",
        "-i",
        type=Path,
        default=None,
        help="Instrumental WAV path",
    )
    parser.add_argument(
        "--lyrics",
        "-l",
        type=Path,
        default=None,
        help="lyrics.json path",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output MP4 path",
    )
    parser.add_argument(
        "--ass-out",
        type=Path,
        default=None,
        help="Write ASS to this path (default: beside output MP4)",
    )
    parser.add_argument(
        "--clip-end",
        type=float,
        default=None,
        metavar="SEC",
        help="Only render first SEC seconds",
    )
    parser.add_argument(
        "--no-clip",
        action="store_true",
        help="Render full instrumental length (Phase 5 Step 5 full song)",
    )
    parser.add_argument(
        "--validate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Validate lyrics.json before render (default: on)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1920,
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1080,
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
    )
    args = parser.parse_args()

    instrumental, lyrics = resolve_pair(args.instrumental, args.lyrics)
    if not instrumental.is_file():
        print(f"ERROR: instrumental not found: {instrumental}", file=sys.stderr)
        print("Run Phase 3 Demucs first.", file=sys.stderr)
        return 1
    if not lyrics.is_file():
        print(f"ERROR: lyrics not found: {lyrics}", file=sys.stderr)
        print("Run Phase 4 first.", file=sys.stderr)
        return 1

    if args.validate:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from validate_lyrics_json import validate_lyrics  # noqa: E402

        import json

        try:
            lyrics_data = json.loads(lyrics.read_text(encoding="utf-8"))
            validate_lyrics(lyrics_data, path=str(lyrics))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR: invalid lyrics: {e}", file=sys.stderr)
            return 1

    duration = get_audio_duration(instrumental)
    if args.no_clip:
        clip_end = None
    else:
        clip_end = args.clip_end
        if clip_end is None and duration > 35:
            clip_end = 30.0
            print(
                f"note: clipping to first {clip_end:.0f}s of {duration:.0f}s instrumental "
                "(use --no-clip or --clip-end to override)"
            )

    print(f"instrumental: {instrumental}")
    print(f"lyrics:       {lyrics}")
    print(f"output:       {args.output}")
    if clip_end is not None:
        print(f"clip:         0–{clip_end:.1f}s")

    t0 = time.perf_counter()
    try:
        out = render_karaoke(
            instrumental,
            lyrics,
            args.output,
            ass_path=args.ass_out,
            resolution=(args.width, args.height),
            fps=args.fps,
            clip_end=clip_end,
        )
    except RenderError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - t0
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"written:  {out} ({size_mb:.2f} MB)")
    print(f"done in {elapsed:.1f}s")
    print("Phase 5 local render OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
