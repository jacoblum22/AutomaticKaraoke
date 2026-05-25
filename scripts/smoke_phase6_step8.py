#!/usr/bin/env python3
"""Phase 6 Step 8 — production frontend sign-off.

``--verify-only`` checks the live Vercel bundle points at Modal (fast).
``--full`` also runs ``npm run smoke:modal`` (client.ts E2E, ~10–25 min).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
PRODUCTION = "https://automatic-karaoke.vercel.app"
MODAL_API = "https://jacoblum22--karaoke-api.modal.run"


def _fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "AutomaticKaraoke-smoke/1.0"})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def verify_production_bundle() -> None:
    print(f"Checking {PRODUCTION} …")
    html = _fetch(PRODUCTION)
    match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
    if not match:
        raise SystemExit("Could not find main JS bundle in production HTML")
    js_url = PRODUCTION + match.group(1)
    print(f"  bundle:   {js_url}")
    try:
        js = _fetch(js_url)
    except HTTPError as exc:
        raise SystemExit(f"Failed to fetch bundle: HTTP {exc.code}") from exc

    if MODAL_API not in js and "jacoblum22--karaoke-api.modal.run" not in js:
        raise SystemExit(f"Production bundle missing Modal API ({MODAL_API})")

    if "stub API" in js or "Modal stub" in js:
        print(
            "  note:     bundle still shows old stub subtitle — redeploy frontend "
            "(git push main or vercel --prod) after App.tsx update"
        )
    else:
        print("  subtitle: OK (no stub API copy in bundle)")

    if "mockCreateJob" in js:
        raise SystemExit("Production bundle appears to include mock job API")

    print("  API:      Modal (mock off in bundle)")


def run_client_smoke() -> None:
    print("\nRunning frontend npm run smoke:modal …")
    proc = subprocess.run(
        ["npm", "run", "smoke:modal"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 Step 8 production sign-off")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only check live Vercel bundle (no upload)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Verify bundle + run client.ts E2E against Modal API",
    )
    args = parser.parse_args()

    verify_production_bundle()

    if args.full:
        run_client_smoke()
    elif not args.verify_only:
        print(
            "\nManual gate: open https://automatic-karaoke.vercel.app, upload a song, "
            "wait for done, confirm the video plays."
        )
        print("Automated E2E: re-run with --full (long) or npm run smoke:modal in frontend/")

    print("\nPhase 6 Step 8 verify OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
