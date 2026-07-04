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

from fastapi.testclient import TestClient

from sharedvoice import models
from sharedvoice.app import create_app
from sharedvoice.storage.db import connect


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
