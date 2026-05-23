#!/usr/bin/env python3
"""Phase 5 Step 7 — smoke render on deployed Modal app ``karaoke``.

Default: ``Function.from_name("karaoke", "smoke_render_fixture").remote()``.
Use ``--local-run`` for ephemeral ``modal run`` (Step 6).
Use ``--deploy`` to run ``modal deploy app.py`` first.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
INSTRUMENTAL = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "instrumental.wav"
LYRICS = REPO_ROOT / "scripts" / "output" / "psychosomatic" / "lyrics.json"
MODAL_APP = "karaoke"
SMOKE_FN = "smoke_render_fixture"
MAX_ELAPSED_30S = 90.0


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run_deploy() -> None:
    cmd = [*_modal_cmd(), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_local_smoke(*, full: bool) -> None:
    step6 = REPO_ROOT / "scripts" / "smoke_phase5_step6.py"
    cmd = [sys.executable, str(step6)]
    if full:
        cmd.append("--full")
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False, env=_utf8_env())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_deployed_smoke(*, clip_end: float | None = 30.0) -> dict:
    import modal

    print(f"Deployed app: {MODAL_APP}  function: {SMOKE_FN}  clip_end={clip_end!r}")
    fn = modal.Function.from_name(MODAL_APP, SMOKE_FN)
    result = fn.remote(clip_end=clip_end)
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected return type: {type(result)}")

    mp4_path = result.get("mp4_path")
    size_bytes = result.get("size_bytes")
    elapsed = result.get("elapsed_s")
    if not mp4_path:
        raise RuntimeError(f"missing mp4_path in result: {list(result.keys())}")
    if not size_bytes or int(size_bytes) <= 0:
        raise RuntimeError(f"invalid size_bytes: {size_bytes!r}")
    if elapsed is None:
        raise RuntimeError("missing elapsed_s in result")

    print(f"MP4_PATH={mp4_path}")
    print(f"SIZE_BYTES={size_bytes}")
    print(f"ELAPSED_S={elapsed:.1f}")
    if clip_end == 30.0 and float(elapsed) > MAX_ELAPSED_30S:
        print(
            f"WARN: elapsed {elapsed:.1f}s > {MAX_ELAPSED_30S:.0f}s (30s clip)",
            file=sys.stderr,
        )
    return result


def run_api_regression() -> None:
    """Phase 2 stub API still healthy after deploy."""
    api_smoke = REPO_ROOT / "scripts" / "smoke_modal_deployed.py"
    if not api_smoke.is_file():
        print("skip: smoke_modal_deployed.py not found")
        return
    print("\n=== API regression (stub orchestrator) ===")
    proc = subprocess.run(
        [sys.executable, str(api_smoke)],
        cwd=REPO_ROOT,
        check=False,
        env=_utf8_env(),
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 Modal render smoke (deployed)")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Run modal deploy app.py before smoke",
    )
    parser.add_argument(
        "--local-run",
        action="store_true",
        help="Use modal run (Step 6) instead of deployed function",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full song render (clip_end=None); default is 30s clip",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip smoke_modal_deployed.py after render smoke",
    )
    args = parser.parse_args()

    if not INSTRUMENTAL.is_file() or not LYRICS.is_file():
        print("FAIL: need psychosomatic instrumental + lyrics", file=sys.stderr)
        print("Run Phase 3 Step 7 and Phase 4 Step 5.", file=sys.stderr)
        print("Redeploy after files exist so they bake into _RENDER_IMAGE.", file=sys.stderr)
        return 1

    if args.deploy:
        run_deploy()

    if args.local_run:
        run_local_smoke(full=args.full)
    else:
        clip_end = None if args.full else 30.0
        run_deployed_smoke(clip_end=clip_end)

    if not args.skip_api and not args.local_run:
        run_api_regression()

    label = "local run" if args.local_run else "deployed"
    print(f"Phase 5 Modal render smoke OK ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
