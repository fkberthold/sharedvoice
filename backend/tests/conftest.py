"""Suite-wide test fixtures.

``create_app`` fails fast when ``SHAREDVOICE_SECRET_KEY`` is unset (sv-dkl.2).
This autouse fixture supplies that key (plus the join code) for every test so
the pre-existing suite keeps constructing apps without env boilerplate. Tests
that exercise the fail-fast path delete the key themselves via monkeypatch.

It also pins ``SHAREDVOICE_BCRYPT_ROUNDS`` to bcrypt's minimum (4) so real
password hashing in register/login tests stays fast (sv-1x1); production
leaves the env var unset and gets bcrypt's own default (12).
"""

import pytest
from fastapi.testclient import TestClient

from sharedvoice.app import create_app


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setenv("SHAREDVOICE_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SHAREDVOICE_JOIN_CODE", "test-join-code")
    monkeypatch.setenv("SHAREDVOICE_BCRYPT_ROUNDS", "4")


@pytest.fixture
def authed_client(tmp_path):
    """A ``TestClient`` that has registered (and is therefore logged in).

    The app is built at ``tmp_path/"t.db"`` (blobs at ``tmp_path/"blobs"``) so a
    test can also ``connect(tmp_path/"t.db")`` for direct DB setup and hit the
    same app through this cookie-bearing client. Registering logs the client in
    via the session cookie, so its subsequent requests carry authentication.
    """
    app = create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")
    client = TestClient(app)
    resp = client.post(
        "/auth/register",
        json={
            "join_code": "test-join-code",
            "username": "tester",
            "display_name": "Tester",
            "password": "pw",
        },
    )
    assert resp.status_code == 201
    return client
