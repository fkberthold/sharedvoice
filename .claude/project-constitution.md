---
# Project constitution — YAML front-matter
#
# Authoritative tooling profile for sharedvoice. Dispatched workers,
# hooks, and skills read this to stay aligned. Front-matter below was
# auto-detected during /loom-adopt P5 (2026-07-02) and reconciled to
# Frank's build brief (2026-07-02, MemPalace drawer f7c9d745) once the
# project's purpose + stack were known.
#
# Leave keys as empty strings ("") / empty lists ([]) when they don't
# apply — don't delete keys.

shell:
  # Target dev shell is a Nix flake (python + audio deps + ffmpeg +
  # node/pnpm). enter stays "" until flake.nix actually lands (bead
  # sv-lds.1); that bead flips enter -> "nix develop". Setting it before
  # the flake exists would break workers entering a shell that isn't there.
  enter: ""
  run_prefix: ""

# Backend python deps. Frontend uses pnpm (node) — see prose "Tooling
# choices". Single package_manager field tracks the primary (backend).
package_manager: pip

language:
  runtime: python
  # No version marker pinned yet — set when the flake fixes it.
  version: ""

# Bash patterns the agent must NEVER run here (lock-in posture). The
# project's hard constraints are ARCHITECTURAL (no DTW / no MediaRecorder
# / capture-flags-off) not bash-command-shaped, so they live in the prose
# "Forbidden patterns" section, not here. Empty by design.
forbidden: []

canonical_commands:
  build: ""
  test: "pytest"
  lint: "ruff check ."
  gen: ""
  # dev/build/deploy fixed once they exist (never-invent discipline):
  # backend dev will be a uvicorn command; frontend dev a pnpm command.
  dev: ""
  deploy: ""

# Escape hatches that bypass constitution enforcement. Use sparingly.
bypass_patterns: []

# Project-specific ARCHITECTURAL invariants (enforced across Bash +
# write-class tools). The audio DO-NOTs are documented in prose rather
# than regex-enforced here (code-shaped, not reliably pattern-matchable).
#
# invariants:
#   - id: <e.g. no-direct-file-io>
#     applies_to:
#       - Write
#       - Edit
#       - MultiEdit
#     deny_pattern: "<e.g. \\bopen\\( >"
#     message: "<e.g. reason this is forbidden>"
---

# sharedvoice — project constitution

SharedVoice is a small, self-hosted web app that lets a remote Buddhist sangha
(the Secular Buddhist Tradition) recite their daily affirmations "together"
**asynchronously**. One person (Venerable Tarpa) records a *root* recitation of
an affirmation; others listen to that root on headphones while recording
themselves reciting along; the server *aligns* each contribution to the root,
and a curator picks which voices to include and downloads a mix — the felt
result being "a hall full of people reciting together," though nobody was
online at the same time. It replaces trying to do this live over Zoom, where
round-trip latency makes synchronized recitation impossible. It is private,
non-commercial, for one community; audio is treated as sensitive by default.

This constitution pins the tooling profile so dispatched workers, hooks, and
skills stay aligned. The full design spec lives in the MemPalace
`sharedvoice/decisions` drawer `f7c9d745` (Frank's build brief). Read that
before touching the audio pipeline.

## Tooling choices

The one design fact that drives everything: **this is recitation, not sustained
chant** — syllabic speech with sharp consonant transients. That makes alignment
cheap (plain cross-correlation, never time-warping) and makes Python the natural
home, because the audio-science ecosystem we lean on lives there.

- **Shell**: a **Nix flake** (`flake.nix`) providing a reproducible `nix develop`
  shell with Python + the audio deps + ffmpeg + node/pnpm. Frank works in Nix on
  Ubuntu (Helix editor — no IDE config needed). `shell.enter` is set to
  `nix develop` once the flake lands (bead `sv-lds.1`).
- **Backend**: **Python + FastAPI**. Python for the audio ecosystem
  (`numpy`, `scipy.signal`, `librosa`, `soundfile`, `ffmpeg`); FastAPI for clean
  async file-upload endpoints. Package manager `pip` (no lockfile yet;
  reconsider `uv`/`poetry` once deps stabilize).
- **Frontend**: **framework-light TypeScript + Web Audio API**, built with
  **pnpm**/node (Vite). The app is small and the hard part is audio, not UI —
  vanilla TS with thin structure; no heavy SPA stack.
- **Storage**: filesystem for audio blobs + SQLite for metadata in the MVP,
  behind an **interface** so it can move to object storage later without
  touching the pipeline.
- **Canonical commands**: `test: pytest`, `lint: ruff check .` (mirror
  `.beads/preflight.template`). `build`/`gen`/`dev`/`deploy` filled as they
  come into existence.

## Forbidden patterns

These are architectural DO-NOTs from the brief — traps that turn "a choir" into
"a conference call." They are code-shaped (not bash patterns), so they are
enforced by review + tests, not by the `forbidden:` front-matter list.

- **No time-stretching, phase vocoder, WSOLA, or DTW-based warping** in v1. We
  *shift*, we never *stretch*. Reciting along live makes tempo-warping
  unnecessary, and it is the most artifact-prone subsystem there is.
- **No pitch correction / auto-tune.** Recitation is barely pitched; slightly
  different pitches *are* the chorus.
- **Never re-enable** `echoCancellation` / `autoGainControl` / `noiseSuppression`
  on mic capture. All three stay off (with a mandatory headphone gate).
- **No `MediaRecorder` blobs** where AudioWorklet Float32 PCM is specified.
- **Never search the full-length signal** for the cross-correlation peak —
  constrain the lag search to a plausible latency window (±1 s). The liturgy
  repeats line openings; an unconstrained search locks onto the wrong repetition
  (the anaphora bug).
- **Do not aim for tight unison.** The aesthetic target is a *murmur*
  (phrase-start spread in [80, 250] ms); landing near 0 ms passes through the
  [20, 60] ms flam valley, which reads as a mistake.

## Bypass patterns

None. `bypass_patterns: []` — no escape hatches are authored yet.

## Lineage

- **Design spec**: MemPalace `sharedvoice/decisions` drawer `f7c9d745` — Frank's
  SharedVoice build brief (2026-07-02).
- **Adoption**: captured by `/loom-adopt` P5 on 2026-07-02; front-matter mirrors
  the P1 audit drawer `drawer_sharedvoice_decisions_281fc837258180ee634fcef0`
  and the P5 constitution drawer `drawer_sharedvoice_decisions_17936f90...`.
- **Beads**: epic `sv-lds` (SharedVoice) and its Phase 0–3 children; this prose
  authored under `sv-fa9`. The Nix flake / `shell.enter` reconciliation is
  owned by `sv-lds.1`.
