"""Contract: the affirmation read endpoints are GATED behind a session
(sv-dkl.4). An authenticated caller seeds + serves the corpus and the root
recording; an anonymous caller is refused with 401. ``/health`` stays public.

Authenticated (via the ``authed_client`` fixture, which registers + logs in):
    GET /affirmations            -> 200, 16 items ordered by order
    GET /affirmations/{id}       -> 200 one affirmation | 404
    GET /affirmations/{id}/root  -> 200 audio bytes | 404 when no root

Anonymous (a plain ``TestClient`` with no login):
    GET /affirmations            -> 401
    GET /affirmations/{id}       -> 401
    GET /affirmations/{id}/root  -> 401
    GET /health                  -> 200 (health is NOT gated)

The three anonymous->401 tests are the RED: they fail until the router gates the
reads behind ``current_user`` (the endpoints still return 200/404 today). The
authed happy-paths and the health-public guard PASS.
"""

from __future__ import annotations

import io
import uuid

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from sharedvoice import models, takes
from sharedvoice.app import create_app
from sharedvoice.audio.ingest import encode_wav
from sharedvoice.storage.db import connect

JOIN_CODE = "test-join-code"
MIX_SR = 48000


def _app(tmp_path):
    return create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")


# --- authenticated happy paths -------------------------------------------

def test_list_returns_16(authed_client):
    resp = authed_client.get("/affirmations")
    assert resp.status_code == 200
    assert len(resp.json()) == 16


def test_list_is_ordered(authed_client):
    data = authed_client.get("/affirmations").json()
    assert [a["order"] for a in data] == list(range(1, 17))
    assert data[0]["id"] == "waking"


def test_get_one_affirmation(authed_client):
    resp = authed_client.get("/affirmations/waking")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Waking Affirmation"
    assert "precious human life" in body["body_text"]


def test_get_missing_affirmation_404(authed_client):
    assert authed_client.get("/affirmations/nope").status_code == 404


def test_root_404_when_absent(authed_client):
    assert authed_client.get("/affirmations/waking/root").status_code == 404


def test_root_served_when_present(authed_client, tmp_path):
    # ``authed_client`` already built the app at tmp_path/"t.db" + tmp_path/"blobs";
    # attach a root recording + blob directly at those SAME paths (the upload
    # endpoint arrives in sv-lds.7), then hit the endpoint via the authed client.
    db_path = tmp_path / "t.db"
    blobs = tmp_path / "blobs"

    conn = connect(db_path)
    models.add_recording(
        conn,
        models.Recording(id="r1", affirmation_id="waking", audio_path="roots/waking.wav",
                         sample_rate=48000, duration=1.0),
    )
    models.set_root_recording(conn, "waking", "r1")
    conn.close()
    (blobs / "roots").mkdir(parents=True, exist_ok=True)
    (blobs / "roots" / "waking.wav").write_bytes(b"RIFFfake-wav")

    resp = authed_client.get("/affirmations/waking/root")
    assert resp.status_code == 200
    assert resp.content == b"RIFFfake-wav"


# --- anonymous requests are gated (RED until the router gate lands) -------

def test_list_anonymous_401(tmp_path):
    resp = TestClient(_app(tmp_path)).get("/affirmations")
    assert resp.status_code == 401


def test_get_one_anonymous_401(tmp_path):
    resp = TestClient(_app(tmp_path)).get("/affirmations/waking")
    assert resp.status_code == 401


def test_root_anonymous_401(tmp_path):
    resp = TestClient(_app(tmp_path)).get("/affirmations/waking/root")
    assert resp.status_code == 401


# --- /health stays public -------------------------------------------------

def test_health_is_public(tmp_path):
    resp = TestClient(_app(tmp_path)).get("/health")
    assert resp.status_code == 200


# --- GET /affirmations/{id}/mix (sv-lds.17) --------------------------------
#
# Curator-only: root-recording upload is curator-only (sv-lds.7) and, per the
# build brief, "a curator picks which voices to include and downloads a
# mix" -- downloading a mix is likewise a curator action. Mixes ALL of the
# affirmation's takes (no voice-selection UI yet -- sv-lds.19). The root is
# always included as one of the mixed tracks, at offset 0 (it defines the
# timeline every take aligns to) -- so even zero takes yields a valid "mix of
# one": the root alone, passed through the same encode/limiter pipeline.
#
# These tests build root/take audio directly (DB row + blob), not via the
# upload endpoints (already covered by test_roots_api.py / test_takes_api.py)
# -- that gives exact, predictable control over a synthetic "click" transient
# so alignment correctness is assertable without flakiness.

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


def _mix_actors(app):
    """(anon, curator, member_a, member_a_id, member_b, member_b_id) --
    first registrant becomes curator (sv-lds.7 convention)."""
    anon = TestClient(app)
    curator = TestClient(app)
    assert _register(curator, "tarpa").status_code == 201
    member_a = TestClient(app)
    reg_a = _register(member_a, "alice")
    assert reg_a.status_code == 201
    member_b = TestClient(app)
    reg_b = _register(member_b, "bob")
    assert reg_b.status_code == 201
    return anon, curator, member_a, reg_a.json()["id"], member_b, reg_b.json()["id"]


def _click_track(duration_s: float, click_at: float, *, amplitude: float = 0.2, sr: int = MIX_SR) -> np.ndarray:
    """A single decaying-exponential 'click' at `click_at` seconds, silence
    elsewhere -- sharp enough for align_offset's onset-envelope correlation
    to lock onto, and simple enough that a shifted copy is an exactly
    predictable signal (unlike random noise bursts, which only add
    *energy*, not *amplitude*, when summed -- useless for asserting
    constructive stacking at the aligned peak).
    """
    n = int(round(duration_s * sr))
    signal = np.zeros(n, dtype=np.float32)
    burst_len = int(round(0.05 * sr))
    envelope = (amplitude * np.exp(-np.linspace(0.0, 8.0, burst_len))).astype(np.float32)
    start = int(round(click_at * sr))
    end = min(start + burst_len, n)
    signal[start:end] = envelope[: end - start]
    return signal


