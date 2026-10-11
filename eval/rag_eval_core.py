"""Pure parts of the RAG evaluation: test-set loading, refusal metrics, gate tuning (EVAL_PLAN §A)."""
import json
import random
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Gold(BaseModel):
    source_id: str
    modality: Literal["pdf", "slide", "video"]
    locator: dict


class Item(BaseModel):
    id: str
    kind: Literal["single", "multi_hop", "off_material"]
    question: str = Field(min_length=3)
    reference_answer: str = ""
    gold: list[Gold] = []
    needs_figure: bool = False
    concept_ids: list[str] = []
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    expected: Literal["answer", "decline"]
    author_checked: bool = False


def load_testset(path: Path, require_checked: bool = True) -> list[Item]:
    items = [Item(**raw) for raw in json.loads(path.read_text(encoding="utf-8"))]
    if len({i.id for i in items}) != len(items):
        raise ValueError("duplicate item ids in the test set")
    for i in items:
        if (i.expected == "decline") != (i.kind == "off_material") or bool(i.gold) == (i.kind == "off_material"):
            raise ValueError(f"{i.id}: kind, expected and gold are inconsistent (see docs/planning/TESTSET_FORMAT.md)")
    unchecked = [i.id for i in items if not i.author_checked]
    if require_checked and unchecked:
        raise ValueError(f"items not hand-checked (author_checked=false): {unchecked}")
    return items


def refusal_scores(expected_decline: list[bool], predicted_decline: list[bool]) -> dict[str, float | int]:
    pairs = list(zip(expected_decline, predicted_decline))
    tp = sum(e and p for e, p in pairs)
    predicted, expected = sum(p for _, p in pairs), sum(e for e, _ in pairs)
    return {"precision": tp / predicted if predicted else 0.0, "recall": tp / expected if expected else 0.0,
            "n_expected_decline": expected, "n_predicted_decline": predicted}


def best_threshold(sims: list[float], should_decline: list[bool]) -> float:
    """Gate threshold maximising decline F1 (decline when top similarity < threshold)."""
    best, best_f1 = 0.0, -1.0
    for tau in sorted(set(sims) | {0.0}):
        pred = [s < tau for s in sims]
        scores = refusal_scores(should_decline, pred)
        p, r = scores["precision"], scores["recall"]
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        if f1 > best_f1:
            best, best_f1 = tau, f1
    return best


def split_for_tuning(n: int, seed: int = 0, tune_share: float = 0.7) -> tuple[list[int], list[int]]:
    """Indexes to tune the gate on and held-out indexes to report it on (EVAL_PLAN honesty rules)."""
    order = list(range(n))
    random.Random(seed).shuffle(order)
    cut = int(n * tune_share)
    return order[:cut], order[cut:]
