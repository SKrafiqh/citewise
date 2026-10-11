"""Coverage gate: decline questions the material does not cover (GR-3)."""
from app.config import get_settings
from app.qa.retrieve import Hit


def covered(top_sim: float, threshold: float | None = None) -> bool:
    return top_sim >= (get_settings().coverage_threshold if threshold is None else threshold)


def decline_reason(hits: list[Hit]) -> str:
    if not hits:
        return "Your course material has no content related to this question."
    nearest = hits[0]
    return (
        f"Your course material does not appear to cover this. The closest content is in "
        f"“{nearest.source_title}”, but it does not address the question."
    )
