"""Contract: session cookie + auth dependencies.

Pins the sv-dkl.2 surface:
- ``create_app`` fails fast (RuntimeError) when SHAREDVOICE_SECRET_KEY is unset.
- ``create_app`` installs starlette SessionMiddleware keyed by that env, so a
  route may stash ``request.session["user_id"]`` and later requests recover it.
- ``dependencies.current_user`` loads the session user via
  ``users.get_user_by_id``; 401 when there is no session or the id is unknown.
- ``dependencies.require_curator`` 403s a non-curator, passes a curator.

RED until ``sharedvoice.dependencies`` exists and ``create_app`` wires the
SessionMiddleware + fail-fast. The probe routes below are appended to the app
under test (routes may be added until the first request) so the deps are
exercised end-to-end through a real TestClient session cookie.
"""

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient

from sharedvoice import users
from sharedvoice.app import create_app
from sharedvoice.dependencies import current_user, require_curator
from sharedvoice.storage.db import connect
from sharedvoice.users import User


def _probe_app(tmp_path):
    """Build the app, seed nothing, and bolt on three probe routes.

    Routes are attached before the first request (TestClient is constructed by
    the caller), which is legal in Starlette. Each probe drives one dependency.
    """
    app = create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")

    @app.post("/_probe/login/{user_id}")
    def _login(request: Request, user_id: str) -> dict:
        request.session["user_id"] = user_id
        return {"ok": True}

    @app.get("/_probe/me")
    def _me(user: User = Depends(current_user)) -> dict:
        return {"id": user.id, "is_curator": user.is_curator}

    @app.get("/_probe/curator")
    def _curator(user: User = Depends(require_curator)) -> dict:
        return {"id": user.id}

    return app


def _seed_user(tmp_path, *, user_id: str, is_curator: bool) -> None:
    conn = connect(tmp_path / "t.db")
    users.create_user(
        conn,
        User(
            id=user_id,
            username=user_id,
            display_name=user_id.title(),
            password_hash="x",
            is_curator=is_curator,
        ),
    )
    conn.close()


def test_no_session_is_401(tmp_path):
    # Fresh client with no login POST -> no session cookie -> unauthenticated.
    client = TestClient(_probe_app(tmp_path))
    assert client.get("/_probe/me").status_code == 401


def test_logged_in_regular_user_me(tmp_path):
    app = _probe_app(tmp_path)
    _seed_user(tmp_path, user_id="u1", is_curator=False)

    client = TestClient(app)  # persists the session cookie across requests
    assert client.post("/_probe/login/u1").status_code == 200

    resp = client.get("/_probe/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "u1"
    assert body["is_curator"] is False


def test_regular_user_forbidden_from_curator(tmp_path):
    app = _probe_app(tmp_path)
    _seed_user(tmp_path, user_id="u1", is_curator=False)

    client = TestClient(app)
    client.post("/_probe/login/u1")
    assert client.get("/_probe/curator").status_code == 403


def test_curator_allowed(tmp_path):
    app = _probe_app(tmp_path)
    _seed_user(tmp_path, user_id="c1", is_curator=True)

    client = TestClient(app)
    client.post("/_probe/login/c1")

    resp = client.get("/_probe/curator")
    assert resp.status_code == 200
    assert resp.json()["id"] == "c1"


def test_unknown_session_user_is_401(tmp_path):
    # Session points at a user_id that was never persisted (stale cookie).
    app = _probe_app(tmp_path)
    client = TestClient(app)
    client.post("/_probe/login/ghost")
    assert client.get("/_probe/me").status_code == 401


def test_missing_secret_key_fails_fast(tmp_path, monkeypatch):
    monkeypatch.delenv("SHAREDVOICE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app(tmp_path / "a.db", tmp_path / "b")
