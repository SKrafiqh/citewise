"""Cold start: intake familiarity -> priors, and a diagnostic aimed at the most uncertain concepts (LM-4)."""
FAMILIARITY_PRIOR = {0: 0.1, 1: 0.3, 2: 0.5}  # never seen / heard of it / comfortable


def prior_for(level: int) -> float:
    if level not in FAMILIARITY_PRIOR:
        raise ValueError("familiarity must be 0, 1 or 2")
    return FAMILIARITY_PRIOR[level]


def diagnostic_concepts(mastery: dict[str, float], topic_of: dict[str, str], n: int = 10) -> list[str]:
    """Most uncertain concepts (P closest to 0.5), spread across topics round-robin."""
    by_topic: dict[str, list[str]] = {}
    for concept in sorted(topic_of, key=lambda c: (abs(mastery.get(c, 0.2) - 0.5), c)):
        by_topic.setdefault(topic_of[concept], []).append(concept)
    queues = sorted(by_topic.values(), key=lambda q: abs(mastery.get(q[0], 0.2) - 0.5))
    chosen: list[str] = []
    while len(chosen) < n and any(queues):
        for queue in queues:
            if queue and len(chosen) < n:
                chosen.append(queue.pop(0))
    return chosen
