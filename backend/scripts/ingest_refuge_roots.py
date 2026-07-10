"""Ingest Ven. Tarpa's Refuge.mp3 into per-affirmation root recordings.

Glue over two independently-built, independently-tested tools (sv-lds.20):
``sharedvoice.audio.segment.cut_segments`` (ffmpeg-based splitter) and
``sharedvoice.audio.root_ingest_batch.ingest_root_clips`` (batch ingest,
reusing sv-lds.7's resample/store pipeline). Reads the committed cut points
at ``data/refuge_split.yaml``, splits the source recording into a temporary
directory of per-affirmation clips, and ingests them as root Recordings.

The source recording itself is NOT committed to this repo (sensitive voice
content) -- pass its local path via --source, or rely on the default
(~/Downloads/Refuge.mp3).

Usage (from repo root, main venv):
    .venv/bin/python backend/scripts/ingest_refuge_roots.py
    .venv/bin/python backend/scripts/ingest_refuge_roots.py --source /path/to/Refuge.mp3
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import yaml

from sharedvoice import models
from sharedvoice.audio.root_ingest_batch import ingest_root_clips
from sharedvoice.audio.segment import cut_segments
from sharedvoice.storage.db import connect
from sharedvoice.storage.local import LocalBlobStore

REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT_FILE = REPO_ROOT / "data" / "refuge_split.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / "Downloads" / "Refuge.mp3")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "backend" / "var" / "sharedvoice.db")
    parser.add_argument("--blobs", type=Path, default=REPO_ROOT / "backend" / "var" / "blobs")
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(f"source recording not found: {args.source}")

    split = yaml.safe_load(SPLIT_FILE.read_text(encoding="utf-8"))
    segments = split["segments"]

    conn = connect(args.db)
    models.init_schema(conn)
    storage = LocalBlobStore(args.blobs)

    with tempfile.TemporaryDirectory() as tmp:
        clips_dir = Path(tmp)
        cut_segments(args.source, segments, clips_dir)
        ingested = ingest_root_clips(conn, storage, clips_dir)

    all_ids = {s["id"] for s in segments}
    missing = sorted(all_ids - set(ingested))
    print(f"Ingested {len(ingested)}/{len(all_ids)} roots.")
    if missing:
        print(f"MISSING (not ingested -- no matching affirmation id in the DB): {missing}")

    conn.close()


if __name__ == "__main__":
    main()
