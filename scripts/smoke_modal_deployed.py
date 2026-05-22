#!/usr/bin/env python3
"""Phase 2 Step 4 — smoke test against deployed Modal API (no modal serve)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Stable production URL from `modal deploy` (label: karaoke-api)
DEPLOYED_API_URL = "https://jacoblum22--karaoke-api.modal.run"

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.environ["MODAL_API_URL"] = DEPLOYED_API_URL
    script = REPO_ROOT / "scripts" / "smoke_modal_api.py"
    print(f"Deployed API: {DEPLOYED_API_URL}\n")
    raise SystemExit(
        subprocess.call([sys.executable, str(script)], cwd=REPO_ROOT)
    )


if __name__ == "__main__":
    main()
