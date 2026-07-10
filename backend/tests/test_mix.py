"""Contract for the mix engine (sv-lds.11) — implementation lands in sv-lds.16.

``sharedvoice.audio.mix`` does not exist yet. This file is a pure RED-test
pin: it defines, via failing tests, the mix engine's public surface and the
three aesthetic/correctness invariants from the constitution
(``.claude/project-constitution.md``) and Frank's build brief:

1. **No-clip**: summing many "hot" tracks and passing them through a soft
   limiter must never leave [-1.0, 1.0], even though a naive sum would.
2. **Mute = exact removal**: muting a take must remove EXACTLY that take's
   contribution to the mix — not an approximation, not a side effect on the
   other tracks' rendering.
3. **Spread distribution**: the aesthetic target is a *murmur*, not unison.
   ``spread_ms`` controls phrase-start offset jitter across tracks.
   ``spread_ms == 0`` collapses toward unison; higher ``spread_ms`` must
   widen the offset DISTRIBUTION (not just its mean) while avoiding the
   [20, 60] ms "flam valley", which reads as a mistake rather than a chorus.

Contract surface pinned by this file (the implementer's job in sv-lds.16):

- ``mix_tracks(tracks, sr, mute=None, spread_ms=0.0, rng=None) -> np.ndarray``
  Sums aligned mono float32 ``tracks`` (each already phrase-aligned at index
  0 by the alignment pipeline) into one mix, after applying per-track
  phrase-start jitter (see ``spread_offsets_ms`` below) and a soft limiter.
  ``mute`` is a set of indices into ``tracks`` to exclude from the sum
  entirely, as if they had never been passed.

- ``spread_offsets_ms(n_tracks, spread_ms, rng=None) -> np.ndarray``
  The per-track phrase-start offsets (in ms) that ``mix_tracks`` draws from
  when rendering at a given ``spread_ms``. Pulled out as its own pure,
  directly-testable function (rather than only reachable by detecting
  onsets in a summed, overlapping mix) so the statistical-spread invariant
  can be pinned deterministically with a seeded ``rng``.

- ``soft_limit(samples, ceiling=1.0) -> np.ndarray``
  The non-clipping limiter ``mix_tracks`` applies before returning, kept
  separately importable for the no-clip invariant.

These are judgment calls made while authoring this RED test (sv-lds.11 is a
contract-pinning bead, not an implementation bead) — the implementer of
sv-lds.16 should treat this file, not the prose above, as the source of
truth.
"""

from __future__ import annotations

import numpy as np
import pytest

from sharedvoice.audio.mix import mix_tracks, soft_limit, spread_offsets_ms

SR = 48000


def _tone(freq: float, amplitude: float, duration_s: float, sr: int = SR) -> np.ndarray:
    """A synthetic mono float32 sine track — a stand-in for an aligned take."""
    n = int(duration_s * sr)
    t = np.arange(n) / sr
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# (a) No-clip: summing hot tracks must never leave [-1.0, 1.0].
# ---------------------------------------------------------------------------


def test_summing_hot_tracks_never_clips():
    """8 tracks at 0.9 amplitude naively sum to a peak of ~7.2 -- way past
    [-1, 1]. The soft limiter must bring the mixed output back in range.
    """
    n_tracks = 8
    tracks = [_tone(440.0 + 10.0 * i, 0.9, duration_s=0.5) for i in range(n_tracks)]

    naive_peak = np.max(np.abs(np.sum(tracks, axis=0)))
    assert naive_peak > 1.0, "test setup sanity: naive sum should clip"

    mixed = mix_tracks(tracks, SR)

    assert np.all(np.isfinite(mixed)), "limiter output must not be NaN/Inf"
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6, (
        f"soft-limited mix exceeded [-1, 1]: peak={np.max(np.abs(mixed))}"
    )


def test_soft_limit_is_transparent_well_below_ceiling():
    """A quiet signal, far under the ceiling, should pass through the
    limiter essentially unchanged -- it's a LIMITER, not a compressor that
    colors everything.
    """
    quiet = _tone(220.0, 0.1, duration_s=0.2)
    limited = soft_limit(quiet, ceiling=1.0)
    np.testing.assert_allclose(limited, quiet, atol=1e-3)


def test_soft_limit_never_exceeds_ceiling_for_extreme_input():
    """A pathological, way-over-ceiling input must still come back capped."""
    hot = _tone(300.0, 5.0, duration_s=0.2)  # amplitude 5.0 -- absurdly hot
    limited = soft_limit(hot, ceiling=1.0)
    assert np.max(np.abs(limited)) <= 1.0 + 1e-6


# ---------------------------------------------------------------------------
# (b) Mute = exact removal, not an approximation.
# ---------------------------------------------------------------------------


