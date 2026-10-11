"""Forgetting curve and review scheduling (LM-5). Pure functions."""
import math

MASTERED = 0.8
DUE_BELOW = 0.85       # review when estimated recall drops under this
INITIAL_STABILITY = 1.0  # days


def recall(stability_days: float, elapsed_days: float) -> float:
    return math.exp(-max(0.0, elapsed_days) / stability_days)


def is_due(p_known: float, stability_days: float | None, elapsed_days: float) -> bool:
    """Only mastered concepts are scheduled for review; weaker ones are handled by the policy."""
    return p_known >= MASTERED and recall(stability_days or INITIAL_STABILITY, elapsed_days) < DUE_BELOW


def next_stability(stability_days: float | None, correct: bool, p_known_after: float) -> float:
    """Doubles after a correct review once mastered; halves (floor 1 day) after a miss."""
    current = stability_days or INITIAL_STABILITY
    if not correct:
        return max(INITIAL_STABILITY, current * 0.5)
    return current * 2 if p_known_after >= MASTERED else current
