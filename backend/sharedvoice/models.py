"""Data model — Affirmation + Recording (root) — and their SQLite DAO.

Schema lives here; the connection (Row factory + foreign_keys ON) comes
from ``sharedvoice.storage.db.connect``. Take + MixRequest arrive later
(P1/P3). SQL column names ``sort_order`` / ``set_name`` avoid the ``order``
/ ``set`` reserved words; the dataclass fields keep the brief's vocabulary.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass
class Affirmation:
    id: str
    title: str
    body_text: str = ""
    order: int = 0
    set: str | None = None  # 'morning' | 'evening' | None
    root_recording_id: str | None = None


@dataclass
class Recording:
    id: str
    affirmation_id: str
    audio_path: str
    sample_rate: int
    duration: float
    phrase_boundaries: list[float] | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS affirmations (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    body_text         TEXT NOT NULL DEFAULT '',
    sort_order        INTEGER NOT NULL DEFAULT 0,
    set_name          TEXT,
    root_recording_id TEXT REFERENCES recordings(id)
);

CREATE TABLE IF NOT EXISTS recordings (
    id                TEXT PRIMARY KEY,
    affirmation_id    TEXT NOT NULL REFERENCES affirmations(id),
    audio_path        TEXT NOT NULL,
    sample_rate       INTEGER NOT NULL,
    duration          REAL NOT NULL,
    phrase_boundaries TEXT
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# --- Affirmation DAO ---------------------------------------------------

def _affirmation_from_row(row: sqlite3.Row) -> Affirmation:
    return Affirmation(
        id=row["id"],
        title=row["title"],
        body_text=row["body_text"],
        order=row["sort_order"],
        set=row["set_name"],
        root_recording_id=row["root_recording_id"],
    )


def add_affirmation(conn: sqlite3.Connection, a: Affirmation) -> None:
    conn.execute(
        "INSERT INTO affirmations "
        "(id, title, body_text, sort_order, set_name, root_recording_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (a.id, a.title, a.body_text, a.order, a.set, a.root_recording_id),
    )
    conn.commit()


def get_affirmation(conn: sqlite3.Connection, affirmation_id: str) -> Affirmation | None:
    row = conn.execute(
        "SELECT * FROM affirmations WHERE id = ?", (affirmation_id,)
    ).fetchone()
    return _affirmation_from_row(row) if row else None


def list_affirmations(conn: sqlite3.Connection) -> list[Affirmation]:
    rows = conn.execute(
        "SELECT * FROM affirmations ORDER BY sort_order, id"
    ).fetchall()
    return [_affirmation_from_row(r) for r in rows]


def set_root_recording(
    conn: sqlite3.Connection, affirmation_id: str, recording_id: str
) -> None:
    conn.execute(
        "UPDATE affirmations SET root_recording_id = ? WHERE id = ?",
        (recording_id, affirmation_id),
    )
    conn.commit()


# --- Recording DAO -----------------------------------------------------

def _recording_from_row(row: sqlite3.Row) -> Recording:
    pb = row["phrase_boundaries"]
    return Recording(
        id=row["id"],
        affirmation_id=row["affirmation_id"],
        audio_path=row["audio_path"],
        sample_rate=row["sample_rate"],
        duration=row["duration"],
        phrase_boundaries=json.loads(pb) if pb is not None else None,
    )


def add_recording(conn: sqlite3.Connection, r: Recording) -> None:
    pb = json.dumps(r.phrase_boundaries) if r.phrase_boundaries is not None else None
    conn.execute(
        "INSERT INTO recordings "
        "(id, affirmation_id, audio_path, sample_rate, duration, phrase_boundaries) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (r.id, r.affirmation_id, r.audio_path, r.sample_rate, r.duration, pb),
    )
    conn.commit()


def get_recording(conn: sqlite3.Connection, recording_id: str) -> Recording | None:
    row = conn.execute(
        "SELECT * FROM recordings WHERE id = ?", (recording_id,)
    ).fetchone()
    return _recording_from_row(row) if row else None
