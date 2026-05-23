"""Phase 5 Step 1 gate — ffmpeg + ffprobe on PATH."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Optional: warn if Phase 5 inputs missing (not required for Step 1 gate)
LYRICS_CANDIDATES = (
    REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json",
    REPO_ROOT / "scripts" / "output" / "lyrics.json",
)
INSTRUMENTAL_CANDIDATES = (
    REPO_ROOT / "scripts" / "output" / "psychosomatic" / "instrumental.wav",
    REPO_ROOT / "scripts" / "output" / "instrumental.wav",
)


def _find_first(paths: tuple[Path, ...]) -> Path | None:
    for path in paths:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _parse_major_version(version_output: str) -> int | None:
    # ffmpeg version 6.1.1 ... / ffprobe version 6.1.1 ...
    match = re.search(r"version\s+(\d+)", version_output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def check_tool(name: str) -> tuple[bool, str, int | None]:
    exe = shutil.which(name)
    if exe is None:
        return False, "", None
    try:
        proc = subprocess.run(
            [exe, "-version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError as e:
        return False, str(e), None
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, out.strip() or f"exit {proc.returncode}", None
    major = _parse_major_version(out)
    first_line = out.strip().splitlines()[0] if out.strip() else name
    return True, first_line, major


def main() -> int:
    print("Phase 5 Step 1 — FFmpeg toolchain")

    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        found, line, major = check_tool(tool)
        if not found:
            print(f"FAIL: {tool} not found on PATH", file=sys.stderr)
            ok = False
            continue
        print(f"{tool}: ok — {line}")
        if major is not None and major < 4:
            print(f"WARN: {tool} major version {major} (< 4 recommended)", file=sys.stderr)

    if not ok:
        print(file=sys.stderr)
        print("Install FFmpeg:", file=sys.stderr)
        print("  Windows: winget install Gyan.FFmpeg  (or add ffmpeg/bin to PATH)", file=sys.stderr)
        print("  macOS:   brew install ffmpeg", file=sys.stderr)
        print("  Linux:   apt install ffmpeg", file=sys.stderr)
        return 1

    lyrics = _find_first(LYRICS_CANDIDATES)
    instrumental = _find_first(INSTRUMENTAL_CANDIDATES)
    if lyrics and instrumental:
        print(f"render inputs (ready for Step 3+): {instrumental.name} + {lyrics.name}")
    else:
        print("note: run Phase 3–4 first for instrumental.wav + lyrics.json")

    print("Phase 5 Step 1 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
