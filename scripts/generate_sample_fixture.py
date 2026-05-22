"""Generate royalty-free 30s test audio for Phase 3 (stdlib only).

Creates scripts/fixtures/sample_30s.wav (440 Hz tone).
Optionally creates sample_30s.mp3 if ffmpeg is on PATH.
"""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "scripts" / "fixtures"
WAV_PATH = FIXTURES / "sample_30s.wav"
MP3_PATH = FIXTURES / "sample_30s.mp3"

SAMPLE_RATE = 44_100
DURATION_S = 30
FREQUENCY_HZ = 440
AMPLITUDE = 0.25


def write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = SAMPLE_RATE * DURATION_S
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            sample = int(32767 * AMPLITUDE * math.sin(2 * math.pi * FREQUENCY_HZ * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Wrote {path} ({size_mb:.2f} MB, {DURATION_S}s mono @ {SAMPLE_RATE} Hz)")


def write_mp3_from_wav(wav_path: Path, mp3_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not on PATH — skip MP3 (use sample_30s.wav for Phase 3)")
        return False
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "6",
            str(mp3_path),
        ],
        check=True,
        capture_output=True,
    )
    size_kb = mp3_path.stat().st_size / 1024
    print(f"Wrote {mp3_path} ({size_kb:.0f} KB)")
    return True


def main() -> int:
    write_wav(WAV_PATH)
    write_mp3_from_wav(WAV_PATH, MP3_PATH)
    print("Fixture ready for Phase 3 Step 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
