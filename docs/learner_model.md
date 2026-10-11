# Learner model

## Why BKT
Bayesian Knowledge Tracing is interpretable, works with a handful of answers per concept, needs no training data and runs in a few microseconds. Parameters are fitted on simulated students (grid search on the likelihood), not trained as a neural model.

## Update equations and parameters
Per concept, P(known) is updated after each graded answer by `app/learner/bkt.py` (written by the project owner):

- correct: P(L|obs) = P(L)(1−S) / [P(L)(1−S) + (1−P(L))G]
- wrong: P(L|obs) = P(L)S / [P(L)S + (1−P(L))(1−G)]
- learn: P(L_next) = P(L|obs) + (1 − P(L|obs))·T

Defaults: P(L0) = 0.2 (or the intake prior), T = 0.15, S = 0.10. The guess probability G depends on the question: 1/(number of options) for MCQ, 0.05 numerical, 0.10 short answer (`policy.bkt_params_for`). Short answers with rubric score ≥ 0.6 count as correct. Fitted T and S from the simulation are reported in [results.md](results.md).

## Evidence from conversations (half weight)
After a grounded answer the tutor attaches one unseen verified check question on the main cited concept. Answering it updates mastery with weight 0.5 (`P_new = P_old + 0.5·(P_full − P_old)`), logged with source `check`. A check question is never asked twice.

## Forgetting and review scheduling
`learner/review.py`: stability s (days) starts at 1, doubles after each correct review once P ≥ 0.8 and halves (floor 1) after a miss. Recall = exp(−Δdays / s); a mastered concept is due for review when recall < 0.85.

## Cold start: intake and diagnostic
The intake form sets P(L0) per topic from self-rated familiarity: new 0.1, heard of it 0.3, comfortable 0.5. The diagnostic (≈10 questions) picks the concepts whose P is closest to 0.5, spread round-robin over topics.

## Next-question policy
`learner/policy.py`: candidates = concepts due for review, plus concepts with 0.3 ≤ P ≤ 0.8 whose prerequisites are all ≥ 0.6. Due concepts first, then lowest P; if no candidate exists the whole scope is used so a quiz is never empty. Target difficulty ≈ P. Recommendations list due and weak concepts and put a weak prerequisite before the concept that needs it. Questions are chosen when a quiz is created, so adaptation happens between quizzes, not inside one.

## Simulation results
See [results.md](results.md) (`python -m eval.simulate`).

## Limitations
- One skill per question; no multi-concept credit.
- Parameters are shared across concepts and students.
- Self-rated familiarity is a weak prior; the diagnostic corrects it only after ~10 answers.
- The simulation's adaptive arm uses the real policy but picks questions with a simpler loop than `assess/selection.py` (no per-concept cap); fitted T and S are reported, not fed back into the defaults.
- The simulated student is an assumption (known/unknown with slip, guess, learn and forget); simulation results show the policy works under that model, not on real students.
