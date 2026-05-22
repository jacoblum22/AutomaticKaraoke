"""Transcription + alignment test on vocal stem — implemented in Phase 4."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe and align vocals.wav (Phase 4)"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="scripts/fixtures/vocals_30s.wav",
        help="Path to isolated vocal stem",
    )
    args = parser.parse_args()
    print(f"Phase 4 — Whisper/WhisperX not implemented yet. Would process: {args.input}")


if __name__ == "__main__":
    main()
