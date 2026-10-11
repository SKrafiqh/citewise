# Evaluation results

> **Status: not run yet.** The code to produce every table below is finished and tested, but it needs the ingested course material, the hand-written test set and live API keys. Nothing here is a measured result until the commands below have been run; replace each "not run" with the generated table.

## Setup (course material, test set size, models, seeds)
- Course material: MIT 6.041 lectures 1–3 + slides, OpenStax *Introductory Statistics 2e* ch. 3 (see README for licences).
- Generator and embeddings: Gemini (`GEMINI_MODEL`, `GEMINI_EMBED_MODEL`); judge and verifier: OpenRouter (`OPENROUTER_MODEL`).
- Test set: `eval/testset.json`, ~40 hand-checked items (EV-2). Currently empty.
- Simulation: 5 profiles × 10 seeds × 8 sessions × 10 questions.

## A. Retrieval and generation (RAGAS + custom metrics)
Command: `python -m eval.run_rag_eval` → `eval/out/rag_eval.md`. Not run.

## Ablations
Vector only vs hybrid; claim check on vs off (same command). Reranker and figure-description ablations are not implemented (see DECISIONS #13). Not run.

## B. Assessment quality
- Verification pass rate by type: `python -m app.assess.bank --report`. Not run.
- Hand audit of 20 released questions (correctness, tag accuracy): to be done by hand. Not run.
- Repetition rate across 5 assessments: from the simulation. Not run.

## C. Personalization (simulated students)
Command: `python -m eval.simulate --export-bank && python -m eval.simulate` → `eval/out/simulation.md` and charts. Requires `app/learner/bkt.py` and `app/assess/dedup.py`. Not run.

## Failure examples
To be filled from the run (at least three, with an explanation each).

## Limitations and honest notes
- The coverage threshold must be tuned on the held-out split (`--tune-gate`) before the retrieval numbers are meaningful.
- RAGAS scores depend on the judge model; they are comparable across the variants in this report, not with other papers.
- Simulation results depend on the simulated-student assumptions.
