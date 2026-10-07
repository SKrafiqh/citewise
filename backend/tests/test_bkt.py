import pytest

from app.learner.bkt import BKTParams, update
from tests.conftest import call_or_skip

P = BKTParams(p_learn=0.15, p_slip=0.10, p_guess=0.25)


def test_correct_answer_raises_mastery():
    # 0.2*0.9 / (0.18 + 0.8*0.25) = 0.47368; then + (1-0.47368)*0.15
    assert call_or_skip(update, 0.2, True, P) == pytest.approx(0.55263, abs=1e-4)


def test_wrong_answer_lowers_mastery():
    # 0.2*0.1 / (0.02 + 0.8*0.75) = 0.03226; then + (1-0.03226)*0.15
    assert call_or_skip(update, 0.2, False, P) == pytest.approx(0.17742, abs=1e-4)


def test_half_weight_moves_halfway():
    full = call_or_skip(update, 0.2, True, P)
    half = call_or_skip(update, 0.2, True, P, weight=0.5)
    assert half == pytest.approx(0.2 + 0.5 * (full - 0.2), abs=1e-6)


def test_stays_in_bounds():
    for p in (0.0, 0.5, 1.0):
        for correct in (True, False):
            assert 0.0 <= call_or_skip(update, p, correct, P) <= 1.0
