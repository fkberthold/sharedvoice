"""Pure mix-engine logic (sv-lds.16) -- no HTTP, no storage.

Sums already-aligned mono float32 takes into one mix, honoring the
constitution's murmur-not-unison aesthetic target and the no-clip
invariant. Tracks arriving here are assumed already phrase-aligned at
index 0 by the alignment pipeline (``sharedvoice.audio.align``, a sibling
module) -- ``mix_tracks`` does no temporal alignment of its own. It only:

1. Excludes muted tracks entirely (as if never passed).
2. Applies a small per-track phrase-start jitter (see ``spread_offsets_ms``)
   so the mix reads as a murmur rather than tight unison.
3. Sums the result.
4. Passes the sum through ``soft_limit`` so hot mixes never clip.

See ``backend/tests/test_mix.py`` for the pinned contract this module
implements (authored under sv-lds.11).
"""

from __future__ import annotations

import numpy as np

# Fraction of `spread_ms` used as the standard deviation of the sampled
# jitter magnitude -- wide enough to give a real spread of onsets, narrow
# enough that the bulk of the distribution still clusters near `spread_ms`
# itself (see spread_offsets_ms docstring for why we center on spread_ms
# rather than on zero).
_MAGNITUDE_SPREAD_FRACTION = 0.3

# Soft-limiter knee: signals at or under this fraction of `ceiling` pass
# through completely untouched (a limiter should be transparent at normal
# levels); only the portion above the knee is compressed toward `ceiling`.
_KNEE_FRACTION = 0.7


def spread_offsets_ms(
    n_tracks: int,
    spread_ms: float,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Per-track phrase-start jitter offsets (ms), one per track.

    ``spread_ms == 0`` (or negative) collapses to exact unison: an
    all-zero array, no randomness involved at all.

    For ``spread_ms > 0``, offsets are NOT drawn from a zero-centered
    normal (``rng.normal(0, spread_ms)``) -- that shape puts a large
    share of its mass near zero, which is exactly the [20, 60] ms "flam
    valley" the constitution calls out as reading like a mistake rather
    than a chorus. Instead we sample the offset MAGNITUDE from a normal
    centered on ``spread_ms`` itself (stddev a fraction of ``spread_ms``),
    then apply a random sign. That keeps the bulk of the distribution
    clustered around the requested spread (a genuine "murmur" of
    staggered onsets) while still letting `spread_ms` scale both the
    center and the width of the distribution, so larger `spread_ms`
    widens the spread (not just shifts the mean) as required.
    """
    if spread_ms <= 0.0:
        return np.zeros(n_tracks, dtype=np.float64)

    if rng is None:
        rng = np.random.default_rng()

    magnitude = rng.normal(
        loc=spread_ms, scale=spread_ms * _MAGNITUDE_SPREAD_FRACTION, size=n_tracks
    )
    magnitude = np.clip(magnitude, 0.0, None)
    sign = rng.choice(np.array([-1.0, 1.0]), size=n_tracks)
    return sign * magnitude


def _shift_samples(track: np.ndarray, offset_ms: float, sr: int) -> np.ndarray:
    """Shift `track` by `offset_ms` (positive = later, negative = earlier),
    zero-padding the freed edge. Output length matches the input length --
    content shifted past either edge is dropped, like a simple delay line.
    """
    offset_samples = int(round(offset_ms / 1000.0 * sr))
    if offset_samples == 0:
        return track.astype(np.float32, copy=True)

    shifted = np.zeros_like(track)
    n = len(track)
    if offset_samples > 0:
        if offset_samples < n:
            shifted[offset_samples:] = track[: n - offset_samples]
    else:
        advance = -offset_samples
        if advance < n:
            shifted[: n - advance] = track[advance:]
    return shifted


def mix_tracks(
    tracks: list[np.ndarray],
    sr: int,
    mute: set[int] | None = None,
    spread_ms: float = 0.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Mix `tracks` (already mono float32, already phrase-aligned at index
    0) into one mono float32 mix.

    `mute` is a set of indices into `tracks` to exclude from the sum
    entirely, as if they had never been passed. `spread_ms` controls
    per-track phrase-start jitter (see `spread_offsets_ms`); 0.0 means no
    jitter. The summed result is passed through `soft_limit` so a mix of
    many hot takes never leaves [-1, 1].
    """
    if mute is None:
        mute = set()
    kept = [track for i, track in enumerate(tracks) if i not in mute]
    if not kept:
        return np.zeros(0, dtype=np.float32)

    offsets_ms = spread_offsets_ms(len(kept), spread_ms, rng=rng)
    shifted = [_shift_samples(track, offset_ms, sr) for track, offset_ms in zip(kept, offsets_ms)]

    max_len = max(len(t) for t in shifted)
    summed = np.zeros(max_len, dtype=np.float64)
    for t in shifted:
        summed[: len(t)] += t.astype(np.float64)

    return soft_limit(summed.astype(np.float32))


def soft_limit(samples: np.ndarray, ceiling: float = 1.0) -> np.ndarray:
    """A soft-knee limiter, not a hard clip.

    Below `_KNEE_FRACTION * ceiling`, output is exactly the input --
    transparent, no coloration of normal-level signal. Above that knee,
    the excess is compressed with a tanh curve that asymptotically
    approaches `ceiling`, so pathologically hot input is capped without
    ever producing a hard clip, NaN, or Inf.
    """
    samples = np.asarray(samples, dtype=np.float64)
    threshold = _KNEE_FRACTION * ceiling
    span = ceiling - threshold
    abs_samples = np.abs(samples)

    limited = np.where(
        abs_samples <= threshold,
        samples,
        np.sign(samples) * (threshold + span * np.tanh((abs_samples - threshold) / span)),
    )
    return limited.astype(np.float32)
