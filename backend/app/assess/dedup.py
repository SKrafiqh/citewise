"""Question dedup against everything a student has seen. YOU implement this.

A new question is a duplicate if its cosine similarity to any seen question
embedding is >= threshold (start at 0.88, tune on real questions).

Tests: backend/tests/test_dedup.py
"""


def cosine(a: list[float], b: list[float]) -> float:
    raise NotImplementedError("Shaik: implement cosine similarity")


def is_duplicate(new: list[float], seen: list[list[float]], threshold: float = 0.88) -> bool:
    raise NotImplementedError("Shaik: implement duplicate check")
