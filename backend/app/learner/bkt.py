"""Bayesian Knowledge Tracing update. YOU implement this (see CLAUDE.md rule 6).

Formulas (see build spec, "Learner model"):
    correct: P(L|obs) = P(L)(1-S) / [P(L)(1-S) + (1-P(L))G]
    wrong:   P(L|obs) = P(L)S     / [P(L)S     + (1-P(L))(1-G)]
    learn:   P(L_next) = P(L|obs) + (1 - P(L|obs)) * T

Weighted evidence (tutor check questions use weight 0.5):
    P_new = P_old + weight * (P_full_update - P_old)

Tests: backend/tests/test_bkt.py
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_learn: float = 0.15  # T
    p_slip: float = 0.10   # S
    p_guess: float = 0.25  # G (1/options for MCQ, ~0.05 numerical)


def update(p_known: float, correct: bool, params: BKTParams, weight: float = 1.0) -> float:
    """Return the new P(known) after one graded observation."""
    raise NotImplementedError("Shaik: implement the BKT update")
