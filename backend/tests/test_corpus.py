"""Contract: the affirmation corpus loads from data/affirmations.yaml as
16 ordered Affirmations with resolvable morning/evening sets and real
(non-placeholder) body text. RED until corpus.py exists.
"""

from sharedvoice.corpus import load_affirmations


def _by_id():
    return {a.id: a for a in load_affirmations()}


def test_corpus_has_16():
    assert len(load_affirmations()) == 16


def test_ids_are_unique():
    affs = load_affirmations()
    assert len({a.id for a in affs}) == 16


def test_orders_are_1_through_16():
    assert [a.order for a in load_affirmations()] == list(range(1, 17))


def test_all_bodies_are_nonempty():
    assert all(a.body_text.strip() for a in load_affirmations())


def test_morning_set_resolves():
    by = _by_id()
    assert by["waking"].set == "morning"
    assert by["morning-community"].set == "morning"
    assert by["my-path"].set == "morning"


def test_evening_affirmation_dropped():
    # The Evening Affirmation is not on Ven. Tarpa's Refuge recording, so it
    # was dropped — the recording is the source of truth. No evening set remains.
    affs = load_affirmations()
    assert "evening" not in {a.id for a in affs}
    assert all(a.set != "evening" for a in affs)


def test_known_titles_present():
    titles = {a.title for a in load_affirmations()}
    assert {
        "Waking Affirmation",
        "The Five Remembrances",
        "Pledge of Daily Practice and Commitments",
    } <= titles


def test_mental_discipline_anaphora_preserved():
    # Five identical "I will no longer allow" line-openings — exactly the
    # repetition the aligner's +/-1s window guard must not mis-lock onto.
    body = _by_id()["mental-discipline"].body_text
    assert body.count("I will no longer allow") == 5


def test_four_noble_truths_ends_at_eightfold_path():
    # The daily-practice pledge that used to tail this affirmation is now its
    # own entry (the recording announces it separately), so the Four Noble
    # Truths body ends at the Eightfold Path and no longer carries the vows.
    body = _by_id()["four-noble-truths"].body_text
    assert "Right concentration" in body
    assert "I vow, to uphold my daily training" not in body


def test_pledge_of_daily_practice_split_out():
    # Split out of four-noble-truths to match the recording; order 16 (the
    # slot the dropped Evening Affirmation vacated).
    pledge = _by_id()["pledge-of-daily-practice"]
    assert pledge.order == 16
    assert pledge.title == "Pledge of Daily Practice and Commitments"
    assert "I vow, to uphold my daily training" in pledge.body_text
    assert "To purify my vows monthly" in pledge.body_text
