import pytest

from app.assess.dedup import cosine, is_duplicate
from tests.conftest import call_or_skip


def test_cosine_identical_and_orthogonal():
    assert call_or_skip(cosine, [1, 0], [1, 0]) == pytest.approx(1.0)
    assert call_or_skip(cosine, [1, 0], [0, 1]) == pytest.approx(0.0)


def test_duplicate_detected():
    assert call_or_skip(is_duplicate, [1, 0.01], [[0, 1], [1, 0]]) is True


def test_novel_question_passes():
    assert call_or_skip(is_duplicate, [1, 1], [[1, 0]], threshold=0.88) is False


def test_nothing_seen_is_not_duplicate():
    assert call_or_skip(is_duplicate, [1, 0], []) is False
