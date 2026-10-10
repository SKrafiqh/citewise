# Evaluation plan

Implements PRD §6.5. All runs use cached LLM calls and fixed seeds so results reproduce from one command. Every number goes into `docs/results.md`, including weak ones.

## A. Retrieval and generation (`eval/run_rag_eval.py`)

**Input:** `eval/testset.json` (see TESTSET_FORMAT.md). Each question goes through the real `/chat` pipeline.

| Metric | Source | Computed on |
|---|---|---|
| Faithfulness | RAGAS | single + multi_hop answers |
| Answer relevancy | RAGAS | single + multi_hop |
| Context precision | RAGAS | single + multi_hop (reference answers) |
| Context recall | RAGAS | single + multi_hop (reference answers) |
| Citation accuracy | `eval/metrics.py` | cited locators vs gold |
| Hit@5 | custom | gold unit among top 5 retrieved |
| Refusal precision / recall | custom | declines vs `expected` |
| Figure-question accuracy | custom | items with `needs_figure: true` |

Judge model: the OpenRouter model (a different provider from the generator), named in results.

**Ablations** (same test set):

| Variant | Purpose |
|---|---|
| Vector only | Baseline retrieval |
| Hybrid (vector + full text, RRF) | Value of keyword search |
| Hybrid + reranker | Value of reranking |
| With vs without claim check | Value of the verifier for faithfulness |
| With vs without figure descriptions | Value of multimodal extraction |

## B. Assessment quality

| Metric | How |
|---|---|
| Verification pass rate | From `questions.verify_log`, by question type |
| Correctness | Hand audit of 20 random released questions (you, not a model) |
| Tag accuracy | Same 20: is the concept tag and anchor location right? |
| Repetition rate | 5 consecutive assessments for one student: share of near-duplicates |

## C. Personalization (`eval/simulate.py`)

**Simulated student:** hidden true knowledge per concept (known / not known). Answer correct with probability known·(1−S) + (1−known)·G. After feedback, learns with probability T. Between sessions, forgets with a small per-day probability.

| Profile | Hidden truth |
|---|---|
| Strong | Most concepts known |
| Weak foundations | Prerequisite concepts unknown |
| Uneven | Half the topics known |
| Fast learner | Higher T |
| Forgetful | Higher forgetting rate |

**Protocol:** 5 profiles × 10 seeds × 8 sessions × 10 questions. Same question bank for both policies.

| Policy | Description |
|---|---|
| Adaptive | `learner/policy.py` choosing concept and difficulty |
| Random | Uniform random question from the bank |

**Report (mean ± std over seeds):**
- True mastery gain (share of concepts known at end − start)
- Mean absolute error of BKT estimate vs hidden truth per session (should fall: "improves with more data")
- Repetition rate
- Sessions until 80% of concepts known
- Fitted BKT T and S

Optional: two LLM-played students with scripted misconceptions, as a qualitative case study.

## Honesty rules

- Never tune thresholds on the same items you report; tune τ on a held-out 30% of off-material and in-material items, or say clearly that you did not.
- Report n for every number.
- List failure examples (at least 3) with an explanation.
