"""Global-offset aligner: windowed cross-correlation over an onset-strength
envelope (sv-lds.15).

``align_offset(reference, candidate, sr, expected_offset=0.0,
max_offset_seconds=1.0)`` recovers the fixed latency offset between a root
recitation (``reference``) and a contributor's take (``candidate``) --
windowed cross-correlation over an onset-strength envelope, constrained to
a plausible latency search window centered on ``expected_offset``.

Sign convention (canonical, pinned by ``test_align_offset.py``): returns the
offset in SECONDS such that ``candidate[t] ~= reference[t - offset]`` -- a
POSITIVE offset means the candidate is DELAYED relative to the reference
(the common case: headphone playback + reaction-time latency before a
contributor starts reciting along). A NEGATIVE offset means the candidate
leads it.

Method: a rectified + smoothed short-window energy derivative turns each
signal into an "onset-strength" envelope that peaks at transient onsets
(sharp consonant/burst attacks -- see docs/explanation/mental-model.md,
"Cheap, robust alignment"). The reference is FIRST sliced down to only the
plausible latency window (``[expected_offset - max_offset_seconds,
expected_offset + max_offset_seconds]``, padded by the candidate's own
length so every lag in the window still has full overlap) -- envelope and
correlation math only ever run on that slice. This is the anaphora-bug
guard: the aligner structurally cannot see, let alone lock onto, a repeated
line-opening outside the window (project constitution, "Forbidden
patterns" -- "Never search the full-length signal for the cross-correlation
peak").

NEVER dynamic time warping, phase vocoder, WSOLA, or any other
time-stretching -- this project shifts, it never stretches.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import correlate

# Short-window energy smoothing before differentiating -- long enough to
# average out sample-level noise, short enough to keep sharp onsets sharp.
_ENERGY_SMOOTH_SECONDS = 0.01


def _onset_strength_envelope(signal: np.ndarray, sr: int) -> np.ndarray:
    """Rectified + smoothed short-window energy derivative: turns raw audio
    into a signal that peaks at transient onsets (consonant attacks / noise
    burst starts / chirp attacks). Time-domain, no mel-spectrogram
    assumptions -- recitation transients are broadband, not tonal, so a
    plain energy-flux envelope is cheap and robust here.
    """
    energy = np.asarray(signal, dtype=np.float64) ** 2
    smooth_samples = max(1, int(round(_ENERGY_SMOOTH_SECONDS * sr)))
    smoothed = uniform_filter1d(energy, size=smooth_samples, mode="nearest")
    onset = np.diff(smoothed, prepend=smoothed[0])
    np.clip(onset, 0.0, None, out=onset)  # half-wave rectify: only rising energy is an "onset"
    return onset


def align_offset(
    reference: np.ndarray,
    candidate: np.ndarray,
    sr: int,
    expected_offset: float = 0.0,
    max_offset_seconds: float = 1.0,
) -> float:
    """Recover the offset (seconds) such that ``candidate[t] ~=
    reference[t - offset]``, searching only within ``[expected_offset -
    max_offset_seconds, expected_offset + max_offset_seconds]`` (the
    anaphora-bug guard -- see module docstring).
    """
    reference = np.asarray(reference, dtype=np.float64)
    candidate = np.asarray(candidate, dtype=np.float64)

    window_lo_seconds = expected_offset - max_offset_seconds
    window_hi_seconds = expected_offset + max_offset_seconds

    # Constrain the search: slice out only the plausible latency window of
    # the reference -- padded by the candidate's own length so every lag in
    # the window still has a fully-overlapping comparison -- *before* any
    # envelope/correlation math ever runs. The aligner never even looks at
    # reference audio outside this slice.
    # For candidate[t] = reference[t - O] with t in [0, Nc), the reference
    # index touched is (t - O), ranging over [-O, Nc - O). As O sweeps the
    # requested window, that range's lower bound is smallest (0) at the
    # largest O and its upper bound is largest at the smallest O -- so the
    # union of reference indices ever needed across the whole window is
    # [max(0, -window_hi), min(Nr, Nc - window_lo)), NOT a slice built from
    # window_lo/window_hi symmetrically (that under-covers negative-offset
    # windows, since a very negative offset needs *late* reference indices).
    window_start_samples = max(0, int(np.floor(-window_hi_seconds * sr)))
    window_end_samples = min(
        len(reference), int(np.ceil(len(candidate) - window_lo_seconds * sr))
    )
    if window_end_samples <= window_start_samples:
        # Requested window doesn't overlap the reference at all -- nothing
        # to search; fall back to the (clamped) hint.
        return float(np.clip(expected_offset, window_lo_seconds, window_hi_seconds))

    ref_window = reference[window_start_samples:window_end_samples]

    ref_env = _onset_strength_envelope(ref_window, sr)
    cand_env = _onset_strength_envelope(candidate, sr)

    # score(shift) = sum_j ref_env[j] * cand_env[j + shift]; scipy's 'full'
    # correlate(cand_env, ref_env) gives exactly this at index (shift + Nr-1),
    # where `shift` is expressed relative to ref_window's own local origin
    # (candidate[t] ~= reference[t - offset] => local `shift` = offset +
    # window_start_samples).
    corr = correlate(cand_env, ref_env, mode="full", method="fft")
    nr_local = len(ref_env)
    shift_axis = np.arange(len(corr)) - (nr_local - 1)

    lag_lo_local = int(round(window_lo_seconds * sr)) + window_start_samples
    lag_hi_local = int(round(window_hi_seconds * sr)) + window_start_samples

    in_window = (shift_axis >= lag_lo_local) & (shift_axis <= lag_hi_local)
    if not np.any(in_window):
        return float(np.clip(expected_offset, window_lo_seconds, window_hi_seconds))

    candidate_indices = np.nonzero(in_window)[0]
    best_index = candidate_indices[np.argmax(corr[candidate_indices])]
    best_shift_samples = int(shift_axis[best_index])

    offset_samples = best_shift_samples - window_start_samples
    offset_seconds = offset_samples / sr

    # Defensive clamp: guarantees the contract even if edge rounding nudges
    # the raw estimate a hair outside [lo, hi].
    return float(np.clip(offset_seconds, window_lo_seconds, window_hi_seconds))
