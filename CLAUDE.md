# CLAUDE.md — Track D: Grounded Adaptive Study Companion

Multimodal AI Hackathon 2026 (IIT Mandi), Track D. Submission deadline: **Wed 14 Oct 2026, 10 PM IST target** (hard cutoff 15 Oct 00:15).

## What we are building

An AI study companion that ingests lecture videos, a textbook and slide decks into a source-cited knowledge base, then uses it for grounded tutoring, verified adaptive quizzes and a Bayesian Knowledge Tracing learner model. Every answer and question must trace back to an exact page, slide number or video timestamp.

Judging weights: grounding 20%, personalization 20%, assessment 15%, UX/demo 15%, evaluation 15%, code/architecture 15%.

## Read before planning

- `docs/PRD.md`: requirements with IDs (KB-, GR-, AS-, LM-, EV-, OP-) and acceptance criteria
- `docs/TRD.md`: module design, pipelines, API contract
- `docs/WORKFLOW.md`: the plan → build → review → run → verify → commit loop
- `docs/EVAL_PLAN.md`, `docs/TESTSET_FORMAT.md`: evaluation

Reference PRD requirement IDs in plans and commit messages.

## Non-negotiable rules

1. **Grounding first.** Never generate tutor content or questions without source unit ids. Uncited claims are dropped or moved to the "Outside your material" box.
2. **Every LLM call goes through `app/llm/`**, which caches responses on disk by content hash. Never call provider SDKs directly elsewhere.
3. **No neural model training.** The learner model is statistical (BKT); parameters are fit on simulated data.
4. **Secrets live in `.env` only.** Never print, log or commit keys.
5. **One module per session.** Plan → implement → test → commit. Do not touch modules outside the current task.
6. **Shaik writes the core logic himself**: the BKT update (`learner/bkt.py`), question dedup (`assess/dedup.py`) and the citation-accuracy metric (`eval/metrics.py`). Claude may write tests and review these, but not the implementations, unless explicitly asked.
7. Report evaluation numbers honestly, including failures.

## Stack

- Backend: Python 3.11+, FastAPI, psycopg 3, Pydantic v2
- DB: Postgres + pgvector (Supabase dev project), full-text search via `tsvector`
- Main LLM + embeddings: Gemini API (`google-genai`), embeddings at 768 dims
- Second model (verification, claim check, RAGAS judge): OpenRouter (OpenAI-compatible API)
- Transcription: faster-whisper (run on Colab GPU if the laptop is slow)
- Frontend: Next.js + shadcn/ui + pdf.js + HTML5 video (in `web/`, created on Sun 11 Oct)
- Eval: RAGAS + custom metrics in `eval/`

## Layout

```
backend/app/
  config.py        settings from .env
  db.py            connection helper
  llm/             gemini.py, openrouter.py, cache.py  (all LLM access)
  ingest/          pdf.py, slides.py, video.py, figures.py
  kb/              concepts.py (topic graph), tagging.py, index.py
  qa/              retrieve.py, gate.py, answer.py, claimcheck.py
  assess/          generate.py, verify.py, dedup.py, grade.py, report.py
  learner/         bkt.py, review.py (spaced repetition), diagnostic.py, policy.py
  tutor/           agent.py (tool-calling loop)
  main.py          FastAPI app
migrations/        SQL, applied in order
eval/              testset.json, run_rag_eval.py, simulate.py, metrics.py
docs/              architecture, grounding, learner model, results
prompts/           versioned prompt templates (.md)
data/raw/          course material (git-ignored)
```

## Core data contract: content unit

Every unit has `source_id`, `modality` (`video` | `pdf` | `slide`), `locator` (JSON: `{"page": 87}`, `{"slide": 14}` or `{"t_start": 742, "t_end": 808}`), `text`, `figure_desc`, concept tags and a 768-dim embedding. Citations are unit ids; the frontend turns a unit's locator into a deep link.

## Commands

```bash
cd backend
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload
```

## Definition of done for any module

- Type-hinted, small functions, no dead code
- Unit tests for pure logic; LLM calls mocked in tests
- Runs end-to-end on the real course material
- Committed with a clear message
