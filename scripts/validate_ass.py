"""Validate generated ASS subtitle structure (Phase 5 Step 2)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


class AssValidationError(ValueError):
    """ASS file failed structure checks."""


REQUIRED_SECTIONS = ("[Script Info]", "[V4+ Styles]", "[Events]")
K_TAG_PATTERN = re.compile(r"\\k\d+")


def validate_ass(content: str, *, path: str | None = None) -> dict[str, int]:
    label = path or "subtitles.ass"
    if not content.strip():
        raise AssValidationError(f"{label}: empty file")

    for section in REQUIRED_SECTIONS:
        if section not in content:
            raise AssValidationError(f"{label}: missing {section}")

    dialogues = [ln for ln in content.splitlines() if ln.startswith("Dialogue:")]
    if not dialogues:
        raise AssValidationError(f"{label}: no Dialogue lines")

    k_count = len(K_TAG_PATTERN.findall(content))
    if k_count == 0:
        raise AssValidationError(f"{label}: no karaoke {{\\k}} tags")

    return {
        "dialogues": len(dialogues),
        "k_tags": k_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ASS file (Phase 5)")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("scripts/output/subtitles.ass"),
        help="Path to .ass file",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"FAIL: file not found: {args.path}", file=sys.stderr)
        return 1

    try:
        text = args.path.read_text(encoding="utf-8")
        stats = validate_ass(text, path=str(args.path))
    except AssValidationError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(f"ok: {args.path}")
    print(f"dialogues: {stats['dialogues']}, k_tags: {stats['k_tags']}")
    print("validate_ass OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
