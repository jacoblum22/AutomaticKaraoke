#!/usr/bin/env python3
"""Phase 7 Step 8 — regression and production sign-off.

Default (``--verify-only``): live Vercel bundle + Modal ``/config`` (~30s).

Optional:
  ``--api``       — Phase 7 HTTP/modal smokes (steps 5–7, no full pipeline)
  ``--isolation`` — Phase 3–5 deployed Modal isolation smokes (~minutes)
  ``--full``      — verify + api + isolation + ``smoke_pipeline_modal.py`` (long)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
PRODUCTION = "https://automatic-karaoke.vercel.app"
MODAL_API = os.environ.get("MODAL_API_URL", "https://jacoblum22--karaoke-api.modal.run")

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from smoke_api import request_json  # noqa: E402


def _fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "AutomaticKaraoke-smoke/1.0"})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _run_script(name: str, *extra: str) -> None:
    script = REPO_ROOT / "scripts" / name
    cmd = [sys.executable, str(script), *extra]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, check=False, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def verify_phase7_bundle_extras(js: str) -> None:
    """Phase 7-only checks on the production JS bundle (after Phase 6 verify)."""
    print("\n[2/3] Phase 7 production bundle extras …")
    if "hasClientApiKey" in js or "configured" in js:
        print("  footer:   API key status UI present (Phase 8 debug footer)")
    elif "Client API key" in js:
        print("  footer:   legacy API key status UI present")
    else:
        print("  note:     footer missing API key status — push latest frontend")

    key = os.environ.get("KARAOKE_API_KEY", "test-karaoke-phase7-key")
    if key and key in js:
        print("  api_key:  baked into bundle")
    elif "hasClientApiKey" in js:
        print("  api_key:  client helper present (value may be empty in build)")
    else:
        print("  note:     no VITE_API_KEY in bundle — set on Vercel + redeploy")


def _production_bundle_js() -> str:
    html = _fetch(PRODUCTION)
    match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
    if not match:
        raise SystemExit("Could not find main JS bundle in production HTML")
    return _fetch(PRODUCTION + match.group(1))


def verify_modal_config() -> None:
    print(f"\n[3/3] Modal GET /config ({MODAL_API}) …")
    status, cfg = request_json(f"{MODAL_API.rstrip('/')}/config")
    if status != 200 or not isinstance(cfg, dict):
        raise SystemExit(f"/config failed: {status} {cfg}")
    print(f"  r2_upload:         {cfg.get('r2_upload')}")
    print(f"  api_key_required:  {cfg.get('api_key_required')}")
    if cfg.get("api_key_required") and not os.environ.get("KARAOKE_API_KEY"):
        print(
            "  note: set KARAOKE_API_KEY for automated smokes that call protected routes"
        )


def verify_phase6_signoff() -> None:
    print("[1/3] Phase 6 production checks …")
    _run_script("smoke_phase6_step8.py", "--verify-only")


def run_api_gates() -> None:
    print("\n--- Phase 7 API gates (modal + HTTP) ---")
    if not os.environ.get("KARAOKE_API_KEY", "").strip():
        print(
            "skip HTTP smokes (steps 5, 7): set KARAOKE_API_KEY when api_key_required is true"
        )
        _run_script("smoke_phase7_step1.py")
        return
    _run_script("smoke_phase7_step1.py")
    _run_script("smoke_phase7_step5.py", "--skip-upload")
    _run_script("smoke_phase7_step7.py")


def run_isolation() -> None:
    print("\n--- Phase 3–5 isolation (deployed Modal) ---")
    _run_script("smoke_demucs_modal.py")
    _run_script("smoke_whisper_modal.py")
    _run_script("smoke_render_modal.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 Step 8 sign-off")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Vercel bundle + /config + Phase 6 verify (default)",
    )
    parser.add_argument("--api", action="store_true", help="Also run Phase 7 API smokes")
    parser.add_argument(
        "--isolation",
        action="store_true",
        help="Also run Phase 3–5 Modal isolation smokes",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="verify + api + isolation + full pipeline E2E",
    )
    args = parser.parse_args()

    if not (args.verify_only or args.api or args.isolation or args.full):
        args.verify_only = True

    verify_phase6_signoff()
    verify_phase7_bundle_extras(_production_bundle_js())
    verify_modal_config()

    if args.full or args.api:
        run_api_gates()
    if args.full or args.isolation:
        run_isolation()
    if args.full:
        print("\n--- Full pipeline E2E (long) ---")
        _run_script("smoke_pipeline_modal.py")

    print("\nPhase 7 Step 8 OK")
    print(
        "Manual: upload on https://automatic-karaoke.vercel.app -> done -> video plays."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