def _shift(signal: np.ndarray, offset_seconds: float, sr: int = MIX_SR) -> np.ndarray:
    """Delay `signal` by `offset_seconds` (negative = advance), zero-padded.
    Mirrors align_offset's sign convention: shifted[t] == signal[t - offset].
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


def _seed_root(tmp_path, samples: np.ndarray, *, sr: int = MIX_SR) -> None:
    conn = connect(tmp_path / "t.db")
    try:
        root_id = uuid.uuid4().hex
        models.add_recording(
            conn,
            models.Recording(
                id=root_id,
                affirmation_id="waking",
                audio_path="roots/waking.wav",
                sample_rate=sr,
                duration=len(samples) / sr,
            ),
        )
        models.set_root_recording(conn, "waking", root_id)
    finally:
        conn.close()
    blob_dir = tmp_path / "blobs" / "roots"
    blob_dir.mkdir(parents=True, exist_ok=True)
    (blob_dir / "waking.wav").write_bytes(encode_wav(samples, sr))


def _seed_take(tmp_path, user_id, contributor_name, samples: np.ndarray, *, sr: int = MIX_SR) -> None:
    take_id = uuid.uuid4().hex
    audio_path = f"takes/{take_id}.wav"
    conn = connect(tmp_path / "t.db")
    try:
        takes.create_take(
            conn,
            takes.Take(
                id=take_id,
                affirmation_id="waking",
                user_id=user_id,
                contributor_name=contributor_name,
                audio_path=audio_path,
            ),
        )
    finally:
        conn.close()
    blob_dir = tmp_path / "blobs" / "takes"
    blob_dir.mkdir(parents=True, exist_ok=True)
    (blob_dir / f"{take_id}.wav").write_bytes(encode_wav(samples, sr))


def test_mix_anonymous_401(tmp_path):
    app = _app(tmp_path)
    anon, _curator, _ma, _ma_id, _mb, _mb_id = _mix_actors(app)
    resp = anon.get("/affirmations/waking/mix")
    assert resp.status_code == 401


def test_mix_member_403(tmp_path):
    app = _app(tmp_path)
    _anon, _curator, member_a, _ma_id, _mb, _mb_id = _mix_actors(app)
    resp = member_a.get("/affirmations/waking/mix")
    assert resp.status_code == 403


def test_mix_missing_affirmation_404(tmp_path):
    app = _app(tmp_path)
    _anon, curator, *_rest = _mix_actors(app)
    resp = curator.get("/affirmations/does-not-exist/mix")
    assert resp.status_code == 404


def test_mix_no_root_recording_404(tmp_path):
    app = _app(tmp_path)
    _anon, curator, *_rest = _mix_actors(app)
    resp = curator.get("/affirmations/waking/mix")
    assert resp.status_code == 404


def test_mix_zero_takes_is_root_alone(tmp_path):
    app = _app(tmp_path)
    _anon, curator, *_rest = _mix_actors(app)

    duration, click_at, amplitude = 2.5, 1.0, 0.2
    root = _click_track(duration, click_at, amplitude=amplitude)
    _seed_root(tmp_path, root)

    resp = curator.get("/affirmations/waking/mix")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert "attachment" in resp.headers.get("content-disposition", "")

    samples, sr = sf.read(io.BytesIO(resp.content))
    assert sr == MIX_SR
    assert abs(len(samples) / sr - duration) < 0.05

    peak = np.max(np.abs(samples[int(0.9 * sr): int(1.15 * sr)]))
    # transparent below the soft-limiter's knee -- a solo root passes through
    # essentially unchanged.
    assert 0.15 < peak < 0.25


def test_mix_includes_root_and_all_takes_aligned(tmp_path):
    app = _app(tmp_path)
    _anon, curator, _ma, ma_id, _mb, mb_id = _mix_actors(app)

    duration, click_at, amplitude = 2.5, 1.0, 0.2
    reference = _click_track(duration, click_at, amplitude=amplitude)
    take_a = _shift(reference, 0.4)  # contributor started 0.4s late
    take_b = _shift(reference, -0.3)  # contributor started 0.3s early

    _seed_root(tmp_path, reference)
    _seed_take(tmp_path, ma_id, "Alice", take_a)
    _seed_take(tmp_path, mb_id, "Bob", take_b)

    resp = curator.get("/affirmations/waking/mix")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert "attachment" in resp.headers.get("content-disposition", "")

    samples, sr = sf.read(io.BytesIO(resp.content))
    assert sr == MIX_SR
    assert samples.ndim == 1  # mono
    assert abs(len(samples) / sr - duration) < 0.05
    assert np.max(np.abs(samples)) <= 1.0 + 1e-6  # no-clip invariant

    # All three tracks' clicks should have been shifted into alignment at
    # click_at, stacking constructively -- well above a lone track's ~0.2
    # peak (and comfortably below the soft-limiter's 0.7 knee, so the
    # comparison isn't muddied by compression).
    peak_near_click = np.max(np.abs(samples[int(0.9 * sr): int(1.15 * sr)]))
    assert peak_near_click > 1.5 * amplitude

    # Away from the click, the mix should be near-silent -- sanity check
    # that this isn't just broadband noise everywhere.
    tail = np.max(np.abs(samples[int(2.2 * sr):]))
    assert tail < 0.05
