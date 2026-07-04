"""Data model — User (root) — and its SQLite DAO.

Mirrors the flat-module shape of ``sharedvoice.models``: dataclass +
module-level SCHEMA + ``init_user_schema`` + free DAO funcs taking ``conn``
first. Hashing-agnostic on purpose — ``create_user`` persists whatever
``password_hash`` it is given; hashing lives in ``sharedvoice.security``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field


@dataclass
class User:
    id: str
    username: str
    display_name: str
    password_hash: str
    is_curator: bool = False
    settings: dict = field(default_factory=dict)
    created_at: str | None = None


USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_curator    INTEGER NOT NULL DEFAULT 0,
    settings      TEXT NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_user_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(USER_SCHEMA)
    conn.commit()


# --- User DAO ------------------------------------------------------------

def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        password_hash=row["password_hash"],
        is_curator=bool(row["is_curator"]),
        settings=json.loads(row["settings"]),
        created_at=row["created_at"],
    )


def create_user(conn: sqlite3.Connection, u: User) -> None:
    settings = json.dumps(u.settings)
    if u.created_at is None:
        conn.execute(
            "INSERT INTO users "
            "(id, username, display_name, password_hash, is_curator, settings) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (u.id, u.username, u.display_name, u.password_hash, int(u.is_curator), settings),
        )
    else:
        conn.execute(
            "INSERT INTO users "
            "(id, username, display_name, password_hash, is_curator, settings, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                u.id,
                u.username,
                u.display_name,
                u.password_hash,
                int(u.is_curator),
                settings,
                u.created_at,
            ),
        )
    conn.commit()


def get_user_by_username(conn: sqlite3.Connection, username: str) -> User | None:
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return _user_from_row(row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> User | None:
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return _user_from_row(row) if row else None


def count_users(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return row["n"]
