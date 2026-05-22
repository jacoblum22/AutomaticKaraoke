"""Phase 3 Step 1 gate — fixture present + demucs/torch importable."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "scripts" / "fixtures"

FIXTURE_CANDIDATES = (
    FIXTURES / "sample_30s.mp3",
    FIXTURES / "sample_30s.wav",
)


def find_fixture() -> Path | None:
    for path in FIXTURE_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def main() -> int:
    fixture = find_fixture()
    if fixture is None:
        print("FAIL: no fixture. Run:")
        print("  python scripts/generate_sample_fixture.py")
        print("Or add scripts/fixtures/sample_30s.mp3 (30s audio you have rights to).")
        return 1

    print(f"fixture: {fixture} ({fixture.stat().st_size} bytes)")

    try:
        import demucs  # noqa: F401
        import torch
    except ImportError as e:
        print(f"FAIL: import error — {e}")
        print("Install: pip install -r backend/requirements-demucs.txt")
        return 1

    cuda = torch.cuda.is_available()
    print(f"demucs: ok ({getattr(demucs, '__version__', 'unknown')})")
    print(f"torch: ok ({torch.__version__}, cuda={cuda})")
    print("Phase 3 Step 1 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
