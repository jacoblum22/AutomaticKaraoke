"""Demucs isolation test — implemented in Phase 3."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Separate vocals from mixed audio (Phase 3)")
    parser.add_argument(
        "input",
        nargs="?",
        default="scripts/fixtures/sample_30s.mp3",
        help="Path to input audio",
    )
    args = parser.parse_args()
    print(f"Phase 3 — Demucs not implemented yet. Would process: {args.input}")


if __name__ == "__main__":
    main()
