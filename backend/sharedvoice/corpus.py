"""Load + seed the affirmation corpus from ``data/affirmations.yaml``.

The corpus is data, not code. ``attribution`` is preserved in the YAML but
not carried on the Affirmation model yet (no display need in Phase 0).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from . import models
from .models import Affirmation

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "affirmations.yaml"


def load_affirmations(path: Path | str = DEFAULT_CORPUS) -> list[Affirmation]:
    """Return the corpus as Affirmations, ordered by ``order``."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    affirmations = [
        Affirmation(
            id=entry["id"],
            title=entry["title"],
            body_text=entry.get("body_text", ""),
            order=entry["order"],
            set=entry.get("set"),
        )
        for entry in data["affirmations"]
    ]
    return sorted(affirmations, key=lambda a: a.order)


def seed_affirmations(conn: sqlite3.Connection, path: Path | str = DEFAULT_CORPUS) -> None:
    """Insert corpus affirmations not already present (idempotent)."""
    existing = {a.id for a in models.list_affirmations(conn)}
    for affirmation in load_affirmations(path):
        if affirmation.id not in existing:
            models.add_affirmation(conn, affirmation)
