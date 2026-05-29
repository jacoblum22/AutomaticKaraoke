#!/usr/bin/env python3
"""Phase 8 Step 2 — shadcn/ui component library gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
UI = FRONTEND / "src" / "components" / "ui"


def main() -> int:
    if not (FRONTEND / "components.json").is_file():
        raise SystemExit("missing frontend/components.json")

    pkg = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for name in ("@base-ui/react", "class-variance-authority"):
        if name not in deps:
            raise SystemExit(f"missing dependency: {name}")

    for component in ("button.tsx", "card.tsx", "progress.tsx", "alert.tsx", "badge.tsx"):
        if not (UI / component).is_file():
            raise SystemExit(f"missing src/components/ui/{component}")

    upload = (FRONTEND / "src" / "components" / "UploadForm.tsx").read_text(
        encoding="utf-8"
    )
    app_tsx = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    if '@/components/ui/button"' not in upload:
        raise SystemExit("UploadForm must import shadcn Button")
    if '@/components/ui/card"' not in app_tsx:
        raise SystemExit("App must import shadcn Card")

    if (FRONTEND / "@").exists():
        raise SystemExit(
            "remove stray frontend/@ folder — components belong in src/components/ui"
        )

    print("[1/1] npm run build …")
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("\nPhase 8 Step 2 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
