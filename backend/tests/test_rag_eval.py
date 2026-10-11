import json

import pytest

from eval import run_rag_eval
from eval.rag_eval_core import best_threshold, load_testset, refusal_scores, split_for_tuning


def item(**over):
    base = {"id": "q001", "kind": "single", "question": "What is Bayes?", "reference_answer": "x",
            "gold": [{"source_id": "textbook", "modality": "pdf", "locator": {"page": 87}}],
            "expected": "answer", "author_checked": True}
    return {**base, **over}


def write(tmp_path, items):
    path = tmp_path / "t.json"
    path.write_text(json.dumps(items))
    return path


def test_load_valid_testset(tmp_path):
    off = item(id="q002", kind="off_material", gold=[], expected="decline", reference_answer="")
    assert [i.id for i in load_testset(write(tmp_path, [item(), off]))] == ["q001", "q002"]


def test_rejects_unchecked_duplicates_and_inconsistent_items(tmp_path):
    with pytest.raises(ValueError, match="hand-checked"):
        load_testset(write(tmp_path, [item(author_checked=False)]))
    assert load_testset(write(tmp_path, [item(author_checked=False)]), require_checked=False)
    with pytest.raises(ValueError, match="duplicate"):
        load_testset(write(tmp_path, [item(), item()]))
    with pytest.raises(ValueError, match="inconsistent"):
        load_testset(write(tmp_path, [item(kind="off_material", expected="decline")]))  # off-material with gold
    with pytest.raises(ValueError, match="inconsistent"):
        load_testset(write(tmp_path, [item(gold=[])]))  # answerable without gold


def test_refusal_scores():
    s = refusal_scores([True, True, False, False], [True, False, True, False])
    assert s["precision"] == 0.5 and s["recall"] == 0.5
    assert refusal_scores([False], [False]) == {"precision": 0.0, "recall": 0.0, "n_expected_decline": 0, "n_predicted_decline": 0}


def test_best_threshold_separates_classes():
    sims = [0.2, 0.3, 0.7, 0.8]
    decline = [True, True, False, False]
    tau = best_threshold(sims, decline)
    assert 0.3 < tau <= 0.7


def test_split_is_disjoint_deterministic():
    tune, held = split_for_tuning(10, seed=1)
    assert sorted(tune + held) == list(range(10)) and (tune, held) == split_for_tuning(10, seed=1) and len(held) == 3


def test_hit_at_k_uses_reserved_locator_match(monkeypatch):
    monkeypatch.setattr(run_rag_eval, "locator_matches", lambda cited, gold: cited["locator"] == gold["locator"])
    gold = [{"source_id": "t", "modality": "pdf", "locator": {"page": 3}}]
    refs = [{"source_id": "t", "modality": "pdf", "locator": {"page": p}} for p in (9, 8, 7, 6, 5, 3)]
    assert not run_rag_eval.hit_at_k(refs, gold) and run_rag_eval.hit_at_k(refs, gold, k=6)


def test_markdown_table_handles_missing_values():
    result = {"mode": "hybrid", "claim_check": True, "n_total": 3, "hit@5": 0.5, "citation_accuracy": None, "figure_accuracy": None,
              "n_figure": 0, "refusal": {"precision": 1.0, "recall": 0.5}}
    assert "n/a" in run_rag_eval.to_markdown([result])
