#!/usr/bin/env python3
"""Phase 2 Step 1 gate — job store via modal.Dict (two modal run invocations)."""

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


def run_modal(target: str, *extra: str, parse_job_id: bool = False) -> str | None:
    cmd = [*_modal_cmd(), "run", target, *extra]
    print("+", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=BACKEND,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    if not parse_job_id:
        return None
    for line in result.stdout.splitlines():
        if line.strip().startswith("JOB_ID="):
            return line.strip().split("=", 1)[1]
    raise SystemExit(f"could not parse JOB_ID= from modal output:\n{result.stdout[-500:]}")


def main() -> None:
    print("smoke_jobs_write …")
    job_id = run_modal("app.py::smoke_jobs_write", parse_job_id=True)
    if not job_id or len(job_id) < 32:
        print(f"unexpected job_id from write: {job_id!r}", file=sys.stderr)
        raise SystemExit(1)
    print(f"job_id: {job_id}")

    print("smoke_jobs_read (new container) …")
    run_modal("app.py::smoke_jobs_read", "--job-id", job_id)

    print("smoke_jobs_failed …")
    run_modal("app.py::smoke_jobs_failed")

    print("jobs Dict OK")


if __name__ == "__main__":
    main()
