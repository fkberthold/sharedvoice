"""Contract: batch root-recording ingest from a directory of clip files (sv-lds.20.2).

``ingest_root_clips(conn, storage, clips_dir)`` is the BATCH sibling of
``routers/roots.py``'s per-upload ``upload_root``. For each file in
``clips_dir`` named ``{affirmation_id}.<ext>`` whose stem matches a real
affirmation already in the DB, it runs the EXISTING
``resample_to_48k_mono`` + ``encode_wav`` pipeline (unchanged), stores the
blob at ``roots/{affirmation_id}.wav``, and persists via ``add_recording`` +
``set_root_recording`` -- reading from disk instead of an ``UploadFile``.
Files whose stem does not match any affirmation are silently skipped (no
error, no partial DB writes). Returns the SORTED list of affirmation ids
successfully ingested.

TDD sequence: this file is written RED-first, before
``sharedvoice/audio/root_ingest_batch.py`` exists -- the whole module is
missing, so collection fails with ModuleNotFoundError for the RIGHT reason
until the implementation lands.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import soundfile as sf

from sharedvoice import models
from sharedvoice.audio.root_ingest_batch import ingest_root_clips
from sharedvoice.models import Affirmation
from sharedvoice.storage.db import connect
from sharedvoice.storage.local import LocalBlobStore


def _write_sine_wav(path: Path, *, sr: int = 44100, seconds: float = 0.5, freq: float = 440.0) -> None:
    """Write a synthetic NON-48k mono WAV directly to `path` on disk."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    samples = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), samples, sr, format="WAV")


def _seed(conn) -> None:
    """Seed exactly two synthetic affirmations (NOT the real corpus)."""
    models.add_affirmation(conn, Affirmation(id="waking", title="Waking", order=1))
    models.add_affirmation(conn, Affirmation(id="resting", title="Resting", order=2))


def _clips_dir(tmp_path: Path) -> Path:
    """A directory of three clip files: two matched, one unmatched."""
    clips = tmp_path / "clips"
    clips.mkdir()
    _write_sine_wav(clips / "waking.wav", sr=44100, seconds=0.5, freq=440.0)
    _write_sine_wav(clips / "resting.wav", sr=44100, seconds=0.5, freq=330.0)
    # `unknown-id` matches no seeded affirmation -> must be silently skipped.
    _write_sine_wav(clips / "unknown-id.wav", sr=44100, seconds=0.5, freq=220.0)
    return clips


def test_ingest_root_clips_matches_seeds_and_skips_unknown(tmp_path):
    conn = connect(tmp_path / "t.db")
    models.init_schema(conn)
    _seed(conn)
    clips = _clips_dir(tmp_path)
    storage = LocalBlobStore(tmp_path / "blobs")

    ingested = ingest_root_clips(conn, storage, clips)

    # Sorted list of successfully ingested ids; `unknown-id` skipped, no raise.
    assert ingested == ["resting", "waking"]

    for affirmation_id in ("waking", "resting"):
        affirmation = models.get_affirmation(conn, affirmation_id)
        assert affirmation is not None
        assert affirmation.root_recording_id is not None

        recording = models.get_recording(conn, affirmation.root_recording_id)
        assert recording is not None
        assert recording.affirmation_id == affirmation_id
        assert recording.audio_path == f"roots/{affirmation_id}.wav"
        assert recording.sample_rate == 48000
        assert recording.duration > 0

        # The stored blob is genuinely resampled 48k-mono audio.
        assert storage.exists(recording.audio_path) is True
        stored, stored_sr = sf.read(io.BytesIO(storage.get(recording.audio_path)))
        assert stored_sr == 48000
        assert stored.ndim == 1  # mono

    # The unmatched file left no trace: no recording row references it.
    assert models.get_affirmation(conn, "unknown-id") is None
    assert storage.exists("roots/unknown-id.wav") is False

    conn.close()


def test_ingest_root_clips_rerun_does_not_crash(tmp_path):
    # Idempotency is NOT required to dedupe (upload_root mints a fresh uuid4
    # per recording, so a re-run simply writes a new Recording row and
    # re-points the root). The contract only requires that re-running over the
    # SAME clips_dir does not raise and still reports the matched ids.
    conn = connect(tmp_path / "t.db")
    models.init_schema(conn)
    _seed(conn)
    clips = _clips_dir(tmp_path)
    storage = LocalBlobStore(tmp_path / "blobs")

    first = ingest_root_clips(conn, storage, clips)
    assert first == ["resting", "waking"]

    second = ingest_root_clips(conn, storage, clips)
    assert second == ["resting", "waking"]

    conn.close()
