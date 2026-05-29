#!/usr/bin/env python3
"""Phase 8 Step 7 — docs + regression sign-off gate.

Runs all Phase 8 step smokes (1–6), local build checks, accessibility token
presence, and ``smoke_phase7_step8.py --verify-only`` (live Vercel + Modal).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
SCRIPTS = REPO_ROOT / "scripts"


def _run(name: str, *extra: str) -> None:
    script = SCRIPTS / name
    if not script.is_file():
        raise SystemExit(f"missing script: {script}")
    cmd = [sys.executable, str(script), *extra]
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, check=False, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _check_docs() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    phase8 = (REPO_ROOT / "docs" / "PHASE_8.md").read_text(encoding="utf-8")
    plan = (REPO_ROOT / "docs" / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")

    for needle in ("PHASE_8.md", "Phase 8", "smoke_phase8_step7"):
        if needle not in readme:
            raise SystemExit(f"README.md missing Phase 8 reference: {needle!r}")

    if "Step 7" not in phase8 or "smoke_phase8_step7" not in phase8:
        raise SystemExit("docs/PHASE_8.md must document Step 7 sign-off")

    if "Phase 8 — Frontend polish" not in plan:
        raise SystemExit("IMPLEMENTATION_PLAN.md must reference Phase 8")

    print("  docs:     README + PHASE_8 + IMPLEMENTATION_PLAN OK")


def _check_a11y_tokens() -> None:
    css = (FRONTEND / "src" / "index.css").read_text(encoding="utf-8")
    for needle in ("prefers-reduced-motion", "--color-muted-foreground"):
        if needle not in css:
            raise SystemExit(f"index.css missing accessibility token: {needle!r}")

    button = (FRONTEND / "src" / "components" / "ui" / "button.tsx").read_text(
        encoding="utf-8"
    )
    upload = (FRONTEND / "src" / "components" / "UploadForm.tsx").read_text(
        encoding="utf-8"
    )
    if "focus-visible" not in button:
        raise SystemExit("button.tsx missing focus-visible ring styles")
    if "aria-label" not in upload:
        raise SystemExit("UploadForm missing aria-label on dropzone")

    print("  a11y:     reduced-motion + focus rings present (manual Lighthouse optional)")


def main() -> int:
    print("=== Phase 8 Step 7 sign-off ===\n")

    print("[1/3] Phase 8 step smokes (1–6) …")
    for i in range(1, 7):
        _run(f"smoke_phase8_step{i}.py")

    print("\n[2/3] Docs + accessibility tokens …")
    _check_docs()
    _check_a11y_tokens()

    print("\n[3/3] Phase 7 production verify (API wiring unchanged) …")
    _run("smoke_phase7_step8.py", "--verify-only")

    print("\nPhase 8 Step 7 OK")
    print(
        "Manual: open https://automatic-karaoke.vercel.app — upload → done → MP4; "
        "optional Lighthouse accessibility pass."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
