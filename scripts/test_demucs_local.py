"""Demucs isolation test — Phase 3 local CLI.

Default: scripts/fixtures/sample_30s.mp3 → scripts/output/vocals.wav + instrumental.wav

Typical runtime (30s clip): ~1–5 min CPU, faster on CUDA. First run downloads htdemucs weights.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from separate import SeparationError, separate_audio  # noqa: E402

DEFAULT_FIXTURES = (
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3",
    REPO_ROOT / "scripts" / "fixtures" / "sample_30s.wav",
)
DEFAULT_OUTPUT = REPO_ROOT / "scripts" / "output"


def default_input() -> Path:
    for path in DEFAULT_FIXTURES:
        if path.is_file():
            return path
    return DEFAULT_FIXTURES[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Separate vocals from mixed audio (Phase 3 local)"
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=None,
        help="Input audio path (default: fixtures/sample_30s.mp3 or .wav)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for vocals.wav and instrumental.wav",
    )
    parser.add_argument(
        "--device",
        "-d",
        default=None,
        help="torch device (default: cuda if available else cpu)",
    )
    parser.add_argument(
        "--shifts",
        type=int,
        default=1,
        help="Demucs random shifts (higher = slower, sometimes better quality)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable Demucs progress bar",
    )
    parser.add_argument(
        "--save-fixture",
        action="store_true",
        help="After separation, copy vocals.wav → fixtures/vocals_30s.wav (Phase 4)",
    )
    args = parser.parse_args()

    input_path = args.input or default_input()
    if not input_path.is_file():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        print("Run: python scripts/generate_sample_fixture.py", file=sys.stderr)
        return 1

    print(f"input:  {input_path} ({input_path.stat().st_size} bytes)")
    print(f"output: {args.output}")
    print(f"device: {args.device or 'auto'}")

    t0 = time.perf_counter()
    try:
        vocals_path, instrumental_path = separate_audio(
            input_path,
            args.output,
            device=args.device,
            shifts=args.shifts,
            progress=not args.quiet,
        )
    except SeparationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - t0
    print(f"vocals:        {vocals_path} ({vocals_path.stat().st_size} bytes)")
    print(f"instrumental:  {instrumental_path} ({instrumental_path.stat().st_size} bytes)")
    print(f"done in {elapsed:.1f}s")

    if args.save_fixture:
        script = REPO_ROOT / "scripts" / "save_vocal_fixture.py"
        proc = subprocess.run([sys.executable, str(script)], check=False)
        if proc.returncode != 0:
            return proc.returncode

    print("Phase 3 local Demucs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
