"""Citation accuracy metric. YOU implement this.

A cited locator matches a gold locator when both come from the same source and:
  - pdf:   same page
  - slide: same slide number
  - video: the cited [t_start, t_end] window overlaps the gold window,
           or their nearest edges are within `video_tolerance_s` seconds

Tests: backend/tests/test_metrics.py
"""


def locator_matches(cited: dict, gold: dict, video_tolerance_s: float = 30.0) -> bool:
    """cited/gold look like {"source_id": "textbook", "modality": "pdf", "locator": {"page": 87}}."""
    raise NotImplementedError("Shaik: implement locator matching")


def citation_accuracy(cited: list[dict], gold: list[dict]) -> float:
    """Share of cited locators that match at least one gold locator (0 if nothing cited)."""
    raise NotImplementedError("Shaik: implement citation accuracy")
