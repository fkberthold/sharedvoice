"""Contract: data/refuge_split.yaml holds the cut points that carve Ven.
Tarpa's combined Refuge.mp3 into per-affirmation root recordings. Every
segment id must resolve to a real corpus affirmation, and starts must be
strictly ascending — each segment runs to the next start; the last to EOF.
The mp3 itself is NOT committed (sensitive voice); only the numeric cut
points live here. Consumed by sv-lds.20.
"""

from pathlib import Path

import yaml

from sharedvoice.corpus import load_affirmations

SPLIT_FILE = Path(__file__).resolve().parents[2] / "data" / "refuge_split.yaml"


def _split():
    return yaml.safe_load(SPLIT_FILE.read_text(encoding="utf-8"))


def test_split_file_parses_with_source_and_segments():
    data = _split()
    assert data["source"]  # the (uncommitted) source recording name
    assert len(data["segments"]) == 16


def test_every_segment_id_is_a_real_affirmation():
    ids = {a.id for a in load_affirmations()}
    seg_ids = [s["id"] for s in _split()["segments"]]
    # Exact cover: every recorded segment maps to an affirmation, and every
    # affirmation is recorded (no orphan ids on either side).
    assert set(seg_ids) == ids


def test_segment_starts_are_strictly_ascending():
    starts = [s["start"] for s in _split()["segments"]]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)  # no duplicate cut points
