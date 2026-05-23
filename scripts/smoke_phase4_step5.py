"""Phase 4 Step 5 — full-song lyrics on Psychosomatic vocal stem (Modal GPU).

Writes scripts/output/psychosomatic/lyrics.json and validates contract.
Uses deployed smoke_whisper_fixture(clip_end=None) — redeploy if function signature changed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
VOCAL = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "vocals.wav"
OUTPUT = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json"
MODAL_APP = "karaoke"
SMOKE_FN = "smoke_whisper_fixture"


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_modal_full_song(*, model_size: str = "medium") -> dict:
    import modal

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from validate_lyrics_json import validate_lyrics  # noqa: E402

    print(
        f"Modal: {MODAL_APP}::{SMOKE_FN}(clip_end=None, model_size={model_size!r}) "
        "— full bundled vocal stem"
    )
    fn = modal.Function.from_name(MODAL_APP, SMOKE_FN)
    result = fn.remote(clip_end=None, model_size=model_size)
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected return: {type(result)}")

    lyrics = result.get("lyrics")
    if not isinstance(lyrics, dict):
        raise RuntimeError(f"missing lyrics in result: {list(result.keys())}")

    validate_lyrics(lyrics, path=str(OUTPUT))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(lyrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    segments = lyrics["segments"]
    last_end = max(s["end"] for s in segments)
    word_count = sum(len(s["words"]) for s in segments)
    print(f"written:  {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    print(f"elapsed:  {result.get('elapsed_s'):.1f}s (Modal GPU)")
    print(f"segments: {len(segments)}, words: {word_count}, span_end: {last_end:.1f}s")
    return result


def run_local_full_song(*, model_size: str = "medium") -> int:
    py = sys.executable
    test = REPO_ROOT / "scripts" / "test_whisper_local.py"
    validate = REPO_ROOT / "scripts" / "validate_lyrics_json.py"
    proc = subprocess.run(
        [
            py,
            str(test),
            "--input",
            str(VOCAL),
            "--output",
            str(OUTPUT),
            "--no-clip",
            "--model",
            model_size,
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if proc.returncode != 0:
        return proc.returncode
    proc = subprocess.run([py, str(validate), str(OUTPUT)], cwd=REPO_ROOT, check=False)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 Step 5 full-song lyrics")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run locally on CPU (slow; default is Modal GPU)",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="modal deploy before GPU run",
    )
    parser.add_argument(
        "--model",
        default="medium",
        help="faster-whisper model size (e.g. large-v3)",
    )
    args = parser.parse_args()

    if not VOCAL.is_file():
        print(f"FAIL: {VOCAL} missing", file=sys.stderr)
        print("Run: python scripts/smoke_phase3_step7.py", file=sys.stderr)
        return 1

    if args.deploy:
        run_deploy()

    if args.local:
        print(f"=== local full song (CPU, model={args.model}) ===")
        code = run_local_full_song(model_size=args.model)
        if code != 0:
            return code
    else:
        print(f"=== Modal GPU full song (model={args.model}) ===")
        run_modal_full_song(model_size=args.model)

    print("Phase 4 Step 5 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
