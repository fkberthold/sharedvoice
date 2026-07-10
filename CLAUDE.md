# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

SharedVoice is a small, self-hosted web app that lets a remote Buddhist
sangha (the Secular Buddhist Tradition) recite their daily affirmations
"together" **asynchronously**. One person (a curator) records a *root*
recitation of an affirmation; other members listen to that root on
headphones while recording themselves reciting along; the server *aligns*
each contribution to the root, and a curator picks which voices to include
and downloads a mix — the felt result being "a hall full of people
reciting together," though nobody was online at the same time. It replaces
trying to do this live over Zoom, where round-trip latency makes
synchronized recitation impossible.

Private, non-commercial, single-community app. Audio is treated as
sensitive by default.

Full design spec: MemPalace `sharedvoice/decisions` drawer `f7c9d745`
(Frank's build brief). Read that before touching the audio pipeline.

## The one design fact that drives everything

This is **recitation, not sustained chant** — syllabic speech with sharp
consonant transients. That makes alignment cheap (plain windowed
cross-correlation, never time-warping) and the aesthetic target a
**murmur**, not tight unison.

## Repository layout

```
backend/sharedvoice/       FastAPI app, flat modules (no deep package nesting)
  app.py                   create_app() — wires routers + schema init
  models.py, users.py      dataclass + _SCHEMA string + init_*_schema(conn)
                            + DAO functions, per module (flat-module convention)
  security.py              bcrypt password hashing (hash_password/verify_password)
  dependencies.py          current_user / require_curator FastAPI deps
  corpus.py                affirmation corpus loading
  storage/                 storage interface (filesystem blobs + SQLite metadata)
  audio/                   pure, HTTP-free, unit-testable audio functions
                            (ingest.py: resample_to_48k_mono, encode_wav)
  routers/                 affirmations.py, auth.py, roots.py
backend/tests/              pytest suite (see Testing below)
frontend/                   Vite + vanilla TypeScript, no framework/router
  main.ts, entry.ts         boot(container, api) DI-dispatch (main.ts) kept
                            separate from real fetch wiring (entry.ts)
  api.ts                    typed fetch wrappers to the backend
data/                       affirmation corpus + seed audio
docs/                       MkDocs Material site (Diataxis-shaped)
```

## Tooling

- **Shell**: devbox (Nix-backed), `devbox.json`. `devbox shell` for
  interactive work; `devbox run -- <cmd>` for one-shot commands — both
  build `.venv` + install backend/docs requirements via `init_hook`.
- **Backend**: Python + FastAPI, `pip` (no lockfile yet). Audio ecosystem:
  numpy, scipy.signal, librosa, soundfile, ffmpeg.
- **Frontend**: TypeScript + Web Audio API, pnpm/node, Vite. No SPA
  framework — the app is small and the hard part is audio, not UI.
- **Storage**: filesystem for audio blobs + SQLite for metadata (MVP),
  behind an interface so it can move to object storage later.

### Dev-server gotcha (important)

`devbox run -- uvicorn sharedvoice.main:app --app-dir backend ...` does
**not** `cd` into `backend/` — devbox run resets cwd to repo root, and
`--app-dir` only adds `backend` to `sys.path`. The app's default DB path
(`var/sharedvoice.db`) then resolves against the wrong root, silently
creating an empty DB at `<repo>/var/` instead of `<repo>/backend/var/`.
Always start it with explicit env vars:

```
SHAREDVOICE_DB=backend/var/sharedvoice.db SHAREDVOICE_BLOBS=backend/var/blobs \
  devbox run -- uvicorn sharedvoice.main:app --app-dir backend --reload --reload-dir backend
```

`--reload-dir backend` matters too — without it, `--reload` watches the
whole repo including any `.claude/worktrees/*` from dispatched agents,
causing spurious reloads mid-dispatch.

### Testing

Canonical commands (from `.claude/project-constitution.md`):
`devbox run -- pytest`, `devbox run -- ruff check .`.

**Dispatched-agent / worktree gotcha**: the root `.venv` is gitignored, so
it's **absent** in a fresh isolation worktree. Run tests with the MAIN
checkout's venv instead: `/home/frank/repos/sharedvoice/.venv/bin/pytest -q`
(pytest's `pythonpath = ["backend"]` resolves relative to the worktree).
Do **not** use `devbox run -- pytest` from a worktree — it rebuilds the
whole venv from scratch (multi-minute, reinstalling librosa/scipy/numba).
New deps: install into the main venv and add to `backend/requirements.txt`.

Frontend: `pnpm test` (Vitest + jsdom) from `frontend/`.

## Frontend conventions

Pure render functions return `HTMLElement`; `data-testid=...` are the DOM
hooks for testability. `boot(container, api)` in `main.ts` is DI-dispatch,
kept separate (pure/testable) from `entry.ts` (real fetch wiring). Backend
`Affirmation` is `{id, title, body_text}`, not `{id, text}` —
`api.ts` maps `body_text` (falling back to `title`) to the frontend's
`text` field.

## Architectural DO-NOTs (from the build brief, enforced by review + tests, not regex)

- **No time-stretching, phase vocoder, WSOLA, or DTW-based warping.** We
  *shift*, never *stretch*.
- **No pitch correction / auto-tune.**
- **Never re-enable** `echoCancellation` / `autoGainControl` /
  `noiseSuppression` on mic capture. All three stay off, with a mandatory
  headphone gate.
- **No `MediaRecorder` blobs** where AudioWorklet Float32 PCM is
  specified.
- **Never search the full-length signal** for the cross-correlation peak
  — constrain the lag search to a plausible latency window (±1s). The
  liturgy repeats line openings; an unconstrained search locks onto the
  wrong repetition (the anaphora bug).
- **Do not aim for tight unison.** The aesthetic target is a *murmur*
  (phrase-start spread in [80, 250] ms); near-zero offsets land in the
  [20, 60] ms "flam valley," which reads as a mistake.

## Beads

This project uses `bd` (beads) for task tracking, prefix `sv`. Epic
`sv-lds` tracks the SharedVoice build (Phase 0 scaffold → P1 MVP loop →
P2 per-phrase/murmur → P3 curation/polish). Run `bd ready` to see
unblocked work; `bd memories sharedvoice` for tribal facts (dev-server
gotchas, dispatch gotchas, frontend conventions).
