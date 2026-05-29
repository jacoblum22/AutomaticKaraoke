#!/usr/bin/env python3
"""Phase 8 Step 1 — Tailwind tokens + layout shell gate.

Checks:
  - tailwindcss + @tailwindcss/vite in frontend/package.json
  - src/lib/utils.ts (cn helper)
  - npm run build succeeds
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"


def main() -> int:
    pkg_path = FRONTEND / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    for name in ("tailwindcss", "@tailwindcss/vite", "clsx", "tailwind-merge"):
        if name not in deps:
            raise SystemExit(f"missing dependency: {name}")

    utils = FRONTEND / "src" / "lib" / "utils.ts"
    if not utils.is_file():
        raise SystemExit("missing frontend/src/lib/utils.ts")

    vite_cfg = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")
    if "@tailwindcss/vite" not in vite_cfg:
        raise SystemExit("vite.config.ts missing @tailwindcss/vite plugin")

    index_css = (FRONTEND / "src" / "index.css").read_text(encoding="utf-8")
    if '@import "tailwindcss"' not in index_css:
        raise SystemExit('index.css missing @import "tailwindcss"')

    app_tsx = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    for needle in ("font-display", "max-w-lg", "rounded-2xl"):
        if needle not in app_tsx:
            raise SystemExit(f"App.tsx layout shell missing: {needle}")

    print("[1/1] npm run build …")
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        check=False,
        shell=sys.platform == "win32",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print("\nPhase 8 Step 1 OK")
    print("Manual: npm run dev — check layout at 375px and 1280px width.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
