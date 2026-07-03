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


def test_evening_set_resolves():
    assert _by_id()["evening"].set == "evening"


def test_known_titles_present():
    titles = {a.title for a in load_affirmations()}
    assert {"Waking Affirmation", "The Five Remembrances", "Evening Affirmation"} <= titles


def test_mental_discipline_anaphora_preserved():
    # Five identical "I will no longer allow" line-openings — exactly the
    # repetition the aligner's +/-1s window guard must not mis-lock onto.
    body = _by_id()["mental-discipline"].body_text
    assert body.count("I will no longer allow") == 5
