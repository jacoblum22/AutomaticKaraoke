"""Demucs vocal separation (Phase 3).

Input: path to mixed audio
Output: (vocals.wav, instrumental.wav) under output_dir
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch as th
from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.separate import load_track

MODEL_NAME = "htdemucs"
VOCAL_STEM = "vocals"
OUTPUT_VOCALS = "vocals.wav"
OUTPUT_INSTRUMENTAL = "instrumental.wav"


class SeparationError(RuntimeError):
    """Demucs separation failed."""


def _save_wav(path: Path, tensor: th.Tensor, samplerate: int) -> None:
    """Write float tensor (channels, time) as 16-bit PCM WAV without torchcodec."""
    import wave

    wav = tensor.detach().cpu()
    if wav.dim() == 1:
        wav = wav.unsqueeze(0)
    audio = wav.transpose(0, 1).numpy()
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(pcm.shape[1])
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(pcm.tobytes())


def _resolve_device(device: str | None) -> str:
    if device is not None:
        return device
    return "cuda" if th.cuda.is_available() else "cpu"


def separate_audio(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    device: str | None = None,
    shifts: int = 1,
    progress: bool = True,
) -> tuple[Path, Path]:
    """Run htdemucs and write vocals + instrumental WAVs.

    Instrumental is the sum of all non-vocal stems (equivalent to no_vocals).
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    if not input_path.is_file():
        raise SeparationError(f"Input file not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    vocals_path = output_dir / OUTPUT_VOCALS
    instrumental_path = output_dir / OUTPUT_INSTRUMENTAL

    dev = _resolve_device(device)

    try:
        model = get_model(MODEL_NAME)
    except Exception as e:
        raise SeparationError(f"Failed to load Demucs model {MODEL_NAME}: {e}") from e

    model.cpu()
    model.eval()

    if VOCAL_STEM not in model.sources:
        raise SeparationError(
            f'Model {MODEL_NAME} has no "{VOCAL_STEM}" stem; sources={model.sources}'
        )

    wav = load_track(input_path, model.audio_channels, model.samplerate)

    ref = wav.mean(0)
    wav = wav - ref.mean()
    wav = wav / ref.std()

    sources = apply_model(
        model,
        wav[None],
        device=dev,
        shifts=shifts,
        split=True,
        overlap=0.25,
        progress=progress,
    )[0]
    sources = sources * ref.std() + ref.mean()

    vocal_idx = model.sources.index(VOCAL_STEM)
    vocals = sources[vocal_idx]
    instrumental = th.zeros_like(vocals)
    for i, stem in enumerate(sources):
        if i != vocal_idx:
            instrumental = instrumental + stem

    _save_wav(vocals_path, vocals, model.samplerate)
    _save_wav(instrumental_path, instrumental, model.samplerate)

    if not vocals_path.is_file() or vocals_path.stat().st_size == 0:
        raise SeparationError(f"Missing or empty output: {vocals_path}")
    if not instrumental_path.is_file() or instrumental_path.stat().st_size == 0:
        raise SeparationError(f"Missing or empty output: {instrumental_path}")

    return vocals_path, instrumental_path
