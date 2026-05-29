#!/usr/bin/env python3
"""Phase 8 Step 3 — upload zone + primary CTA polish gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"


def main() -> int:
    upload = (FRONTEND / "src" / "components" / "UploadForm.tsx").read_text(
        encoding="utf-8"
    )
    app_css = (FRONTEND / "src" / "App.css").read_text(encoding="utf-8")

    pkg = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    if "lucide-react" not in pkg.get("dependencies", {}):
        raise SystemExit("missing dependency: lucide-react")

    for needle in (
        "lucide-react",
        "Loader2",
        "Upload",
        "aria-label=\"Remove file\"",
        "clearSelection",
        "@/components/ui/progress",
    ):
        if needle not in upload:
            raise SystemExit(f"UploadForm missing expected Step 3 content: {needle!r}")

    if ".dropzone" in app_css:
        raise SystemExit("remove legacy .dropzone rules from App.css (Step 3 uses Tailwind)")

    tsconfig_text = (FRONTEND / "tsconfig.app.json").read_text(encoding="utf-8")
    if '"baseUrl"' in tsconfig_text:
        raise SystemExit(
            "tsconfig.app.json: remove deprecated baseUrl (use paths with ./src/* prefix only)"
        )
    if '"ignoreDeprecations"' in tsconfig_text:
        raise SystemExit("tsconfig.app.json: remove ignoreDeprecations (fix baseUrl instead)")
    if '"@/*"' not in tsconfig_text:
        raise SystemExit("tsconfig.app.json must define @/* path alias")

    print("[1/1] npm run build …")
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("\nPhase 8 Step 3 OK")
    print("Manual: select file, remove chip, upload → Create karaoke (Modal or mock).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
