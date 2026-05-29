#!/usr/bin/env python3
"""Phase 8 Step 5 — video result card + empty state gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"


def main() -> int:
    player = (FRONTEND / "src" / "components" / "VideoPlayer.tsx").read_text(
        encoding="utf-8"
    )
    app_css = (FRONTEND / "src" / "App.css").read_text(encoding="utf-8")
    app_tsx = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")

    for needle in (
        "@/components/ui/card",
        "Clapperboard",
        "Download MP4",
        "Open in new tab",
        'rel="noopener noreferrer"',
        "controls",
        "processing",
    ):
        if needle not in player:
            raise SystemExit(f"VideoPlayer missing Step 5 content: {needle!r}")

    if ".video-player" in app_css:
        raise SystemExit("remove legacy .video-player rules from App.css")

    if "processing={processing && !videoUrl}" not in app_tsx:
        raise SystemExit("App must pass processing prop to VideoPlayer")

    print("[1/1] npm run build …")
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("\nPhase 8 Step 5 OK")
    print("Manual: complete a job — video plays inline; try Download / Open in new tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
