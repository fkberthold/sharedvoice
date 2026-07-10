"""Contract: the /auth router — register, login, logout, me (sv-dkl.3).

An APIRouter (prefix ``/auth``) wires four endpoints into ``create_app``:

POST /auth/register  {join_code, username, display_name, password}
    - 403 when join_code != SHAREDVOICE_JOIN_CODE, and NO user is created.
    - 409 when the username already exists.
    - else 201, sets the session cookie (logs the new user in), creates the
      user, and the FIRST successful registrant gets is_curator=True (the DB
      had zero users at insert), everyone after gets False.
      Body = {id, username, display_name, is_curator}.

POST /auth/login  {username, password}
    - 200 + cookie on correct creds. Body = {id, username, display_name,
      is_curator}.
    - 401 on wrong password.
    - 401 on unknown username, with the SAME body as the wrong-password case
      (no user-enumeration).

POST /auth/logout -> 204, clears the session; a subsequent /auth/me -> 401.

GET /auth/me -> 200 {id, username, display_name, is_curator} with a valid
    session cookie, 401 without.

RED until ``sharedvoice.routers.auth`` exists and ``create_app`` includes it.
Driven entirely through HTTP status codes so the RED is a behavior failure
(routes 404) rather than a collection error. The autouse conftest fixture
supplies SHAREDVOICE_SECRET_KEY + SHAREDVOICE_JOIN_CODE="test-join-code", so
the join code these tests send is "test-join-code".

TestClient (httpx) PERSISTS cookies within one client instance: a register or
login POST logs that client in, and a later /auth/me on the SAME client carries
the cookie. A FRESH TestClient is an unauthenticated / second-user context.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from sharedvoice import security, users
from sharedvoice.app import create_app
from sharedvoice.storage.db import connect

JOIN_CODE = "test-join-code"


def _app(tmp_path):
    return create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")


def _register_body(username, *, join_code=JOIN_CODE, display_name=None, password="pw"):
    return {
        "join_code": join_code,
        "username": username,
        "display_name": display_name or username.title(),
        "password": password,
    }


# --- register ------------------------------------------------------------

def test_register_wrong_join_code_403_and_no_user(tmp_path):
    app = _app(tmp_path)
    resp = TestClient(app).post("/auth/register", json=_register_body("alice", join_code="nope"))
    assert resp.status_code == 403

    conn = connect(tmp_path / "t.db")
    assert users.count_users(conn) == 0
    conn.close()


def test_register_first_user_is_curator_and_logs_in(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)  # persists the session cookie across requests

    resp = client.post("/auth/register", json=_register_body("alice"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_curator"] is True
    assert body["username"] == "alice"

    # Registering logged this client in: /auth/me works and returns the same id.
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_register_second_user_not_curator(tmp_path):
    app = _app(tmp_path)

    first = TestClient(app).post("/auth/register", json=_register_body("alice"))
    assert first.status_code == 201
    assert first.json()["is_curator"] is True

    # Fresh client -> second-user context, correct code, different username.
    second = TestClient(app).post("/auth/register", json=_register_body("bob"))
    assert second.status_code == 201
    assert second.json()["is_curator"] is False


def test_register_duplicate_username_409(tmp_path):
    app = _app(tmp_path)

    first = TestClient(app).post("/auth/register", json=_register_body("alice"))
    assert first.status_code == 201

    dup = TestClient(app).post("/auth/register", json=_register_body("alice"))
    assert dup.status_code == 409


# --- login ---------------------------------------------------------------

def test_login_correct_creds_200_and_logs_in(tmp_path):
    app = _app(tmp_path)
    TestClient(app).post("/auth/register", json=_register_body("alice", password="s3cret"))

    client = TestClient(app)  # fresh, unauthenticated context
    resp = client.post("/auth/login", json={"username": "alice", "password": "s3cret"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"

    # The login set the cookie on this client.
    assert client.get("/auth/me").status_code == 200


def test_login_wrong_password_401(tmp_path):
    app = _app(tmp_path)
    TestClient(app).post("/auth/register", json=_register_body("alice", password="s3cret"))

    resp = TestClient(app).post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_username_matches_wrong_password_body(tmp_path):
    app = _app(tmp_path)
    TestClient(app).post("/auth/register", json=_register_body("alice", password="s3cret"))

    wrong_pw = TestClient(app).post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    )
    unknown = TestClient(app).post(
        "/auth/login", json={"username": "ghost", "password": "whatever"}
    )
    assert wrong_pw.status_code == 401
    assert unknown.status_code == 401
    # Non-enumeration: the unknown-username response is indistinguishable.
    assert unknown.json() == wrong_pw.json()


def test_login_unknown_username_still_pays_verify_password_cost(tmp_path):
    """Timing side-channel guard (sv-9wi).

    The user-not-found path must still call ``security.verify_password``
    (against a fixed dummy hash) before returning 401, so an unknown
    username can't be distinguished from a wrong password by response
    latency. We can't assert on wall-clock time in CI (flaky), so instead
    we spy on the imported name in ``routers.auth`` and assert it's called
    exactly once even when the username doesn't exist at all.
    """
    app = _app(tmp_path)
    TestClient(app).post("/auth/register", json=_register_body("alice", password="s3cret"))

    with patch("sharedvoice.routers.auth.security.verify_password", wraps=security.verify_password) as spy:
        resp = TestClient(app).post(
            "/auth/login", json={"username": "ghost", "password": "whatever"}
        )
    assert resp.status_code == 401
    assert spy.call_count == 1


# --- logout --------------------------------------------------------------

def test_logout_clears_session(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    client.post("/auth/register", json=_register_body("alice"))
    assert client.get("/auth/me").status_code == 200

    logout = client.post("/auth/logout")
    assert logout.status_code == 204

    assert client.get("/auth/me").status_code == 401


# --- me ------------------------------------------------------------------

def test_me_without_cookie_401(tmp_path):
    app = _app(tmp_path)
    assert TestClient(app).get("/auth/me").status_code == 401


def test_me_with_cookie_returns_full_body(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    client.post("/auth/register", json=_register_body("alice"))

    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"id", "username", "display_name", "is_curator"}
