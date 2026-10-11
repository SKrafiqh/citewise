import pytest

from app.assess.selection import apportion, select_questions


def test_apportion_largest_remainder():
    assert apportion({"mcq": 6, "short": 2, "numerical": 2}, 10) == ["mcq"] * 6 + ["numerical"] * 2 + ["short"] * 2
    assert len(apportion({"mcq": 1, "short": 1, "numerical": 1}, 10)) == 10
    assert apportion({"mcq": 1}, 3) == ["mcq"] * 3
    with pytest.raises(ValueError):
        apportion({"mcq": 0}, 3)


def q(qid, qtype="mcq", difficulty=0.5, emb=(1.0, 0.0)):
    return {"id": qid, "qtype": qtype, "difficulty": difficulty, "embedding": list(emb)}


def run(bank, qtypes, seen=None, dup=lambda new, seen: False, order=None):
    order = order or sorted(bank)
    return select_questions(
        bank, qtypes,
        next_concept=lambda excluded: next((c for c in order if c not in excluded), None),
        target_p=lambda c: 0.3, seen_ids=seen or set(), seen_embeddings=[], is_duplicate=dup,
    )


def test_spreads_over_concepts_first_then_repeats():
    bank = {"a": [q("a1"), q("a2"), q("a3")], "b": [q("b1")]}
    chosen, short = run(bank, ["mcq"] * 4)
    assert [c["id"] for c in chosen] == ["a1", "a2", "b1", "a3"] and short == 0


def test_skips_seen_and_prefers_type_then_difficulty():
    bank = {"a": [q("a1", "short", 0.3), q("a2", "mcq", 0.9), q("a3", "mcq", 0.4)]}
    chosen, _ = run(bank, ["mcq", "short"], seen={"a3"})
    assert [c["id"] for c in chosen] == ["a2", "a1"]


def test_duplicates_are_skipped_and_shortfall_reported():
    bank = {"a": [q("a1", emb=(1, 0)), q("a2", emb=(1, 0.01)), q("a3", emb=(0, 1))]}
    dup = lambda new, seen: any(abs(new[0] * s[0] + new[1] * s[1]) > 0.9 for s in seen)
    chosen, short = run(bank, ["mcq"] * 3, dup=dup)
    assert [c["id"] for c in chosen] == ["a1", "a3"] and short == 1


def test_empty_bank_is_all_shortfall():
    assert run({}, ["mcq"] * 2, order=[]) == ([], 2)
