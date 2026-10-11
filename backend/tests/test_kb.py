import numpy as np

from app.kb import concepts, tagging


def tree(n_concepts=16, prereqs=None):
    prereqs = prereqs or {}
    cs = [{"id": f"c_{i}", "name": f"C{i}", "summary": "s", "prereqs": prereqs.get(f"c_{i}", [])} for i in range(n_concepts)]
    return {"topics": [{"id": "t_a", "name": "A", "subtopics": [{"id": "s_a", "name": "SA", "concepts": cs}]}]}


def test_valid_tree_has_no_problems():
    assert concepts.validate_tree(tree(prereqs={"c_1": ["c_0"], "c_2": ["c_1"]})) == []


def test_cycle_detected():
    problems = concepts.validate_tree(tree(prereqs={"c_0": ["c_1"], "c_1": ["c_0"]}))
    assert "prerequisites contain a cycle" in problems


def test_unknown_self_and_duplicate_ids():
    t = tree(prereqs={"c_0": ["c_0"], "c_1": ["c_missing"]})
    t["topics"][0]["subtopics"][0]["concepts"][3]["id"] = "c_2"
    problems = " ".join(concepts.validate_tree(t))
    assert "itself" in problems and "unknown prerequisite" in problems and "duplicate" in problems


def test_concept_count_bounds_and_bad_ids():
    assert any("concepts; need" in p for p in concepts.validate_tree(tree(3)))
    t = tree()
    t["topics"][0]["id"] = "Bad Id"
    assert any("bad id" in p for p in concepts.validate_tree(t))


def test_flatten_levels_and_edges():
    rows, edges = concepts.flatten(tree(prereqs={"c_1": ["c_0"]}))
    assert [r["level"] for r in rows[:2]] == ["topic", "subtopic"]
    assert sum(r["level"] == "concept" for r in rows) == 16
    assert edges == [("c_1", "c_0")]
    assert rows[1]["parent_id"] == "t_a"


def test_build_tree_repairs_with_feedback(monkeypatch):
    replies = iter([tree(3), tree()])
    prompts = []
    monkeypatch.setattr(concepts, "generate_json", lambda p, **kw: (prompts.append(p), next(replies))[1])
    assert concepts.build_tree("digest") == tree()
    assert "concepts; need" in prompts[1]


def test_shortlist_orders_by_cosine():
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]])
    assert tagging.shortlist(np.array([1.0, 0.1]), ["a", "b", "c"], matrix, k=2) == ["a", "c"]


def test_clean_tags_filters_and_clamps():
    raw = [{"id": "x", "confidence": 5}, {"id": "bad", "confidence": 1}, {"id": "y", "confidence": "n/a"},
           {"id": "z", "confidence": 0.4}, {"id": "w", "confidence": 0.2}, {"id": "v", "confidence": 0.1}]
    assert tagging.clean_tags(raw, ["x", "z", "w", "v"]) == [("x", 1.0), ("z", 0.4), ("w", 0.2)]
    assert tagging.clean_tags(None, ["x"]) == []
