"""Contract: the app exposes a health endpoint for liveness checks.

GET /health -> 200 with a small JSON status body. This pins the app
factory (create_app) and the healthcheck surface; it is RED until the
skeleton exists.
"""

from fastapi.testclient import TestClient

from sharedvoice.app import create_app


def test_health_returns_ok(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs"))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
