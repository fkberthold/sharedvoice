"""Contract: the API seeds + serves the affirmation corpus, and serves a
root recording when one exists.

GET /affirmations            -> 200, 16 items ordered by order
GET /affirmations/{id}       -> 200 one affirmation | 404
GET /affirmations/{id}/root  -> 200 audio bytes | 404 when no root
"""

from fastapi.testclient import TestClient

from sharedvoice import models
from sharedvoice.app import create_app
from sharedvoice.storage.db import connect


def _app(tmp_path):
    return create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")


def test_list_returns_16(tmp_path):
    resp = TestClient(_app(tmp_path)).get("/affirmations")
    assert resp.status_code == 200
    assert len(resp.json()) == 16


def test_list_is_ordered(tmp_path):
    data = TestClient(_app(tmp_path)).get("/affirmations").json()
    assert [a["order"] for a in data] == list(range(1, 17))
    assert data[0]["id"] == "waking"


def test_get_one_affirmation(tmp_path):
    resp = TestClient(_app(tmp_path)).get("/affirmations/waking")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Waking Affirmation"
    assert "precious human life" in body["body_text"]


def test_get_missing_affirmation_404(tmp_path):
    assert TestClient(_app(tmp_path)).get("/affirmations/nope").status_code == 404


def test_root_404_when_absent(tmp_path):
    assert TestClient(_app(tmp_path)).get("/affirmations/waking/root").status_code == 404


def test_root_served_when_present(tmp_path):
    db_path = tmp_path / "t.db"
    blobs = tmp_path / "blobs"
    app = create_app(db_path=db_path, storage_root=blobs)

    # Attach a root recording + blob directly (upload endpoint arrives in sv-lds.7).
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

    resp = TestClient(app).get("/affirmations/waking/root")
    assert resp.status_code == 200
    assert resp.content == b"RIFFfake-wav"
