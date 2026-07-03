"""Contract: audio-blob storage behind an interface (local FS now, object
store later) + a SQLite connection helper for metadata.

The blob store is the abstraction that must be swappable without touching
the pipeline; the SQLite helper is the metadata mechanism (schema lands
with the data model in sv-lds.4). RED until storage/ exists.
"""

import pytest

from sharedvoice.storage import db
from sharedvoice.storage.base import BlobStore
from sharedvoice.storage.local import LocalBlobStore


def test_local_blob_store_satisfies_protocol(tmp_path):
    assert isinstance(LocalBlobStore(tmp_path), BlobStore)


def test_blob_round_trip(tmp_path):
    store = LocalBlobStore(tmp_path)
    store.put("roots/a1.wav", b"\x00\x01\x02")
    assert store.exists("roots/a1.wav")
    assert store.get("roots/a1.wav") == b"\x00\x01\x02"
    assert store.path("roots/a1.wav").read_bytes() == b"\x00\x01\x02"


def test_get_missing_raises_keyerror(tmp_path):
    with pytest.raises(KeyError):
        LocalBlobStore(tmp_path).get("nope.wav")


def test_delete_removes_blob(tmp_path):
    store = LocalBlobStore(tmp_path)
    store.put("t.wav", b"x")
    store.delete("t.wav")
    assert not store.exists("t.wav")


def test_delete_missing_raises_keyerror(tmp_path):
    with pytest.raises(KeyError):
        LocalBlobStore(tmp_path).delete("nope.wav")


def test_key_traversal_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        LocalBlobStore(tmp_path).put("../escape.wav", b"x")


def test_db_connect_round_trip(tmp_path):
    conn = db.connect(tmp_path / "meta.db")
    conn.executescript("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO t (name) VALUES (?)", ("hello",))
    conn.commit()
    assert conn.execute("SELECT name FROM t").fetchone()["name"] == "hello"
    conn.close()
