"""Copy Psychosomatic.mp3 into scripts/fixtures/ for Phase 3 Step 7 (gitignored)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / "Downloads" / "Psychosomatic.mp3"
DEST = REPO_ROOT / "scripts" / "fixtures" / "Psychosomatic.mp3"


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.is_file():
        print(f"FAIL: not found: {source}", file=sys.stderr)
        print("Usage: python scripts/copy_psychosomatic_fixture.py [path-to.mp3]", file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, DEST)
    mb = DEST.stat().st_size / (1024 * 1024)
    print(f"copied → {DEST} ({mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
