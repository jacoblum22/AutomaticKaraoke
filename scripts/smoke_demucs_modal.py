#!/usr/bin/env python3
"""Phase 3 Step 6 — smoke Demucs on deployed Modal app `karaoke`.

Default: invoke deployed ``smoke_demucs_separate`` via ``Function.from_name``.
Use ``--local-run`` for ephemeral ``modal run`` (Step 5).
Use ``--deploy`` to run ``modal deploy app.py`` first.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
FIXTURE = REPO_ROOT / "scripts" / "fixtures" / "sample_30s.mp3"
MODAL_APP = "karaoke"
SMOKE_FN = "smoke_demucs_separate"


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


def run_local_smoke() -> None:
    cmd = [*_modal_cmd(), "run", f"app.py::{SMOKE_FN}"]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=BACKEND, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def run_deployed_smoke() -> dict:
    import modal

    print(f"Deployed app: {MODAL_APP}  function: {SMOKE_FN}")
    fn = modal.Function.from_name(MODAL_APP, SMOKE_FN)
    result = fn.remote()
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected return type: {type(result)}")
    vocals = result.get("vocals")
    instrumental = result.get("instrumental")
    elapsed = result.get("elapsed_s")
    if not vocals or not instrumental:
        raise RuntimeError(f"missing paths in result: {result}")
    print(f"VOCALS_PATH={vocals}")
    print(f"INSTRUMENTAL_PATH={instrumental}")
    print(f"ELAPSED_S={elapsed}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 Modal Demucs smoke")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Run modal deploy app.py before smoke",
    )
    parser.add_argument(
        "--local-run",
        action="store_true",
        help="Use modal run (ephemeral) instead of deployed function",
    )
    args = parser.parse_args()

    if not FIXTURE.is_file():
        print("FAIL: scripts/fixtures/sample_30s.mp3 missing", file=sys.stderr)
        print("Run: python scripts/generate_sample_fixture.py", file=sys.stderr)
        return 1

    if args.deploy:
        run_deploy()

    if args.local_run:
        run_local_smoke()
    else:
        run_deployed_smoke()

    print("Phase 3 Modal Demucs smoke OK (deployed)" if not args.local_run else "Phase 3 Modal Demucs smoke OK (local run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
