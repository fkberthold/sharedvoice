"""Contract: Affirmation + Recording persist to SQLite and round-trip.

Pins the schema, the dataclasses, and the DAO functions (add/get/list +
set_root_recording), including FK enforcement. RED until models.py exists.
"""

import sqlite3

import pytest

from sharedvoice import models
from sharedvoice.models import Affirmation, Recording
from sharedvoice.storage.db import connect


def _db(tmp_path):
    conn = connect(tmp_path / "m.db")
    models.init_schema(conn)
    return conn


def test_affirmation_round_trip(tmp_path):
    conn = _db(tmp_path)
    a = Affirmation(id="waking", title="Waking Affirmation", body_text="I wake.", order=1, set="morning")
    models.add_affirmation(conn, a)
    assert models.get_affirmation(conn, "waking") == a


def test_recording_round_trip(tmp_path):
    conn = _db(tmp_path)
    models.add_affirmation(conn, Affirmation(id="waking", title="Waking"))
    r = Recording(
        id="rec1",
        affirmation_id="waking",
        audio_path="roots/rec1.wav",
        sample_rate=48000,
        duration=12.5,
        phrase_boundaries=[0.0, 3.2, 6.4],
    )
    models.add_recording(conn, r)
    assert models.get_recording(conn, "rec1") == r


def test_set_root_recording(tmp_path):
    conn = _db(tmp_path)
    models.add_affirmation(conn, Affirmation(id="waking", title="Waking"))
    models.add_recording(
        conn,
        Recording(id="rec1", affirmation_id="waking", audio_path="p", sample_rate=48000, duration=1.0),
    )
    models.set_root_recording(conn, "waking", "rec1")
    assert models.get_affirmation(conn, "waking").root_recording_id == "rec1"


def test_get_missing_affirmation_returns_none(tmp_path):
    assert models.get_affirmation(_db(tmp_path), "nope") is None


def test_list_affirmations_is_ordered(tmp_path):
    conn = _db(tmp_path)
    models.add_affirmation(conn, Affirmation(id="evening", title="Evening", order=2, set="evening"))
    models.add_affirmation(conn, Affirmation(id="waking", title="Waking", order=1, set="morning"))
    assert [a.id for a in models.list_affirmations(conn)] == ["waking", "evening"]


def test_recording_fk_violation_rejected(tmp_path):
    conn = _db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        models.add_recording(
            conn,
            Recording(id="x", affirmation_id="ghost", audio_path="p", sample_rate=48000, duration=1.0),
        )
