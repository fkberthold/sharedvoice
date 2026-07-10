"""Contract: member take upload + 48k-mono ingest + Take row (sv-lds.14).

``POST /affirmations/{affirmation_id}/takes`` accepts a multipart audio file
from ANY logged-in sangha member (not curator-only, unlike root upload —
sv-lds.7). It ingests the upload through the same
``sharedvoice.audio.ingest`` pipeline as root upload (resample to canonical
48000 Hz mono), stores the resampled blob via ``app.state.storage``, and
writes a ``Take`` row stamped with the uploader's ``user_id`` /
``contributor_name`` (derived from ``user.display_name``).

Alignment is left as a nullable placeholder on the row — the real aligner is
sv-lds.15, still blocked/future work; this bead does not attempt real
alignment.

TDD sequence (mirrors sv-lds.7 / test_roots_api.py): written RED-first,
before ``sharedvoice/takes.py`` and ``sharedvoice/routers/takes.py`` exist —
every test here should fail for the RIGHT reason (route not registered /
import error) until the implementation lands.
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from sharedvoice.app import create_app
from sharedvoice.storage.db import connect
from sharedvoice.takes import get_take

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


def _two_actors(app):
    """(anon, member, member_public) — a logged-in sangha member (need not be curator)."""
    anon = TestClient(app)
    member = TestClient(app)
    reg = _register(member, "member")
    assert reg.status_code == 201
    return anon, member, reg.json()


def _sine_wav_bytes(*, sr=44100, seconds=0.5, freq=440.0) -> bytes:
    """A synthetic NON-48k mono WAV, entirely in memory."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    samples = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV")
    buf.seek(0)
    return buf.read()


def _upload(client, affirmation_id, *, sr=44100, seconds=0.5, filename="take.wav"):
    data = _sine_wav_bytes(sr=sr, seconds=seconds)
    return client.post(
        f"/affirmations/{affirmation_id}/takes",
        files={"file": (filename, data, "audio/wav")},
    )


# --- GREEN: a logged-in member uploads a take ------------------------------

def test_member_upload_resamples_to_48k_and_creates_take(tmp_path):
    app = _app(tmp_path)
    _anon, member, member_public = _two_actors(app)

    resp = _upload(member, "waking", sr=44100, seconds=0.5)
    assert resp.status_code == 201
    body = resp.json()
    assert body["affirmation_id"] == "waking"
    assert body["contributor_name"] == "Member"
    assert body["user_id"] == member_public["id"]
    assert body["alignment"] is None
    assert "id" in body
    assert "audio_path" in body
    assert "created_at" in body

    conn = connect(tmp_path / "t.db")
    try:
        take = get_take(conn, body["id"])
        assert take is not None
        assert take.affirmation_id == "waking"
        assert take.user_id == member_public["id"]
        assert take.contributor_name == "Member"
        assert take.alignment is None
        assert take.created_at is not None
    finally:
        conn.close()

    # The stored blob is genuinely resampled 48k-mono audio.
    blob_path = tmp_path / "blobs" / take.audio_path
    assert blob_path.is_file()
    stored, stored_sr = sf.read(blob_path)
    assert stored_sr == 48000
    assert stored.ndim == 1  # mono
    assert 0.4 < (len(stored) / stored_sr) < 0.6


def test_two_members_can_each_upload_a_take_for_the_same_affirmation(tmp_path):
    app = _app(tmp_path)
    member_a = TestClient(app)
    member_b = TestClient(app)
    assert _register(member_a, "alice").status_code == 201
    assert _register(member_b, "bob").status_code == 201

    resp_a = _upload(member_a, "waking")
    resp_b = _upload(member_b, "waking")
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    assert resp_a.json()["id"] != resp_b.json()["id"]
    assert resp_a.json()["user_id"] != resp_b.json()["user_id"]
    assert resp_a.json()["contributor_name"] == "Alice"
    assert resp_b.json()["contributor_name"] == "Bob"


def test_upload_missing_affirmation_404(tmp_path):
    app = _app(tmp_path)
    _anon, member, _member_public = _two_actors(app)

    resp = _upload(member, "does-not-exist")
    assert resp.status_code == 404


def test_upload_invalid_audio_is_422(tmp_path):
    app = _app(tmp_path)
    _anon, member, _member_public = _two_actors(app)

    resp = member.post(
        "/affirmations/waking/takes",
        files={"file": ("junk.wav", b"not actually audio", "audio/wav")},
    )
    assert resp.status_code == 422


def test_anonymous_upload_401(tmp_path):
    app = _app(tmp_path)
    anon, _member, _member_public = _two_actors(app)
    resp = _upload(anon, "waking")
    assert resp.status_code == 401
