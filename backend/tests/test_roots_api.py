"""Contract: curator-only root-recording upload (sv-lds.7).

``POST /affirmations/{affirmation_id}/root`` accepts a multipart audio file,
ingests it (resample to canonical 48000 Hz mono, compute duration), stores the
resampled blob via ``app.state.storage``, writes a ``Recording`` row, and sets
it as the affirmation's root. Curator-only: ``Depends(require_curator)``.

TDD sequence (see sv-lds.7 notes): this file is written RED-first, before
``sharedvoice/routers/roots.py`` and ``sharedvoice/audio/ingest.py`` exist —
the whole module is missing, so every test here 404s / errors for the RIGHT
reason (route not registered) until the implementation lands.
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from sharedvoice import models
from sharedvoice.app import create_app
from sharedvoice.storage.db import connect

JOIN_CODE = "test-join-code"


def _app(tmp_path):
    return create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")


def _register(client, username, *, password="pw"):
    return client.post(
        "/auth/register",
        json={
            "join_code": JOIN_CODE,
            "username": username,
            "display_name": username.title(),
            "password": password,
        },
    )


def _three_actors(app):
    """(anon, member, curator) — first registrant becomes curator."""
    anon = TestClient(app)
    curator = TestClient(app)
    assert _register(curator, "tarpa").status_code == 201
    member = TestClient(app)
    assert _register(member, "member").status_code == 201
    return anon, member, curator


def _sine_wav_bytes(*, sr=44100, seconds=0.5, freq=440.0) -> bytes:
    """A synthetic NON-48k mono WAV, entirely in memory."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    samples = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV")
    buf.seek(0)
    return buf.read()


def _upload(client, affirmation_id, *, sr=44100, seconds=0.5, filename="clip.wav"):
    data = _sine_wav_bytes(sr=sr, seconds=seconds)
    return client.post(
        f"/affirmations/{affirmation_id}/root",
        files={"file": (filename, data, "audio/wav")},
    )


# --- GREEN: curator uploads a non-48k clip --------------------------------

def test_curator_upload_resamples_to_48k_and_sets_root(tmp_path):
    app = _app(tmp_path)
    _anon, _member, curator = _three_actors(app)

    resp = _upload(curator, "waking", sr=44100, seconds=0.5)
    assert resp.status_code == 201
    body = resp.json()
    assert body["affirmation_id"] == "waking"
    assert body["sample_rate"] == 48000
    assert 0.4 < body["duration"] < 0.6
    assert "id" in body

    conn = connect(tmp_path / "t.db")
    try:
        recording = models.get_recording(conn, body["id"])
        assert recording is not None
        assert recording.sample_rate == 48000
        assert 0.4 < recording.duration < 0.6
        affirmation = models.get_affirmation(conn, "waking")
        assert affirmation.root_recording_id == recording.id
    finally:
        conn.close()

    # The stored blob is genuinely resampled 48k-mono audio, servable via GET.
    get_resp = curator.get("/affirmations/waking/root")
    assert get_resp.status_code == 200
    stored, stored_sr = sf.read(io.BytesIO(get_resp.content))
    assert stored_sr == 48000
    assert stored.ndim == 1  # mono


def test_upload_missing_affirmation_404(tmp_path):
    app = _app(tmp_path)
    _anon, _member, curator = _three_actors(app)

    resp = _upload(curator, "does-not-exist")
    assert resp.status_code == 404


def test_upload_invalid_audio_is_a_clean_4xx(tmp_path):
    app = _app(tmp_path)
    _anon, _member, curator = _three_actors(app)

    resp = curator.post(
        "/affirmations/waking/root",
        files={"file": ("junk.wav", b"not actually audio", "audio/wav")},
    )
    assert 400 <= resp.status_code < 500


# --- auth matrix: anon -> 401, member -> 403, curator -> 201 --------------

def test_anonymous_upload_401(tmp_path):
    app = _app(tmp_path)
    anon, _member, _curator = _three_actors(app)
    resp = _upload(anon, "waking")
    assert resp.status_code == 401


def test_member_upload_403(tmp_path):
    app = _app(tmp_path)
    _anon, member, _curator = _three_actors(app)
    resp = _upload(member, "waking")
    assert resp.status_code == 403
