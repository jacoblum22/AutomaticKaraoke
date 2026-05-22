#!/usr/bin/env python3
"""Phase 3 Step 7 — Demucs on a full song; validate outputs (duration, size).

Ear-test gates (intelligible vocals, usable instrumental) remain manual.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3"
OUTPUT_DIR = REPO_ROOT / "scripts" / "output" / "psychosomatic"
VOCALS = OUTPUT_DIR / "vocals.wav"
INSTRUMENTAL = OUTPUT_DIR / "instrumental.wav"
MAX_DURATION_DELTA_S = 3.0
MODAL_APP = "karaoke"
MODAL_FN_SONG = "smoke_demucs_psychosomatic"


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def run_modal_song() -> None:
    import modal

    print(f"Modal GPU: {MODAL_APP}.{MODAL_FN_SONG} (~1–3 min on T4)…")
    fn = modal.Function.from_name(MODAL_APP, MODAL_FN_SONG)
    result = fn.remote()
    print(f"ELAPSED_S={result.get('elapsed_s')}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3 Step 7 quality smoke")
    parser.add_argument(
        "--modal",
        action="store_true",
        help="Also run smoke_demucs_psychosomatic on deployed Modal (requires deploy)",
    )
    parser.add_argument(
        "--modal-only",
        action="store_true",
        help="Skip local CPU run; Modal GPU only",
    )
    args = parser.parse_args()

    if args.modal_only:
        run_modal_song()
        print("Phase 3 Step 7 Modal OK")
        return 0
    if not FIXTURE.is_file():
        print("FAIL: missing scripts/fixtures/Psychosomatic.mp3", file=sys.stderr)
        print("Run: python scripts/copy_psychosomatic_fixture.py", file=sys.stderr)
        return 1

    if not args.modal_only:
        py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
        if not py.is_file():
            py = Path(sys.executable)

        test_script = REPO_ROOT / "scripts" / "test_demucs_local.py"
        print(f"Running Demucs on {FIXTURE.name} (CPU; ~5–15 min for 3 min song)…")
        proc = subprocess.run(
            [
                str(py),
                str(test_script),
                str(FIXTURE),
                "--output",
                str(OUTPUT_DIR),
                "--quiet",
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        if proc.returncode != 0:
            print("FAIL: test_demucs_local.py exited", proc.returncode, file=sys.stderr)
            return proc.returncode

        for label, path in ("vocals", VOCALS), ("instrumental", INSTRUMENTAL):
            if not path.is_file() or path.stat().st_size == 0:
                print(f"FAIL: missing {label}: {path}", file=sys.stderr)
                return 1

        v_dur = _wav_duration(VOCALS)
        i_dur = _wav_duration(INSTRUMENTAL)
        delta = abs(v_dur - i_dur)

        print(f"vocals:       {VOCALS} ({v_dur:.1f}s, {VOCALS.stat().st_size // 1024} KB)")
        print(f"instrumental: {INSTRUMENTAL} ({i_dur:.1f}s, {INSTRUMENTAL.stat().st_size // 1024} KB)")

        if delta > MAX_DURATION_DELTA_S:
            print(
                f"FAIL: stem duration mismatch {delta:.1f}s > {MAX_DURATION_DELTA_S}s",
                file=sys.stderr,
            )
            return 1

        if v_dur < 60:
            print(f"WARN: vocals duration only {v_dur:.1f}s — expected ~3 min song", file=sys.stderr)

        print()
        print("Listen (Step 7 manual gate):")
        print(f"  Original:  {FIXTURE}")
        print(f"  Vocals:    {VOCALS}")
        print(f"  Inst:      {INSTRUMENTAL}")

    if args.modal or args.modal_only:
        run_modal_song()

    print("Phase 3 Step 7 automated checks OK — confirm quality by ear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
