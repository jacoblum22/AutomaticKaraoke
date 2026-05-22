"""Phase 4 Step 3 gate — transcribe + align → lyrics.json + validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "scripts" / "output" / "lyrics.json"


def main() -> int:
    py = sys.executable
    test = REPO_ROOT / "scripts" / "test_whisper_local.py"
    validate = REPO_ROOT / "scripts" / "validate_lyrics_json.py"

    print("=== transcribe + align ===")
    proc = subprocess.run(
        [py, str(test), "--output", str(OUTPUT), "--clip-end", "30"],
        cwd=REPO_ROOT,
        check=False,
    )
    if proc.returncode != 0:
        return proc.returncode

    print("\n=== validate lyrics.json ===")
    proc = subprocess.run([py, str(validate), str(OUTPUT)], cwd=REPO_ROOT, check=False)
    if proc.returncode != 0:
        return proc.returncode

    print("Phase 4 Step 3 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