def test_mute_removes_exactly_that_takes_contribution():
    """mix(tracks) - mix(tracks with take `i` muted) must equal take `i`'s
    own (solo) contribution to the mix -- exactly, not approximately.

    Amplitudes are kept low (well under the limiter's engagement region) so
    this test is isolated from limiter nonlinearity -- that's what test (a)
    covers. Here we're pinning pure "muting excludes the track from the sum"
    behavior, and spread_ms=0.0 so there's no jitter to also disentangle.
    """
    tracks = [
        _tone(300.0 + 50.0 * i, amplitude=0.05 * (i + 1), duration_s=0.3) for i in range(4)
    ]
    muted_index = 2

    full_mix = mix_tracks(tracks, SR, spread_ms=0.0)
    partial_mix = mix_tracks(tracks, SR, mute={muted_index}, spread_ms=0.0)
    solo = mix_tracks([tracks[muted_index]], SR, spread_ms=0.0)

    assert full_mix.shape == partial_mix.shape == solo.shape

    removed_contribution = full_mix - partial_mix
    np.testing.assert_allclose(
        removed_contribution,
        solo,
        atol=1e-5,
        err_msg="muting a take must remove EXACTLY its own contribution",
    )


def test_muting_all_but_one_equals_that_ones_solo_mix():
    """Muting every other take leaves a mix identical to that one take
    mixed alone -- another angle on 'mute is exact removal, not a fade'.
    """
    tracks = [_tone(400.0 + 20.0 * i, amplitude=0.04, duration_s=0.25) for i in range(5)]
    keep_index = 3
    muted = set(range(len(tracks))) - {keep_index}

    mostly_muted = mix_tracks(tracks, SR, mute=muted, spread_ms=0.0)
    solo = mix_tracks([tracks[keep_index]], SR, spread_ms=0.0)

    np.testing.assert_allclose(mostly_muted, solo, atol=1e-5)


def test_mute_is_empty_set_by_default():
    """Omitting `mute` entirely must NOT silently drop any tracks."""
    tracks = [_tone(350.0, amplitude=0.05, duration_s=0.2) for _ in range(3)]
    default_mix = mix_tracks(tracks, SR, spread_ms=0.0)
    explicit_empty_mix = mix_tracks(tracks, SR, mute=set(), spread_ms=0.0)
    np.testing.assert_allclose(default_mix, explicit_empty_mix, atol=1e-6)


# ---------------------------------------------------------------------------
# (c) Spread distribution: widen offsets with spread_ms, avoid the flam
#     valley ([20, 60] ms), cluster toward the [80, 250] ms murmur target.
# ---------------------------------------------------------------------------


def test_zero_spread_collapses_offsets_toward_unison():
    offsets = spread_offsets_ms(n_tracks=16, spread_ms=0.0, rng=np.random.default_rng(1))
    assert len(offsets) == 16
    np.testing.assert_allclose(offsets, 0.0, atol=1e-6)


def test_higher_spread_widens_the_offset_distribution():
    """This pins STATISTICAL SPREAD (stddev), not just a shifted mean --
    a naive implementation that only shifts the mean while keeping variance
    fixed must fail this test.
    """
    n_tracks = 128
    low = spread_offsets_ms(n_tracks, spread_ms=20.0, rng=np.random.default_rng(123))
    high = spread_offsets_ms(n_tracks, spread_ms=200.0, rng=np.random.default_rng(456))

    assert np.std(high) > np.std(low), (
        f"expected wider spread at spread_ms=200 than spread_ms=20, "
        f"got std(high)={np.std(high)} std(low)={np.std(low)}"
    )
    # Range (max - min) is a second, cruder statistical-spread signal.
    assert (np.max(high) - np.min(high)) > (np.max(low) - np.min(low))


def test_spread_offsets_avoid_the_flam_valley():
    """[20, 60] ms reads as a mistake, not a chorus (constitution 'Forbidden
    patterns' + build brief). At a spread aimed at the murmur target, only a
    small minority of offsets may land in that band, and the bulk of the
    distribution should sit in [80, 250] ms.
    """
    n_tracks = 300
    offsets = np.abs(
        spread_offsets_ms(n_tracks, spread_ms=150.0, rng=np.random.default_rng(99))
    )

    fraction_in_flam_valley = np.mean((offsets >= 20.0) & (offsets <= 60.0))
    assert fraction_in_flam_valley < 0.15, (
        f"too many offsets ({fraction_in_flam_valley:.0%}) landed in the "
        f"[20, 60]ms flam valley"
    )

    fraction_in_murmur_target = np.mean((offsets >= 80.0) & (offsets <= 250.0))
    assert fraction_in_murmur_target > 0.5, (
        "expected the bulk of the offset distribution to cluster in the "
        "[80, 250]ms murmur target range as spread increases"
    )


def test_spread_offsets_length_matches_track_count():
    offsets = spread_offsets_ms(n_tracks=7, spread_ms=100.0, rng=np.random.default_rng(2))
    assert len(offsets) == 7


@pytest.mark.parametrize("spread_ms", [0.0, 50.0, 180.0])
def test_mix_tracks_accepts_spread_ms_without_crashing(spread_ms):
    """Integration-flavored smoke test tying spread_ms into the full
    mix_tracks entry point (not just the offsets helper) -- the mix must
    still be finite and in range regardless of jitter.
    """
    tracks = [_tone(300.0 + 15.0 * i, amplitude=0.1, duration_s=0.4) for i in range(6)]
    mixed = mix_tracks(tracks, SR, spread_ms=spread_ms, rng=np.random.default_rng(0))
    assert np.all(np.isfinite(mixed))
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6
