#!/usr/bin/env python3
"""Phase 8 Step 4 — progress tracker (stepper + bar + failed alert) gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"


def main() -> int:
    tracker = (FRONTEND / "src" / "components" / "ProgressTracker.tsx").read_text(
        encoding="utf-8"
    )
    app_css = (FRONTEND / "src" / "App.css").read_text(encoding="utf-8")
    app_tsx = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")

    for needle in (
        "@/components/ui/progress",
        "@/components/ui/alert",
        "AlertTitle",
        "Processing failed",
        "Process another song",
        "separating",
        "lucide-react",
    ):
        if needle not in tracker:
            raise SystemExit(f"ProgressTracker missing Step 4 content: {needle!r}")

    if ".progress-tracker" in app_css:
        raise SystemExit("remove legacy .progress-tracker rules from App.css")

    if "text-muted-foreground" not in app_tsx or "text-muted sm:" in app_tsx:
        raise SystemExit("App hero/footer must use text-muted-foreground, not text-muted")

    print("[1/1] npm run build …")
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("\nPhase 8 Step 4 OK")
    print("Manual: mock mode (VITE_USE_MOCK=true) — upload and watch stepper advance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
