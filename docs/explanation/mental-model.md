# Mental model

> **Thesis:** SharedVoice is shaped by one load-bearing idea —
> *this is recitation, not sustained chant.* This page names that
> idea, traces what it makes possible, and is honest about what it
> gives up in return.

## The load-bearing idea

The sangha recites daily affirmations: syllabic speech with an
intonation contour — consonant onsets, rhythmic stress, breath pauses
between lines. It is **not** sustained chant. Everything about the
audio design falls out of that one fact. Because the material is
recitation, participants who follow a root recording track its tempo,
so the dominant misalignment left is a single fixed latency offset —
cheap to recover with plain cross-correlation. No time-stretching, no
phase vocoder, no DTW. If SharedVoice lost this idea and treated the
audio as free-form chant, the whole alignment engine would collapse
into an intractable warping problem.

## What it makes possible

- **"Together," asynchronously.** Nobody has to be online at the same
  time. One person records a root recitation; others recite along to
  it on headphones. The server aligns each take afterwards, so the
  round-trip latency that makes live Zoom recitation impossible simply
  does not apply.
- **Cheap, robust alignment.** Sharp consonant transients give crisp
  cross-correlation peaks. A windowed search over an onset-strength
  envelope recovers each contributor's latency offset without any
  signal warping.
- **The murmur.** The aesthetic target is not tight unison but a
  *murmur* — a hall full of people reciting together. Phrase starts
  are loosely anchored into a deliberate spread so voices stay on the
  same line without collapsing into one flat "congregation creed"
  sound.

## What it gives up

- **No live, synchronous mode.** The whole design assumes contributions
  arrive after the fact. Reciting together in real time is out of
  scope.
- **No tight unison.** Aiming for zero offset lands in the "flam
  valley" — the ~20–60 ms spread that reads as two people who failed
  to sync. SharedVoice deliberately avoids it, which means it will
  never sound like a single voice.
- **No pitch correction.** Recitation is barely pitched; the slightly
  different pitches between contributors *are* the chorus, so no
  auto-tune is applied.

## How to spot drift

The design is drifting away from its load-bearing idea when you see:

- Reaching for DTW, WSOLA, phase vocoders, or any time-stretching to
  "tighten" alignment. The answer is always *shift, never stretch*.
- Aiming for perfect unison, or tuning the `spread` control toward
  zero. That walks straight into the flam valley.
- Re-enabling the browser's `echoCancellation`, `autoGainControl`, or
  `noiseSuppression` on capture. Those are tuned for phone calls and
  turn a choir into a conference call.
- Capturing with `MediaRecorder` blobs instead of raw AudioWorklet
  PCM.

## Cross-references

- [Reference](../reference/index.md) — the surface this idea shapes.
- [How-to guides](../how-to/index.md) — the recipes that follow from
  the shape.
- [Tutorials](../tutorials/index.md) — the guided path that
  introduces the shape.
