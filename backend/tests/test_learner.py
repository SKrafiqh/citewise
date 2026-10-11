import pytest

from app.kb.graph import build_graph
from app.learner import diagnostic, policy, review


def test_bkt_params_guess_by_type():
    assert policy.bkt_params_for("mcq", 4).p_guess == 0.25
    assert policy.bkt_params_for("mcq", 5).p_guess == 0.2
    assert policy.bkt_params_for("numerical").p_guess == 0.05
    assert policy.bkt_params_for("short").p_guess == 0.1


PREREQS = {"a": [], "b": ["a"], "c": ["b"]}


def test_pick_next_prefers_due_then_lowest_mastery():
    mastery = {"a": 0.9, "b": 0.5, "c": 0.4}
    assert policy.pick_next(["a", "b", "c"], mastery, {"a"}, PREREQS) == "a"
    assert policy.pick_next(["a", "b", "c"], mastery, set(), PREREQS) == "b"  # c's prerequisite b is not ready


def test_pick_next_respects_prerequisites_and_exclusions():
    mastery = {"a": 0.2, "b": 0.5, "c": 0.5}
    assert policy.pick_next(["b", "c"], mastery, set(), PREREQS) == "b"
    assert policy.pick_next(["a", "b"], mastery, set(), PREREQS, exclude={"a"}) == "b"


def test_pick_next_falls_back_to_whole_scope_and_handles_empty():
    assert policy.pick_next(["a"], {"a": 0.95}, set(), PREREQS) == "a"
    assert policy.pick_next([], {}, set(), PREREQS) is None
    assert policy.pick_next(["a"], {}, set(), PREREQS, exclude={"a"}) is None


def test_target_difficulty_tracks_mastery():
    assert policy.target_difficulty(0.35) == 0.35
    assert policy.target_difficulty(1.4) == 1.0


def test_recommend_puts_weak_prerequisite_first():
    # a is not "weak" (0.55) but below the 0.6 readiness bar, so it is studied before b
    recs = policy.recommend(["a", "b"], {"a": 0.55, "b": 0.3}, PREREQS, set())
    assert recs == [{"concept_id": "a", "p_known": 0.55, "reason": "prerequisite of b"}]


def test_recommend_weak_concept_without_prerequisite_problem():
    recs = policy.recommend(["a", "b"], {"a": 0.9, "b": 0.3}, PREREQS, set())
    assert recs[0]["concept_id"] == "b" and recs[0]["reason"] == "weak concept"


def test_recommend_lists_due_reviews():
    recs = policy.recommend(["a"], {"a": 0.9}, PREREQS, {"a"})
    assert recs == [{"concept_id": "a", "p_known": 0.9, "reason": "due for review"}]


def test_forgetting_curve_and_due():
    assert review.recall(2, 0) == 1 and review.recall(2, 2) == pytest.approx(0.3679, abs=1e-3)
    assert review.is_due(0.9, 1.0, 1.0)          # recall e^-1 = 0.37 < 0.85
    assert not review.is_due(0.9, 1.0, 0.1)      # still fresh
    assert not review.is_due(0.5, 1.0, 10)       # not mastered: policy handles it


def test_stability_updates():
    assert review.next_stability(None, True, 0.9) == 2.0
    assert review.next_stability(4.0, True, 0.5) == 4.0
    assert review.next_stability(1.5, False, 0.5) == 1.0
    assert review.next_stability(8.0, False, 0.5) == 4.0


def test_prior_levels():
    assert [diagnostic.prior_for(i) for i in (0, 1, 2)] == [0.1, 0.3, 0.5]
    with pytest.raises(ValueError):
        diagnostic.prior_for(3)


def test_diagnostic_spreads_across_topics_and_targets_uncertainty():
    topic_of = {"a1": "t1", "a2": "t1", "a3": "t1", "b1": "t2", "b2": "t2"}
    mastery = {"a1": 0.5, "a2": 0.45, "a3": 0.1, "b1": 0.9, "b2": 0.6}
    chosen = diagnostic.diagnostic_concepts(mastery, topic_of, n=4)
    assert len(chosen) == 4 and chosen[0] == "a1"
    assert {topic_of[c] for c in chosen[:2]} == {"t1", "t2"}
    assert diagnostic.diagnostic_concepts(mastery, topic_of, n=99).__len__() == 5


def test_graph_scope_expansion():
    rows = [
        {"id": "t1", "name": "T", "level": "topic", "parent_id": None, "summary": None},
        {"id": "s1", "name": "S", "level": "subtopic", "parent_id": "t1", "summary": None},
        {"id": "c1", "name": "C1", "level": "concept", "parent_id": "s1", "summary": "x"},
        {"id": "c2", "name": "C2", "level": "concept", "parent_id": "s1", "summary": "y"},
    ]
    graph = build_graph(rows, [{"concept_id": "c2", "prereq_id": "c1"}])
    assert graph.prereqs == {"c1": [], "c2": ["c1"]}
    assert graph.expand_scope(["t1"]) == ["c1", "c2"] and graph.expand_scope(["c2"]) == ["c2"]
    assert graph.expand_scope([]) == ["c1", "c2"] and graph.expand_scope(["zzz"]) == []
