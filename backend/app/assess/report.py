"""Post-assessment report: topic scores, mastery change, weak topics, misconceptions (AS-6)."""
from collections import Counter, defaultdict

WEAK_BELOW = 0.5


def build_report(attempts: list[dict], concepts: dict[str, dict], topics: dict[str, str], total_questions: int) -> dict:
    """attempts: {concept_id, correct, misconception, p_before, p_after} in answer order."""
    per_topic: dict[str, list[bool]] = defaultdict(list)
    before: dict[str, float] = {}
    after: dict[str, float] = {}
    labels: Counter[str] = Counter()
    for a in attempts:
        topic = concepts[a["concept_id"]]["topic_id"]
        per_topic[topic].append(bool(a["correct"]))
        before.setdefault(a["concept_id"], a["p_before"])
        after[a["concept_id"]] = a["p_after"]
        if a.get("misconception"):
            labels[a["misconception"]] += 1
    score_by_topic = [
        {"topic_id": t, "name": topics[t], "correct": sum(r), "total": len(r), "score": sum(r) / len(r)}
        for t, r in per_topic.items()
    ]
    changes = [
        {"concept_id": c, "name": concepts[c]["name"], "before": before[c], "after": after[c], "delta": after[c] - before[c]}
        for c in after
    ]
    topic_after: dict[str, list[float]] = defaultdict(list)
    for c, p in after.items():
        topic_after[concepts[c]["topic_id"]].append(p)
    weak_topics = [
        {"topic_id": t, "name": topics[t], "mastery": sum(ps) / len(ps)}
        for t, ps in topic_after.items() if sum(ps) / len(ps) < WEAK_BELOW
    ]
    return {
        "answered": len(attempts),
        "total": total_questions,
        "correct": sum(bool(a["correct"]) for a in attempts),
        "score_by_topic": sorted(score_by_topic, key=lambda t: t["score"]),
        "mastery_changes": sorted(changes, key=lambda c: c["delta"]),
        "weak_topics": sorted(weak_topics, key=lambda t: t["mastery"]),
        "misconceptions": [{"label": k, "count": v} for k, v in labels.most_common()],
    }
