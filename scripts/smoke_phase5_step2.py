"""Phase 5 Step 2 gate — lyrics.json → ASS with karaoke tags (no FFmpeg)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from render import RenderError, count_karaoke_tags, lyrics_to_ass, write_ass  # noqa: E402
from validate_lyrics_json import validate_lyrics  # noqa: E402
from validate_ass import validate_ass  # noqa: E402

LYRICS_CANDIDATES = (
    REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json",
    REPO_ROOT / "scripts" / "output" / "lyrics.json",
)
DEFAULT_ASS = REPO_ROOT / "scripts" / "output" / "subtitles.ass"


def find_lyrics() -> Path | None:
    for path in LYRICS_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def main() -> int:
    lyrics_path = find_lyrics()
    if lyrics_path is None:
        print("FAIL: no lyrics.json found.", file=sys.stderr)
        print("Run Phase 4, e.g. scripts/smoke_phase4_step3.py", file=sys.stderr)
        return 1

    print(f"lyrics: {lyrics_path}")

    try:
        lyrics = json.loads(lyrics_path.read_text(encoding="utf-8"))
        validate_lyrics(lyrics, path=str(lyrics_path))
        ass_text = lyrics_to_ass(lyrics)
        out_path = write_ass(DEFAULT_ASS, lyrics)
        stats = validate_ass(ass_text, path=str(out_path))
    except (RenderError, ValueError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    seg_count = len(lyrics["segments"])
    word_count = sum(len(s["words"]) for s in lyrics["segments"])
    print(f"written:  {out_path} ({out_path.stat().st_size} bytes)")
    print(f"segments: {seg_count}, words: {word_count}")
    print(f"dialogues: {stats['dialogues']}, k_tags: {stats['k_tags']}")
    if stats["k_tags"] < word_count:
        print(
            f"WARN: fewer k tags than words ({stats['k_tags']} < {word_count})",
            file=sys.stderr,
        )

    first_line = next(ln for ln in ass_text.splitlines() if ln.startswith("Dialogue:"))
    preview = first_line[:120] + ("..." if len(first_line) > 120 else "")
    print(f"preview:  {preview}")
    print("Phase 5 Step 2 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
