"""Download faster-whisper weights with resume + retries (Windows-friendly).

Use when local Whisper fails with IncompleteRead during model.bin download.
Example:
  .\\.venv\\Scripts\\python.exe scripts\\download_whisper_model.py --model large-v3
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Systran repos match faster-whisper model_size names.
MODEL_REPOS: dict[str, str] = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-whisper-distil-large-v2",
    "distil-large-v3": "Systran/faster-whisper-distil-large-v3",
}

# model.bin sizes (bytes) for sanity check after download.
EXPECTED_MODEL_BIN_BYTES: dict[str, int] = {
    "large-v3": 3_087_284_930,
    "large-v2": 3_087_284_930,
    "medium": 1_529_053_573,
}


def _cache_slug(repo_id: str) -> str:
    return "models--" + repo_id.replace("/", "--")


def _clear_incomplete_blobs(model_size: str) -> int:
    repo_id = MODEL_REPOS[model_size]
    cache_root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    blobs_dir = cache_root / _cache_slug(repo_id) / "blobs"
    if not blobs_dir.is_dir():
        return 0
    removed = 0
    for path in blobs_dir.glob("*.incomplete"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def _find_model_bin(model_size: str) -> Path | None:
    repo_id = MODEL_REPOS[model_size]
    cache_root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    snapshots = cache_root / _cache_slug(repo_id) / "snapshots"
    if not snapshots.is_dir():
        return None
    for snap in snapshots.iterdir():
        candidate = snap / "model.bin"
        if candidate.is_file():
            return candidate
    return None


def download_model(
    model_size: str,
    *,
    max_attempts: int = 5,
    use_hf_transfer: bool = True,
) -> Path:
    if model_size not in MODEL_REPOS:
        raise ValueError(f"unknown model {model_size!r}; choose from {sorted(MODEL_REPOS)}")

    repo_id = MODEL_REPOS[model_size]
    if use_hf_transfer:
        try:
            import hf_transfer  # noqa: F401
        except ImportError:
            print(
                "tip: pip install hf_transfer for faster, more reliable downloads",
                file=sys.stderr,
            )
        else:
            os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

    from huggingface_hub import snapshot_download

    expected = EXPECTED_MODEL_BIN_BYTES.get(model_size)
    last_err: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        removed = _clear_incomplete_blobs(model_size)
        if removed:
            print(f"cleared {removed} incomplete blob(s) before attempt {attempt}")

        try:
            print(f"download attempt {attempt}/{max_attempts}: {repo_id}")
            t0 = time.perf_counter()
            path = snapshot_download(repo_id)
            elapsed = time.perf_counter() - t0
            print(f"snapshot: {path} ({elapsed:.0f}s)")

            model_bin = _find_model_bin(model_size)
            if model_bin is None:
                raise RuntimeError("download finished but model.bin not found in cache")

            size = model_bin.stat().st_size
            print(f"model.bin: {model_bin} ({size / 1e9:.2f} GB)")
            if expected is not None and abs(size - expected) > 1024:
                raise RuntimeError(
                    f"model.bin size {size} != expected ~{expected} (corrupt or partial)"
                )
            return model_bin
        except Exception as e:
            last_err = e
            print(f"attempt {attempt} failed: {e}", file=sys.stderr)
            if attempt < max_attempts:
                wait = min(60, 5 * attempt)
                print(f"retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)

    raise RuntimeError(f"download failed after {max_attempts} attempts") from last_err


def main() -> int:
    parser = argparse.ArgumentParser(description="Download faster-whisper model weights")
    parser.add_argument(
        "--model",
        default="large-v3",
        help="faster-whisper model size (default: large-v3)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Retry count on network errors",
    )
    parser.add_argument(
        "--no-hf-transfer",
        action="store_true",
        help="Do not enable HF_HUB_ENABLE_HF_TRANSFER",
    )
    args = parser.parse_args()

    try:
        download_model(
            args.model,
            max_attempts=args.max_attempts,
            use_hf_transfer=not args.no_hf_transfer,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("Whisper model download OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
