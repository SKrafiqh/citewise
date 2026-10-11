"""Next-concept policy, difficulty targeting and recommendations (AS-7, LM-6). Pure functions."""
from app.learner.bkt import BKTParams

DEFAULT_P0 = 0.2        # prior P(known) when nothing is known about the student
WEAK_BELOW = 0.5
PREREQ_READY = 0.6
ZONE = (0.3, 0.8)       # learning zone: not hopeless, not yet mastered
GUESS = {"numerical": 0.05, "short": 0.1}


def bkt_params_for(qtype: str, n_options: int = 4) -> BKTParams:
    """Guess probability depends on how guessable the question type is."""
    guess = 1 / n_options if qtype == "mcq" else GUESS[qtype]
    return BKTParams(p_guess=guess)


def target_difficulty(p_known: float) -> float:
    return min(1.0, max(0.0, p_known))


def _p(mastery: dict[str, float], concept: str) -> float:
    return mastery.get(concept, DEFAULT_P0)


def candidates(scope: list[str], mastery: dict[str, float], due: set[str], prereqs: dict[str, list[str]]) -> list[str]:
    """Due for review, or in the learning zone with every prerequisite ready."""
    chosen = []
    for c in scope:
        in_zone = ZONE[0] <= _p(mastery, c) <= ZONE[1] and all(_p(mastery, d) >= PREREQ_READY for d in prereqs.get(c, []))
        if c in due or in_zone:
            chosen.append(c)
    return chosen


def pick_next(scope: list[str], mastery: dict[str, float], due: set[str], prereqs: dict[str, list[str]], exclude: set[str] | None = None) -> str | None:
    """Due concepts first, then lowest mastery. Falls back to the whole scope so a quiz is never empty."""
    open_scope = [c for c in scope if c not in (exclude or set())]
    pool = candidates(open_scope, mastery, due, prereqs) or open_scope
    return min(pool, key=lambda c: (c not in due, _p(mastery, c), c), default=None)


def recommend(scope: list[str], mastery: dict[str, float], prereqs: dict[str, list[str]], due: set[str], limit: int = 5) -> list[dict]:
    """Weak concepts to study next; a weak prerequisite is recommended before the concept that needs it."""
    out: list[dict] = []
    seen: set[str] = set()

    def add(concept: str, reason: str) -> None:
        if concept not in seen:
            seen.add(concept)
            out.append({"concept_id": concept, "p_known": _p(mastery, concept), "reason": reason})

    for c in sorted(due & set(scope)):
        add(c, "due for review")
    for c in sorted((c for c in scope if _p(mastery, c) < WEAK_BELOW), key=lambda c: (_p(mastery, c), c)):
        weak_prereqs = [d for d in prereqs.get(c, []) if _p(mastery, d) < PREREQ_READY]
        if weak_prereqs:
            add(min(weak_prereqs, key=lambda d: (_p(mastery, d), d)), f"prerequisite of {c}")
        else:
            add(c, "weak concept")
    return out[:limit]
