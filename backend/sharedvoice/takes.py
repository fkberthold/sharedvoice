"""Data model — Take — and its SQLite DAO (sv-lds.14).

Mirrors the flat-module shape of ``sharedvoice.users``: dataclass +
module-level SCHEMA + ``init_take_schema`` + free DAO funcs taking ``conn``
first.

A Take is a sangha member's recitation-along recording for one affirmation.
``user_id`` is stamped from the authenticated uploader (``current_user``,
sv-dkl) — it is the FK future self-delete authorization (a take belongs to
its uploader) will hang off, though that authorization check is out of scope
for this bead. ``alignment`` is a nullable placeholder column: the real
aligner is sv-lds.15, still blocked/future work, and simply leaves this
``NULL`` for now.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass
class Take:
    id: str
    affirmation_id: str
    user_id: str
    contributor_name: str
    audio_path: str
    alignment: dict | list | None = None
    created_at: str | None = None


TAKE_SCHEMA = """
CREATE TABLE IF NOT EXISTS takes (
    id               TEXT PRIMARY KEY,
    affirmation_id   TEXT NOT NULL REFERENCES affirmations(id),
    user_id          TEXT NOT NULL REFERENCES users(id),
    contributor_name TEXT NOT NULL,
    audio_path       TEXT NOT NULL,
    alignment        TEXT,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_take_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(TAKE_SCHEMA)
    conn.commit()


# --- Take DAO --------------------------------------------------------------

def _take_from_row(row: sqlite3.Row) -> Take:
    alignment = row["alignment"]
    return Take(
        id=row["id"],
        affirmation_id=row["affirmation_id"],
        user_id=row["user_id"],
        contributor_name=row["contributor_name"],
        audio_path=row["audio_path"],
        alignment=json.loads(alignment) if alignment is not None else None,
        created_at=row["created_at"],
    )


def create_take(conn: sqlite3.Connection, t: Take) -> None:
    alignment = json.dumps(t.alignment) if t.alignment is not None else None
    if t.created_at is None:
        conn.execute(
            "INSERT INTO takes "
            "(id, affirmation_id, user_id, contributor_name, audio_path, alignment) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (t.id, t.affirmation_id, t.user_id, t.contributor_name, t.audio_path, alignment),
        )
    else:
        conn.execute(
            "INSERT INTO takes "
            "(id, affirmation_id, user_id, contributor_name, audio_path, alignment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                t.id,
                t.affirmation_id,
                t.user_id,
                t.contributor_name,
                t.audio_path,
                alignment,
                t.created_at,
            ),
        )
    conn.commit()


def get_take(conn: sqlite3.Connection, take_id: str) -> Take | None:
    row = conn.execute(
        "SELECT * FROM takes WHERE id = ?", (take_id,)
    ).fetchone()
    return _take_from_row(row) if row else None


def list_takes_by_affirmation(conn: sqlite3.Connection, affirmation_id: str) -> list[Take]:
    """All takes uploaded for `affirmation_id`, oldest first (used by the
    mix endpoint, sv-lds.17, to gather every contributor track to align +
    sum alongside the root)."""
    rows = conn.execute(
        "SELECT * FROM takes WHERE affirmation_id = ? ORDER BY created_at, id",
        (affirmation_id,),
    ).fetchall()
    return [_take_from_row(r) for r in rows]
