import random

import pytest

from eval import simulate


def fake_update(p, correct, params, weight=1.0):
    """Stand-in for the reserved BKT update: standard formulas, used only to test the harness."""
    num = p * (1 - params.p_slip) if correct else p * params.p_slip
    den = num + ((1 - p) * params.p_guess if correct else (1 - p) * (1 - params.p_guess))
    full = num / den + (1 - num / den) * params.p_learn
    return p + weight * (full - p)


def never_dup(new, seen):
    return False


@pytest.fixture
def bank():
    concepts = [f"c{i}" for i in range(6)]
    questions = [
        {"id": f"q{i}_{j}", "concept_id": c, "qtype": "mcq", "difficulty": 0.2 + 0.2 * j, "n_options": 4, "embedding": [float(i), float(j)]}
        for i, c in enumerate(concepts) for j in range(4)
    ]
    return {"concepts": concepts, "prereqs": {c: ([concepts[i - 1]] if i else []) for i, c in enumerate(concepts)},
            "topic_of": {c: "t1" if i < 3 else "t2" for i, c in enumerate(concepts)}, "questions": questions}


def test_profiles_initial_knowledge(bank):
    rng = random.Random(0)
    assert sum(simulate.initial_knowledge("strong", bank, rng).values()) >= 3
    weak = simulate.initial_knowledge("weak_foundations", bank, random.Random(0))
    assert not any(weak[c] for c in bank["concepts"][:-1])  # every non-leaf concept is a prerequisite
    uneven = simulate.initial_knowledge("uneven", bank, random.Random(0))
    assert len({v for c, v in uneven.items() if bank["topic_of"][c] == "t1"}) == 1


def test_run_student_is_deterministic_and_never_repeats_ids(bank):
    profile = simulate.PROFILES[0]
    a = simulate.run_student(profile, 3, "adaptive", bank, fake_update, never_dup, sessions=3, per_session=5)
    b = simulate.run_student(profile, 3, "adaptive", bank, fake_update, never_dup, sessions=3, per_session=5)
    assert a["rows"] == b["rows"] and len(a["rows"]) == 3
    assert 0 <= a["repetition"] <= 1 and all(0 <= r["mae"] <= 1 for r in a["rows"])


def test_both_policies_share_hidden_truth(bank):
    profile = simulate.PROFILES[1]
    ad = simulate.run_student(profile, 1, "adaptive", bank, fake_update, never_dup, sessions=1, per_session=1)
    rd = simulate.run_student(profile, 1, "random", bank, fake_update, never_dup, sessions=1, per_session=1)
    assert ad["rows"][0]["known_share"] == pytest.approx(rd["rows"][0]["known_share"], abs=0.2)


def test_repetition_counts_duplicates(bank):
    always = simulate.run_student(simulate.PROFILES[0], 0, "random", bank, fake_update, lambda n, s: bool(s), sessions=1, per_session=4)
    assert always["repetition"] == 0.75  # first question has nothing to repeat


def test_exhausted_bank_stops_cleanly(bank):
    run = simulate.run_student(simulate.PROFILES[0], 0, "adaptive", bank, fake_update, never_dup, sessions=10, per_session=10)
    assert len(run["rows"]) == 10  # 24 questions, 100 slots: later sessions are simply empty


def test_fit_bkt_recovers_high_learning_rate():
    rng = random.Random(1)
    seqs = []
    for _ in range(300):
        known, seq = False, []
        for _ in range(8):
            correct = rng.random() < (0.9 if known else 0.25)
            seq.append((correct, 0.25))
            known = known or rng.random() < 0.3
        seqs.append(seq)
    t, s = simulate.fit_bkt(seqs)
    assert 0.15 <= t <= 0.4 and s <= 0.2


def test_run_all_and_outputs(bank, tmp_path):
    pytest.importorskip("matplotlib")  # installed by requirements-eval.txt
    results = simulate.run_all(bank, 2, fake_update, never_dup, sessions=2, per_session=3)
    assert len(results) == 10
    report = simulate.write_outputs(results, 2, tmp_path)
    text = report.read_text()
    assert "n = 2 seeds" in text and "fitted" in text
    assert {p.name for p in tmp_path.iterdir()} >= {"simulation.csv", "simulation.md", "mastery_gain.png", "bkt_error.png", "repetition.png"}
