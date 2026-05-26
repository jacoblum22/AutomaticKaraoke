"""Quiet ``modal run`` helpers for smoke scripts (capture + filter CLI noise)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
# Lines from Modal smoke functions we want to show (not mount/function trees).
_SMOKE_MARKERS = (
    "RATE_LIMIT_",
    "API_KEY_",
    "JOB_ID=",
    "EXPIRED_JOB_ID=",
    "FRESH_JOB_ID=",
    "CLEANUP_SUMMARY=",
    "R2_",
    "_OK",
    "count=",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def backend_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "backend"


def modal_cmd(root: Path | None = None) -> list[str]:
    base = root or repo_root()
    venv_modal = base / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def utf8_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def modal_output_text(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "") + (proc.stderr or "")


def is_modal_smoke_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("{") and "}" in s:
        return True
    return any(marker in s for marker in _SMOKE_MARKERS)


def print_modal_output(proc: subprocess.CompletedProcess[str]) -> None:
    """Print smoke result lines only; full log on failure or SMOKE_MODAL_VERBOSE=1."""
    text = modal_output_text(proc)
    if os.environ.get("SMOKE_MODAL_VERBOSE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        if text.strip():
            print(text.rstrip())
        return

    for line in text.splitlines():
        if is_modal_smoke_line(line):
            print(line)


def run_modal(
    target: str,
    *extra: str,
    cwd: Path | None = None,
    root: Path | None = None,
    echo_cmd: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``modal run`` with captured output; hide mount/function tree spam."""
    base = root or repo_root()
    run_cwd = cwd or backend_dir(base)
    cmd = [*modal_cmd(base), "run", target, *extra]
    if echo_cmd:
        print("+", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=run_cwd,
        check=False,
        env=utf8_env(),
        capture_output=True,
        text=True,
    )
    print_modal_output(proc)
    if proc.returncode != 0:
        print("--- modal run failed (full output) ---", file=sys.stderr)
        sys.stderr.write(modal_output_text(proc))
        if not modal_output_text(proc).endswith("\n"):
            sys.stderr.write("\n")
        raise SystemExit(proc.returncode)
    return proc


def run_modal_deploy(root: Path | None = None) -> None:
    base = root or repo_root()
    cmd = [*modal_cmd(base), "deploy", "app.py"]
    print("+", " ".join(cmd))
    proc = subprocess.run(
        cmd, cwd=backend_dir(base), check=False, env=utf8_env()
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
