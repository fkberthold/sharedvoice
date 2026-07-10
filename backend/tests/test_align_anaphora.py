"""RED regression contract for the anaphora bug (sv-lds.10).

The liturgy repeats line openings — e.g. "I will no longer allow my" (x5),
"May all be", "I appreciate" — so an UNCONSTRAINED cross-correlation search
over a whole recording can lock onto the WRONG repetition of a phrase and
shift a take's alignment by a whole line. The project constitution is
explicit about this (see "Forbidden patterns" in
``.claude/project-constitution.md``):

    Never search the full-length signal for the cross-correlation peak —
    constrain the lag search to a plausible latency window (+/-1 s). The
    liturgy repeats line openings; an unconstrained search locks onto the
    wrong repetition (the anaphora bug).

The (future, not-yet-built) global-offset aligner at
``sharedvoice.audio.align`` — sv-lds.15, a separate blocked bead — is
contractually required to honor that +/-1s guard. This module does NOT
implement that aligner; it only PINS the regression contract so sv-lds.15
has a falsifiable target. Until sv-lds.15 lands, every test below fails at
COLLECTION with ``ModuleNotFoundError`` (no ``sharedvoice/audio/align.py``
exists yet) — that is the expected RED state for this bead.

Signature convention
---------------------
No sibling ``sharedvoice.audio.align`` module or ``test_align_offset.py``
exists in this worktree (checked via ``git log`` / ``git grep`` before
writing this file), so the exact signature sv-lds.15 will land is unknown.
This test assumes::

    align_offset(
        reference: np.ndarray,
        candidate: np.ndarray,
        sr: int,
        expected_offset: float = 0.0,
        window: float = 1.0,
    ) -> float

extending the base ``align_offset(reference, candidate, sr) -> float`` shape
with ``expected_offset``/``window`` keyword args, because the +/-1s guard is
only meaningful *around* something — the aligner must be told the plausible
latency estimate it is allowed to search near. If sv-lds.15 lands with a
different signature (e.g. the expected offset baked into how the caller
slices ``reference`` instead of passed explicitly), this file's call site is
the one place to update; the synthetic-signal construction and the offsets
it asserts stay valid regardless.

Synthetic scenario
-------------------
* ``reference`` is a synthetic recording containing ``N_REPETITIONS`` = 5
  copies of the SAME onset transient ("phrase"), spaced
  ``LINE_SPACING_SECONDS`` = 3.0s apart — standing in for a liturgy line
  opening that recurs identically five times.
* ``candidate`` is a synthetic take whose phrase-bearing region is a
  BIT-EXACT copy of the reference's repetition at
  ``DISTRACTOR_REPETITION_ONSET`` (one line before the take's true line).
  Because it is bit-exact, it is a PERFECT correlation match there — the
  theoretical maximum — which is guaranteed to outscore the candidate's
  correlation against the TRUE repetition at ``TRUE_REPETITION_ONSET``
  (which shares only the same phrase shape, not this candidate's exact
  ambient-noise realization). ``test_naive_unconstrained_correlation_...``
  proves this numerically, independent of ``align_offset``, so the trap is
  not merely asserted — it is demonstrated.
* ``EXPECTED_OFFSET_HINT_SECONDS`` (a rough scheduling estimate, 0.2s off
  the true offset — modeling ordinary clock/latency jitter) sits close to
  ``TRUE_OFFSET_SECONDS`` but 3.0s away from ``DISTRACTOR_OFFSET_SECONDS``.
  A search correctly constrained to +/-1s around the hint can only ever see
  the true repetition; an unconstrained (or over-widened) search sees both
  and prefers the distractor.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import chirp, correlate
from scipy.signal.windows import hann

from sharedvoice.audio.align import align_offset

SR = 8000

LINE_SPACING_SECONDS = 3.0
PHRASE_ONSETS = [0.0, 3.0, 6.0, 9.0, 12.0]  # 5 repeated line-openings
PHRASE_DURATION_SECONDS = 0.6
REFERENCE_DURATION_SECONDS = 14.0
AMBIENT_NOISE_STD = 0.05

CANDIDATE_PAD_BEFORE_SECONDS = 0.7
CANDIDATE_PAD_AFTER_SECONDS = 0.7
CANDIDATE_DURATION_SECONDS = (
    CANDIDATE_PAD_BEFORE_SECONDS + PHRASE_DURATION_SECONDS + CANDIDATE_PAD_AFTER_SECONDS
)

# One line before the take's true line — the false peak an unconstrained
# search will prefer.
DISTRACTOR_REPETITION_ONSET = 3.0
# The line this take actually belongs to.
TRUE_REPETITION_ONSET = 6.0

# A rough scheduling estimate, deliberately NOT exact (0.2s off true) —
# ordinary latency jitter, not a hand-picked answer.
EXPECTED_OFFSET_HINT_SECONDS = 5.5
SEARCH_WINDOW_SECONDS = 1.0  # the contractual +/-1s guard

TRUE_OFFSET_SECONDS = TRUE_REPETITION_ONSET - CANDIDATE_PAD_BEFORE_SECONDS  # 5.3
DISTRACTOR_OFFSET_SECONDS = DISTRACTOR_REPETITION_ONSET - CANDIDATE_PAD_BEFORE_SECONDS  # 2.3

REFERENCE_NOISE_SEED = 42
CANDIDATE_NOISE_SEED = 123


def _make_phrase(sr: int, duration: float) -> np.ndarray:
    """A synthetic line-opening transient: a rising chirp under a Hann
    attack/decay envelope, standing in for a spoken phrase onset like
    "I will no longer allow my ...". The SAME array is reused at every
    onset below, mirroring how the same words produce the same onset shape
    every time a liturgy line-opening repeats.
    """
    n = int(round(duration * sr))
    t = np.arange(n) / sr
    carrier = chirp(t, f0=300.0, f1=1200.0, t1=duration, method="linear")
    envelope = hann(n)
    return (carrier * envelope).astype(np.float64)


def _build_reference() -> np.ndarray:
    """The canonical reference recording: 5 copies of the SAME phrase,
    spaced ``LINE_SPACING_SECONDS`` apart, in low-level ambient noise.
    """
    rng = np.random.default_rng(REFERENCE_NOISE_SEED)
    n_samples = int(round(REFERENCE_DURATION_SECONDS * SR))
    reference = rng.normal(0.0, AMBIENT_NOISE_STD, n_samples)

    phrase = _make_phrase(SR, PHRASE_DURATION_SECONDS)
    phrase_len = len(phrase)
    for onset in PHRASE_ONSETS:
        start = int(round(onset * SR))
        reference[start:start + phrase_len] += phrase
    return reference


def _build_candidate(reference: np.ndarray) -> np.ndarray:
    """A candidate take engineered so an unconstrained search is handed a
    trap: the phrase-bearing region is a BIT-EXACT copy of the reference's
    DISTRACTOR repetition (see module docstring for why that guarantees the
    distractor outscores the true repetition under unconstrained search).
    """
    rng = np.random.default_rng(CANDIDATE_NOISE_SEED)
    n_samples = int(round(CANDIDATE_DURATION_SECONDS * SR))
    candidate = rng.normal(0.0, AMBIENT_NOISE_STD, n_samples)

    phrase_len = int(round(PHRASE_DURATION_SECONDS * SR))
    distractor_start = int(round(DISTRACTOR_REPETITION_ONSET * SR))
    distractor_slice = reference[distractor_start:distractor_start + phrase_len]

    pad_before_samples = int(round(CANDIDATE_PAD_BEFORE_SECONDS * SR))
    candidate[pad_before_samples:pad_before_samples + phrase_len] = distractor_slice
    return candidate


def _naive_unconstrained_search(reference: np.ndarray, candidate: np.ndarray):
    """A plain, UNCONSTRAINED cross-correlation over the whole signal — the
    exact anti-pattern the constitution forbids. Returns
    ``(argmax_lag_seconds, corr_at_argmax, corr_at_true_offset)`` so callers
    can compare the naive answer against the true one without going through
    ``align_offset`` at all.
    """
    full_corr = correlate(reference, candidate, mode="valid", method="fft")
    lags = np.arange(len(full_corr)) / SR

    naive_argmax_lag = float(lags[np.argmax(full_corr)])
    corr_at_naive = float(np.max(full_corr))
    true_idx = int(round(TRUE_OFFSET_SECONDS * SR))
    corr_at_true = float(full_corr[true_idx])

    return naive_argmax_lag, corr_at_naive, corr_at_true


def test_naive_unconstrained_correlation_would_pick_the_wrong_repetition():
    """Falsifiability check, independent of ``align_offset``: proves the
    synthetic scenario really is a trap and not just an assertion. A plain
    unconstrained xcorr's global best match is the DISTRACTOR repetition
    (~2.3s), not the TRUE one (~5.3s) — exactly the anaphora bug the
    constitution warns about ("an unconstrained search locks onto the wrong
    repetition").
    """
    reference = _build_reference()
    candidate = _build_candidate(reference)

    naive_lag, corr_at_naive, corr_at_true = _naive_unconstrained_search(reference, candidate)

    assert naive_lag == pytest.approx(DISTRACTOR_OFFSET_SECONDS, abs=0.02), (
        "the synthetic scenario is supposed to make the DISTRACTOR repetition "
        f"the unconstrained global-argmax; got argmax lag {naive_lag}s, expected "
        f"~{DISTRACTOR_OFFSET_SECONDS}s"
    )
    assert corr_at_naive > corr_at_true, (
        "the distractor repetition must out-correlate the true repetition for "
        "this to be a genuine trap, not a trivially-easy case"
    )


def test_windowed_search_recovers_true_offset_not_wrong_repetition():
    """The core sv-lds.10 regression contract.

    ``align_offset`` is called with an ``expected_offset`` hint
    (``EXPECTED_OFFSET_HINT_SECONDS`` = 5.5s, itself 0.2s off the true
    offset — ordinary jitter) and the contractual ``window`` = 1.0s. The
    true repetition (5.3s) sits inside that window; the higher-correlation
    distractor repetition (2.3s) sits 3.2s away, well outside it.

    A correctly windowed implementation can only ever see the true
    repetition and must return ~5.3s. If the search window is REMOVED
    (full-signal search) or WIDENED past the guard (e.g. enough to reach
    3.2s away), the distractor's higher correlation wins instead and this
    assertion fails — see
    ``test_naive_unconstrained_correlation_would_pick_the_wrong_repetition``
    for the numeric proof that the distractor really does outscore the true
    match.
    """
    reference = _build_reference()
    candidate = _build_candidate(reference)

    result = align_offset(
        reference,
        candidate,
        SR,
        expected_offset=EXPECTED_OFFSET_HINT_SECONDS,
        window=SEARCH_WINDOW_SECONDS,
    )

    assert result == pytest.approx(TRUE_OFFSET_SECONDS, abs=0.02), (
        f"expected the +/-{SEARCH_WINDOW_SECONDS}s windowed search around "
        f"{EXPECTED_OFFSET_HINT_SECONDS}s to recover the TRUE repetition's "
        f"offset ({TRUE_OFFSET_SECONDS}s), got {result}s"
    )
    # Explicitly not the wrong (but higher-correlation) repetition an
    # unconstrained search would have preferred.
    assert abs(result - DISTRACTOR_OFFSET_SECONDS) > 0.5, (
        "windowed search must not have drifted onto the distractor "
        f"repetition's offset ({DISTRACTOR_OFFSET_SECONDS}s), got {result}s"
    )
