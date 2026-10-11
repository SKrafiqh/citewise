# Citewise

**A study companion that only teaches from your course material and cites every answer.**

An AI study companion that turns lecture videos, a textbook and slide decks into a source-cited knowledge base, then tutors students and runs verified adaptive quizzes driven by a Bayesian Knowledge Tracing learner model. Every answer and question links to the exact page, slide or video second it came from.

Built for Track D of the Multimodal AI Hackathon 2026 (IIT Mandi).

> **Status:** feature-complete code (backend, web app, evaluation harness) with tests. Not yet run on the real course material. Results, demo video and public URL are added to this README when they exist; see [docs/results.md](docs/results.md) for what has and has not been measured.

## What it does

- **Grounded tutor:** hybrid retrieval, a coverage gate that declines off-material questions, sentence-level citations, a second-model claim check, and a labelled "Outside your material" box.
- **Verified assessments:** MCQ (with misconception-tagged distractors), numerical and short-answer questions generated from source excerpts and verified by a second model before release; no repeats; cited feedback; reports with weak topics and misconceptions.
- **Learner model:** per-concept BKT mastery, half-weight evidence from tutor check questions, forgetting-based review, intake + diagnostic cold start, prerequisite-aware recommendations, course map coloured by mastery.
- **Evaluation:** RAGAS + citation accuracy, hit@5, refusal metrics, ablations, and a simulated-student study (adaptive vs random).

## Quick start

Prerequisites: Python 3.11+ (3.12 tested), Node 22, ffmpeg, a Supabase project, a Gemini API key and an OpenRouter API key.

```bash
cp .env.example .env     # fill GEMINI_API_KEY, OPENROUTER_API_KEY, DATABASE_URL, ADMIN_TOKEN
```

1. **Database.** Open the Supabase project's SQL editor and run, in order, `migrations/001_init.sql`, `002_assessment_links.sql`, `003_unique_attempt.sql`, `004_vector_extension_schema.sql` (Supabase only), `005_unique_check_attempt.sql`. (The project's "Tutor" database already has all five applied.) `DATABASE_URL` is the *Session pooler* connection string (port 5432).
2. **Backend.**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   pytest -q                                   # unit tests (+ DB tests if TEST_DATABASE_URL is set)
   uvicorn app.main:app --reload               # http://127.0.0.1:8000/docs
   ```
3. **Web app.**
   ```bash
   cd web && cp .env.example .env.local && npm install && npm run dev   # http://localhost:3000
   ```

## Build the knowledge base (run once)

```bash
bash scripts/download_material.sh        # MIT slides, videos, captions; then save the OpenStax PDF as data/raw/textbook/openstax_intro_stats_2e.pdf
TEXTBOOK_PAGES=START-END bash scripts/ingest_all.sh   # slides, 3 lectures, textbook chapter 3, concept graph, tags
cd backend && .venv/bin/python -m app.assess.bank --per-concept 4   # verified question bank (needs your app/assess/dedup.py)
.venv/bin/python -m app.assess.bank --report                         # verification pass rate by type
```

`TEXTBOOK_PAGES` is the PDF page range of OpenStax chapter 3 (open the PDF and note the first and last page). Rendered page and slide images land in `data/derived/<source>/`; commit them (small JPEGs) so the deployed API can serve them. Every LLM call is cached in `.cache/llm`, so reruns are free and a 429 from a free tier just means "run it again". Set `GEMINI_MAX_RPM` / `OPENROUTER_MAX_RPM` in `.env` to stay under free-tier per-minute limits.

The same ingestion is available in the web app's **Library** page (PDF/PPTX upload and YouTube URL), protected by `ADMIN_TOKEN`.

## Things only you can do

| Item | Why |
|---|---|
| Implement `backend/app/learner/bkt.py`, `backend/app/assess/dedup.py`, `eval/metrics.py` | Reserved for the project owner (CLAUDE.md rule 6). Tests are in `backend/tests/`. Until they exist, quizzes, answers, the question bank, the simulation and citation accuracy return HTTP 501 / raise `NotImplementedError`. |
| Write `eval/testset.json` (~40 hand-checked items) | Gold locators must be verified by a person ([docs/planning/TESTSET_FORMAT.md](docs/planning/TESTSET_FORMAT.md)). |
| Hand-audit 20 released questions | Correctness is judged by you, not a model. |

## Evaluate

```bash
cd backend && pip install -r requirements-eval.txt && cd ..
python -m eval.run_rag_eval --tune-gate           # choose COVERAGE_THRESHOLD on a 70% split, report on 30%
python -m eval.run_rag_eval                       # metrics + ablations + RAGAS -> eval/out/rag_eval.md
python -m eval.simulate --export-bank && python -m eval.simulate   # adaptive vs random -> eval/out/simulation.md
```

Copy the generated tables into [docs/results.md](docs/results.md); do not edit numbers by hand.

## Deploy

- **API (Render):** `render.yaml` + `Dockerfile` (build context = repo root). Set `DATABASE_URL`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `ADMIN_TOKEN`, `CORS_ORIGINS` (the Vercel URL) in the dashboard. Health check: `/health`; DB readiness: `/ready`.
- **Web (Vercel):** project root `web/`, env `NEXT_PUBLIC_API_URL` = the API URL.
- Local database for tests: any Postgres with pgvector, e.g. `docker run -d -p 54329:5432 -e POSTGRES_PASSWORD=x -e POSTGRES_DB=tutor pgvector/pgvector:pg17`, apply the migrations, then `TEST_DATABASE_URL=postgresql://postgres:x@localhost:54329/tutor pytest`.

