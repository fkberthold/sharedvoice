"""Contract: User persists to SQLite and round-trips through the DAO.

Pins the ``User`` dataclass, ``USER_SCHEMA`` (unique username), the flat DAO
funcs (create/get_by_username/get_by_id/count), and that ``USER_SCHEMA`` is
wired into ``create_app``. The DAO is hashing-agnostic — it stores whatever
``password_hash`` it is given. RED until users.py exists.
"""

import sqlite3

import pytest

from sharedvoice import users
from sharedvoice.app import create_app
from sharedvoice.storage.db import connect
from sharedvoice.users import User


def _db(tmp_path):
    conn = connect(tmp_path / "u.db")
    users.init_user_schema(conn)
    return conn


def _assert_user_fields_eq(got: User, want: User) -> None:
    # created_at is DB-generated, so round-trip only the caller-controlled fields.
    assert got.id == want.id
    assert got.username == want.username
    assert got.display_name == want.display_name
    assert got.password_hash == want.password_hash
    assert got.is_curator == want.is_curator
    assert got.settings == want.settings


def test_count_users_starts_empty(tmp_path):
    conn = _db(tmp_path)
    assert users.count_users(conn) == 0


def test_create_and_get_by_username_defaults(tmp_path):
    conn = _db(tmp_path)
    u = User(id="u1", username="alice", display_name="Alice", password_hash="h")
    users.create_user(conn, u)

    got = users.get_user_by_username(conn, "alice")
    _assert_user_fields_eq(got, u)
    assert got.is_curator is False
    assert type(got.is_curator) is bool
    assert got.settings == {}
    assert isinstance(got.settings, dict)


def test_create_preserves_curator_and_settings(tmp_path):
    conn = _db(tmp_path)
    u = User(
        id="u2",
        username="bob",
        display_name="Bob",
        password_hash="h",
        is_curator=True,
        settings={"theme": "dark"},
    )
    users.create_user(conn, u)

    got = users.get_user_by_username(conn, "bob")
    assert got.is_curator is True
    assert type(got.is_curator) is bool
    assert got.settings == {"theme": "dark"}
    assert isinstance(got.settings, dict)


def test_get_by_id_round_trip(tmp_path):
    conn = _db(tmp_path)
    u = User(id="u3", username="carol", display_name="Carol", password_hash="h")
    users.create_user(conn, u)

    got = users.get_user_by_id(conn, "u3")
    _assert_user_fields_eq(got, u)


def test_count_users_increments(tmp_path):
    conn = _db(tmp_path)
    assert users.count_users(conn) == 0
    users.create_user(conn, User(id="u1", username="alice", display_name="Alice", password_hash="h"))
    assert users.count_users(conn) == 1
    users.create_user(conn, User(id="u2", username="bob", display_name="Bob", password_hash="h"))
    assert users.count_users(conn) == 2


def test_duplicate_username_rejected(tmp_path):
    conn = _db(tmp_path)
    users.create_user(conn, User(id="u1", username="alice", display_name="Alice", password_hash="h"))
    with pytest.raises(sqlite3.IntegrityError):
        users.create_user(conn, User(id="u2", username="alice", display_name="Other", password_hash="h"))


def test_get_by_username_missing_returns_none(tmp_path):
    conn = _db(tmp_path)
    assert users.get_user_by_username(conn, "missing") is None


def test_created_at_is_db_generated(tmp_path):
    conn = _db(tmp_path)
    u = User(id="u1", username="alice", display_name="Alice", password_hash="h", created_at=None)
    users.create_user(conn, u)
    got = users.get_user_by_username(conn, "alice")
    assert got.created_at is not None


def test_user_schema_wired_into_create_app(tmp_path):
    create_app(tmp_path / "app.db", tmp_path / "blobs")
    conn = connect(tmp_path / "app.db")
    assert users.count_users(conn) == 0
