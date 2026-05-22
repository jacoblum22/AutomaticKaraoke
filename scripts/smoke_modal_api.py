#!/usr/bin/env python3
"""Phase 2 Step 3 gate — HTTP start-job + job-status against modal serve or deploy."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BACKEND = Path(__file__).resolve().parent.parent / "backend"
REPO_ROOT = BACKEND.parent

POLL_INTERVAL_S = 2
POLL_TIMEOUT_S = 60
TERMINAL = frozenset({"done", "failed"})
STUB_VIDEO = "https://automatic-karaoke.vercel.app/sample.mp4"


def _configure_stdio_utf8() -> None:
    """Avoid Windows cp1252 errors when Modal prints Unicode (e.g. ✓)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _safe_echo(line: str) -> None:
    try:
        print(line.rstrip())
    except UnicodeEncodeError:
        sys.stdout.buffer.write(line.rstrip().encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")


def _modal_cmd() -> list[str]:
    venv_modal = REPO_ROOT / ".venv" / "Scripts" / "modal.exe"
    if venv_modal.is_file():
        return [str(venv_modal)]
    return [sys.executable, "-m", "modal"]


def _multipart_body(filename: str, data: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = [
        f"--{boundary}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode(),
        data,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def _request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
) -> tuple[int, dict | str]:
    hdrs = dict(headers or {})
    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if raw:
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, raw
            return resp.status, {}
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def _find_serve_url(line: str) -> str | None:
    # modal serve prints https://<workspace>--<label>-dev.modal.run (or similar)
    m = re.search(r"https://[a-zA-Z0-9.-]+\.modal\.run", line)
    return m.group(0).rstrip("/") if m else None


def start_modal_serve() -> tuple[subprocess.Popen[str], str]:
    cmd = [*_modal_cmd(), "serve", "app.py"]
    print("+", " ".join(cmd), "(waiting for URL…)")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.Popen(
        cmd,
        cwd=BACKEND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.stdout is not None
    deadline = time.time() + 180
    base_url: str | None = None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            _safe_echo(line)
            url = _find_serve_url(line)
            if url:
                base_url = url
                break
    if not base_url:
        proc.terminate()
        raise SystemExit("modal serve did not print a .modal.run URL within 180s")
    return proc, base_url


def run_smoke(base_url: str) -> None:
    base = base_url.rstrip("/")
    origin = "http://localhost:5173"

    print("OPTIONS /start-job (CORS preflight) …")
    status, _ = _request(
        "OPTIONS",
        f"{base}/start-job",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    if status not in (200, 204):
        raise SystemExit(f"CORS preflight failed: HTTP {status}")

    print("POST /start-job …")
    body, ctype = _multipart_body("smoke.mp3", b"\x00\x01\x02", "audio/mpeg")
    t0 = time.time()
    status, data = _request(
        "POST",
        f"{base}/start-job",
        body=body,
        headers={"Content-Type": ctype},
        timeout=10,
    )
    elapsed = time.time() - t0
    if status != 200 or not isinstance(data, dict) or "job_id" not in data:
        raise SystemExit(f"start-job failed: HTTP {status} {data!r}")
    if elapsed > 2.0:
        print(f"warning: start-job took {elapsed:.2f}s (gate is <2s)", file=sys.stderr)
    job_id = data["job_id"]
    print(f"job_id: {job_id} ({elapsed:.2f}s)")

    deadline = time.time() + POLL_TIMEOUT_S
    last_status: str | None = None
    while time.time() < deadline:
        q = urlencode({"job_id": job_id})
        status, data = _request("GET", f"{base}/job-status?{q}", timeout=10)
        if status != 200 or not isinstance(data, dict):
            raise SystemExit(f"job-status failed: HTTP {status} {data!r}")
        st = data.get("status")
        if st != last_status:
            print(f"{st} {data.get('progress', 0)} {data.get('message', '')}".strip())
            last_status = st
        if st in TERMINAL:
            if st == "failed":
                raise SystemExit(f"job failed: {data.get('error')}")
            if data.get("video_url") != STUB_VIDEO:
                raise SystemExit(f"unexpected video_url: {data.get('video_url')}")
            print(f"done video_url={data.get('video_url')}")
            print("modal API OK")
            return
        time.sleep(POLL_INTERVAL_S)
    raise SystemExit("poll timed out")


def main() -> None:
    _configure_stdio_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        help="Modal API base (e.g. from modal serve). Overrides MODAL_API_URL.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start modal serve app.py and auto-detect URL (default if no --base-url)",
    )
    args = parser.parse_args()

    base_url = args.base_url or os.environ.get("MODAL_API_URL")
    serve_proc: subprocess.Popen[str] | None = None

    try:
        if not base_url:
            serve_proc, base_url = start_modal_serve()
            time.sleep(2)
        print(f"API base: {base_url}")
        run_smoke(base_url)
    finally:
        if serve_proc and serve_proc.poll() is None:
            serve_proc.terminate()
            try:
                serve_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                serve_proc.kill()


if __name__ == "__main__":
    main()