## Project structure

```
backend/            FastAPI service
  app/
    api/            HTTP routers (library, tutor, learning)
    llm/            every LLM call: Gemini, OpenRouter, disk cache, retry
    ingest/         PDF, slide and video ingestion -> units with locators
    kb/             concept graph and unit tagging
    qa/             retrieval, coverage gate, cited answers, claim check
    assess/         question generation, verification, grading, reports
    learner/        BKT mastery, review scheduling, diagnostic, policy
    tutor/          tutor check questions
  scripts/          check_setup.py (verifies keys, models and DB)
  tests/            pytest suite
web/                Next.js app (chat + source viewer, quizzes, dashboard, course map)
eval/               test set, RAG evaluation, simulated students, metrics
migrations/         SQL schema, applied in order
prompts/            versioned prompt templates
scripts/            download course material, ingest everything
data/derived/       rendered page and slide images served by the API
docs/               architecture, grounding, learner model, results
  planning/         PRD, TRD, decisions, eval plan, workflow
```

## Documentation

| Doc | Purpose |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Components, data model, request flows |
| [docs/grounding.md](docs/grounding.md) | Retrieval, gate, citations, claim check |
| [docs/learner_model.md](docs/learner_model.md) | BKT, review, cold start, policy |
| [docs/results.md](docs/results.md) | Evaluation protocol and results (honest status) |
| [docs/planning/PRD.md](docs/planning/PRD.md), [docs/planning/TRD.md](docs/planning/TRD.md) | Requirements and original design |
| [docs/planning/DECISIONS.md](docs/planning/DECISIONS.md) | Why we chose X over Y (incl. deviations from the TRD) |
| [docs/planning/EVAL_PLAN.md](docs/planning/EVAL_PLAN.md), [docs/planning/TESTSET_FORMAT.md](docs/planning/TESTSET_FORMAT.md) | Evaluation protocol and test-set format |

## Security notes

Keys live only in `.env`. Ingestion endpoints need `ADMIN_TOKEN` (16+ characters); LLM-spending endpoints are rate-limited per IP with a daily cap; the database has RLS enabled with no policies and is reached only through the API; numerical verification evaluates a restricted arithmetic expression and never executes model-written code. There is no end-user login by design: student ids are random 32-character capabilities, so do not share URLs or screenshots that contain them.

## Course material

| Source | Content used | License |
|---|---|---|
| [MIT OCW 6.041 Probabilistic Systems Analysis (Fall 2010)](https://ocw.mit.edu/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/) | Lecture videos 1–3 and their slides | CC BY-NC-SA 4.0 |
| [OpenStax Introductory Statistics 2e](https://openstax.org/details/books/introductory-statistics-2e) | Chapter 3, Probability Topics | CC BY 4.0 |

## Related work

[OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) generates interactive lessons from a topic or document. This project differs by grounding every answer and question in the student's own course material with exact source links, and by adapting to the student through a learner model.
