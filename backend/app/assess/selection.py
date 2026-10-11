"""Pick questions for a quiz: policy-chosen concepts, unseen, non-duplicate, near the target difficulty."""
from collections.abc import Callable

PER_CONCEPT_CAP = 2  # first pass: spread the quiz over concepts before repeating any


def apportion(mix: dict[str, float], n: int) -> list[str]:
    """Question types for n slots by largest-remainder shares of `mix` (weights, any scale)."""
    total = sum(mix.values())
    if total <= 0:
        raise ValueError("mix must have a positive weight")
    exact = {t: n * w / total for t, w in mix.items() if w > 0}
    counts = {t: int(x) for t, x in exact.items()}
    by_remainder = sorted(exact, key=lambda t: (counts[t] - exact[t], t))
    for t in by_remainder[: n - sum(counts.values())]:
        counts[t] += 1
    return [t for t in sorted(counts) for _ in range(counts[t])]


def select_questions(
    bank: dict[str, list[dict]],
    qtypes: list[str],
    next_concept: Callable[[set[str]], str | None],
    target_p: Callable[[str], float],
    seen_ids: set[str],
    seen_embeddings: list[list[float]],
    is_duplicate: Callable[[list[float], list[list[float]]], bool],
) -> tuple[list[dict], int]:
    """Return (chosen questions in order, shortfall). bank: concept -> [{id, qtype, difficulty, embedding}]."""
    chosen: list[dict] = []
    embeddings = list(seen_embeddings)
    used_ids = set(seen_ids)
    uses: dict[str, int] = {}
    pending = list(qtypes)
    for cap in (PER_CONCEPT_CAP, len(qtypes)):
        exhausted: set[str] = set()
        while pending:
            excluded = exhausted | {c for c, k in uses.items() if k >= cap}
            concept = next_concept(excluded)
            if concept is None:
                break
            preferred = pending[0]
            target = target_p(concept)
            options = sorted(
                (q for q in bank.get(concept, []) if q["id"] not in used_ids),
                key=lambda q: (q["qtype"] != preferred, abs(q["difficulty"] - target), q["id"]),
            )
            pick = next((q for q in options if not is_duplicate(q["embedding"], embeddings)), None)
            if pick is None:
                exhausted.add(concept)
                continue
            chosen.append(pick)
            pending.pop(0)
            used_ids.add(pick["id"])
            embeddings.append(pick["embedding"])
            uses[concept] = uses.get(concept, 0) + 1
        if not pending:
            break
    return chosen, len(pending)
