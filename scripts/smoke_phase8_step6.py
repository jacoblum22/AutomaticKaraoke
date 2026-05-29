#!/usr/bin/env python3
"""Phase 8 Step 6 — dev debug footer + optional metadata + config alert gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
SRC = FRONTEND / "src"


def main() -> int:
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    debug = (SRC / "components" / "DevDebugFooter.tsx").read_text(encoding="utf-8")
    meta = (SRC / "components" / "SongMetadataFields.tsx").read_text(encoding="utf-8")
    tracker = (SRC / "components" / "ProgressTracker.tsx").read_text(encoding="utf-8")

    for needle in ("DevDebugFooter", "SongMetadataFields", "AlertTitle", "API key required"):
        if needle not in app:
            raise SystemExit(f"App.tsx missing Step 6 content: {needle!r}")

    if "<details" not in debug or "import.meta.env.DEV" not in debug:
        raise SystemExit("DevDebugFooter must use collapsible details in DEV only")

    if "configured" not in debug or "missing" not in debug:
        raise SystemExit('DevDebugFooter must show "configured"/"missing", not the raw key')

    if "VITE_API_KEY" in debug:
        raise SystemExit("DevDebugFooter must not reference VITE_API_KEY string")

    if "Song title" not in meta or "Artist" not in meta:
        raise SystemExit("SongMetadataFields must include title and artist inputs")

    if 'status === "done"' not in tracker or "STEPS.length" not in tracker:
        raise SystemExit("ProgressTracker must treat done as all steps complete")

    print("[1/1] npm run build …")
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    # Footer must not echo the key in UI copy (key may still be baked for X-API-Key headers).
    if "test-karaoke" in debug.lower():
        raise SystemExit("DevDebugFooter must not hardcode API key values")

    print("\nPhase 8 Step 6 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
