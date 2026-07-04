"""Pure audio-ingest logic — no HTTP, no storage, unit-testable in isolation.

SharedVoice's canonical audio format is 48000 Hz mono. Every uploaded
recording (root or, later, take) is decoded and resampled to this format
before it is written to a blob, so downstream processing (alignment,
mixing) never has to reason about mixed sample rates or channel counts.
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from librosa import resample as librosa_resample

CANONICAL_SAMPLE_RATE = 48000


class InvalidAudioError(ValueError):
    """Raised when the given bytes cannot be decoded as audio."""


def resample_to_48k_mono(src: bytes | str) -> tuple[np.ndarray, int, float]:
    """Decode `src`, downmix to mono, and resample to 48 kHz.

    ``src`` is either raw audio bytes (e.g. from an upload) or a path to an
    audio file on disk. Returns ``(samples, sample_rate, duration_seconds)``
    where ``sample_rate`` is always ``CANONICAL_SAMPLE_RATE`` and ``samples``
    is a 1-D float32 array.

    Raises ``InvalidAudioError`` if the input cannot be decoded as audio.
    """
    try:
        data, sr = sf.read(io.BytesIO(src) if isinstance(src, bytes) else src, dtype="float32", always_2d=True)
    except Exception as exc:  # soundfile raises its own LibsndfileError subtypes
        raise InvalidAudioError(f"could not decode audio: {exc}") from exc

    # Downmix to mono by averaging channels.
    mono = data.mean(axis=1).astype(np.float32)

    if sr != CANONICAL_SAMPLE_RATE:
        mono = librosa_resample(mono, orig_sr=sr, target_sr=CANONICAL_SAMPLE_RATE)
        mono = mono.astype(np.float32)

    duration = len(mono) / CANONICAL_SAMPLE_RATE
    return mono, CANONICAL_SAMPLE_RATE, duration


def encode_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode a mono float32 array as WAV bytes (for writing to a BlobStore)."""
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()
