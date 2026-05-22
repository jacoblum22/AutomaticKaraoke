#!/usr/bin/env python3
"""Phase 2 Step 2 gate — stub orchestrator via spawn + Dict polling."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
REPO_ROOT = BACKEND.parent


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def run_modal(target: str) -> None:
    cmd = [*_modal_cmd(), "run", target]
    print("+", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=BACKEND,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(result.returncode)


def main() -> None:
    print("smoke_orchestrator_happy (spawn + poll) …")
    run_modal("app.py::smoke_orchestrator_happy")

    print("smoke_orchestrator_fail …")
    run_modal("app.py::smoke_orchestrator_fail")

    print("stub orchestrator OK")


if __name__ == "__main__":
    main()
