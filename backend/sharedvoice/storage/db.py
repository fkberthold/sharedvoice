"""SQLite connection helper for metadata.

Thin on purpose: the schema (Affirmation / Recording / Take tables) lands
with the data model in sv-lds.4. This just gives a consistent connection
(Row factory + foreign keys on).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
