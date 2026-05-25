#!/usr/bin/env python3
"""Phase 2 Step 4 — smoke test against deployed Modal API (no modal serve).

Runs Phase 6 E2E pipeline smoke (real R2 video_url), not the Phase 2 stub check.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    script = REPO_ROOT / "scripts" / "smoke_pipeline_modal.py"
    raise SystemExit(subprocess.call([sys.executable, str(script)], cwd=REPO_ROOT))


if __name__ == "__main__":
    main()
