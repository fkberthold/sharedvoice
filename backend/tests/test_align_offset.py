"""Contract: global-offset recovery via windowed cross-correlation (sv-lds.9).

``align_offset(reference, candidate, sr, max_offset_seconds=1.0)`` recovers the
single fixed latency offset between a root recitation and a contributor's take
-- windowed cross-correlation over an onset-strength envelope, constrained to
a plausible latency search window. It must NEVER search the full-length
signal (project constitution, "Forbidden patterns": the liturgy repeats line
openings -- e.g. the five identical "I will no longer allow" openings in
``mental-discipline``, see ``test_corpus.py`` -- so an unconstrained search
locks onto the wrong repetition; the "anaphora bug").

Sign convention: returns the offset in SECONDS such that
``candidate[t] ~= reference[t - offset]`` -- a POSITIVE offset means the
candidate is DELAYED relative to the reference (the common case: headphone
playback + reaction-time latency before a contributor starts reciting along).
A NEGATIVE offset means the candidate leads it.

Method note for sv-lds.15 (the implementation bead this test pins the
contract for): windowed cross-correlation on an onset-strength envelope,
search window +/-1s. NEVER dynamic time warping, phase vocoder, WSOLA, or any
other time-stretching -- this project shifts, it never stretches (project
constitution, "Forbidden patterns"; docs/explanation/mental-model.md).

TDD sequence: this file is written RED-first, before
``sharedvoice/audio/align.py`` exists -- the whole module is missing, so
collection fails with ModuleNotFoundError for the RIGHT reason until sv-lds.15
lands.
"""

from __future__ import annotations

import numpy as np
import pytest

from sharedvoice.audio.align import align_offset

SR = 16000
MAX_OFFSET_SECONDS = 1.0

# Tight relative to the +/-1s search window (2% of it) -- well within reach of
# windowed cross-correlation over sharp synthetic transients, but strict
# enough to catch a lazy/approximate implementation.
TOLERANCE_SECONDS = 0.02

# Aperiodic onset times (irregular gaps: 0.55, 0.85, 0.31, 0.73, 0.62s) so no
# two onsets are separated by a gap close to a tested offset -- avoids a
# false-clean correlation peak that would mask an aligner mis-locking onto a
# repeated line-opening (the anaphora bug this contract exists to prevent).
REFERENCE_ONSETS = [1.5, 2.05, 2.90, 3.21, 3.94, 4.56]
DURATION_SECONDS = 6.5  # ample head/tail room either side of onsets for +/-1s shifts

OFFSET_CASES = [
    pytest.param(0.0, id="zero-offset"),
    pytest.param(0.30, id="mid-positive"),
    pytest.param(-0.30, id="mid-negative"),
    pytest.param(0.95, id="near-positive-edge"),
    pytest.param(-0.95, id="near-negative-edge"),
]


def _burst_train(
    sr: int, n_samples: int, onset_times: list[float], rng: np.random.Generator
) -> np.ndarray:
    """A synthetic onset-strength-ish signal: short decaying noise bursts at
    `onset_times`, standing in for the sharp consonant transients that make
    recitation audio cheap to cross-correlate (docs/explanation/mental-model.md
    -- "Cheap, robust alignment"). Not real speech, just enough transient
    structure for a windowed cross-correlation aligner to lock onto.
    """
    signal = np.zeros(n_samples, dtype=np.float64)
    burst_len = int(0.04 * sr)  # 40ms decaying burst, syllable-onset-ish
    envelope = np.exp(-np.linspace(0.0, 10.0, burst_len))
    for onset in onset_times:
        start = int(round(onset * sr))
        if start >= n_samples:
            continue
        end = min(start + burst_len, n_samples)
        span = end - start
        signal[start:end] += rng.standard_normal(span) * envelope[:span]
    return signal


def _shift(signal: np.ndarray, offset_seconds: float, sr: int) -> np.ndarray:
    """Delay `signal` by `offset_seconds` (negative = advance), same length,
    zero-padded at the freed edge. Mirrors `align_offset`'s sign convention:
    `shifted[t] == signal[t - offset_seconds]`.
    """
    offset_samples = int(round(offset_seconds * sr))
    shifted = np.zeros_like(signal)
    n = len(signal)
    if offset_samples >= 0:
        keep = n - offset_samples
        if keep > 0:
            shifted[offset_samples:] = signal[:keep]
    else:
        drop = -offset_samples
        keep = n - drop
        if keep > 0:
            shifted[:keep] = signal[drop:]
    return shifted


def _make_candidate(
    reference: np.ndarray,
    offset_seconds: float,
    sr: int,
    *,
    gain: float,
    noise_level: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """A shifted, gain-scaled, noisy copy of `reference` -- standing in for a
    contributor's take: different mic level / room hiss, plus the fixed
    latency offset this test pins.
    """
    shifted = _shift(reference, offset_seconds, sr)
    noise = rng.standard_normal(len(shifted)) * noise_level
    return gain * shifted + noise


@pytest.fixture
def reference() -> np.ndarray:
    n_samples = int(round(DURATION_SECONDS * SR))
    rng = np.random.default_rng(seed=1234)
    return _burst_train(SR, n_samples, REFERENCE_ONSETS, rng)


@pytest.mark.parametrize("true_offset_seconds", OFFSET_CASES)
def test_recovers_known_offset_within_tolerance(reference, true_offset_seconds):
    """A clean (low-noise, unit-gain) shifted copy is recovered tightly --
    including offsets near the +/-1s search-window edges, where an aligner
    that clips its window incorrectly (off-by-one, inclusive/exclusive) would
    fail first.
    """
    rng = np.random.default_rng(seed=42)
    candidate = _make_candidate(
        reference, true_offset_seconds, SR, gain=1.0, noise_level=0.01, rng=rng
    )

    recovered = align_offset(reference, candidate, SR, max_offset_seconds=MAX_OFFSET_SECONDS)

    assert recovered == pytest.approx(true_offset_seconds, abs=TOLERANCE_SECONDS)


@pytest.mark.parametrize("true_offset_seconds", OFFSET_CASES)
def test_recovers_known_offset_with_noise_and_gain_change(reference, true_offset_seconds):
    """Robustness: a quieter take (gain 0.4x) with a real noise floor still
    resolves to the same offset -- level and gain differences between
    contributors' mics/rooms must not fool the correlation peak.
    """
    rng = np.random.default_rng(seed=99)
    noisy_candidate = _make_candidate(
        reference, true_offset_seconds, SR, gain=0.4, noise_level=0.15, rng=rng
    )

    recovered = align_offset(reference, noisy_candidate, SR, max_offset_seconds=MAX_OFFSET_SECONDS)

    assert recovered == pytest.approx(true_offset_seconds, abs=TOLERANCE_SECONDS)


def test_never_reports_offset_outside_the_search_window(reference):
    """Hard contract from the project constitution ("never search the
    full-length signal for the cross-correlation peak"): whatever the
    implementation, a returned offset must never exceed the requested +/-1s
    window. This is the anaphora-bug guard -- the liturgy repeats line
    openings, so an unconstrained search could lock onto the wrong repetition
    far outside any plausible latency.
    """
    rng = np.random.default_rng(seed=7)
    candidate = _make_candidate(reference, 0.5, SR, gain=1.0, noise_level=0.01, rng=rng)

    recovered = align_offset(reference, candidate, SR, max_offset_seconds=MAX_OFFSET_SECONDS)

    assert abs(recovered) <= MAX_OFFSET_SECONDS
