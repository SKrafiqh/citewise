# Architecture

A study companion that answers and quizzes only from the student's own course material, cites the exact page, slide or video second, and adapts to a per-concept mastery estimate.

## Overview

```
 Lecture videos      Textbook PDFs        Slide decks (PDF/PPTX)
 (captions/Whisper   (PyMuPDF text +      (page image -> vision model
  + keyframes)        figure vision)       + slide text)
        \                  |                    /
         ---------- ingest/  (store.py: idempotent upsert, embeddings) ----------
                           |
        Supabase Postgres + pgvector:  sources, units(locator, embedding, tsvector),
                           concepts/prereqs, unit_concepts
                           |
        kb/ concept graph + tagging
                           |
   +-----------------------+-----------------------+
   |                       |                       |
 qa/ grounded chat    assess/ question bank    learner/ BKT + review + policy
   |                       |   <--------------->   |
   +------- tutor/check: one verified check question per answer -------+
                           |
                 FastAPI (app/api/*)  ->  Next.js app (web/)
                           |
        eval/: RAGAS + custom metrics (run_rag_eval), simulated students (simulate)
```

## Components

| Package | Responsibility |
|---|---|
| `app/llm/` | The only place that calls Gemini (generation, vision, embeddings) and OpenRouter (second model). Every call is cached on disk by request hash, retried on 429/5xx, and JSON replies get one repair re-prompt. |
| `app/ingest/` | `pdf.py`, `slides.py`, `video.py` turn a source into units; `store.py` embeds and upserts them (units are keyed `source-p87`, `source-s14`, `source-t742`, so re-ingesting never duplicates and removed units are pruned). A failure marks the source `failed` with the error and can be re-run. |
| `app/kb/` | `concepts.py` builds a validated topic → subtopic → concept graph with acyclic prerequisites; `tagging.py` tags each unit with 1–3 concepts; `graph.py` is the read-only view used everywhere else. |
| `app/qa/` | `retrieve.py` (vector + full text, reciprocal rank fusion), `gate.py`, `answer.py`, `claimcheck.py`, and `chat.py` which runs one tutoring turn. |
| `app/assess/` | `generate.py` / `verify.py` / `bank.py` build a verified question bank; `selection.py` + `service.py` serve quizzes, grade answers, update mastery and build reports. `safe_eval.py` evaluates the model's arithmetic expression for numerical checks (no code execution). |
| `app/learner/` | BKT update (`bkt.py`, owner-written), forgetting curve (`review.py`), cold start (`diagnostic.py`), next-concept policy (`policy.py`), DB side (`store.py`). |
| `app/api/`, `app/main.py` | HTTP layer: validation, rate limit, admin gate, error mapping. |
| `web/` | Next.js app: tutor chat with source viewer, assessments, dashboard, course map, library. |
| `eval/` | `run_rag_eval.py` (RAGAS + citation accuracy, hit@5, refusal, ablations, gate tuning) and `simulate.py` (5 simulated profiles, adaptive vs random). |

## Data model and locators

Schema: `migrations/001_init.sql` plus `002`–`004`. A unit's `locator` is the single source of truth for a citation:

| Modality | Locator | Citation label | Deep link |
|---|---|---|---|
| pdf | `{"page": 87}` | `p. 87` | `/assets/<source>/pages/87.jpg` |
| slide | `{"slide": 14}` | `slide 14` | `/assets/<source>/slides/14.jpg` |
| video | `{"t_start": 742, "t_end": 808}` | `12:22` | YouTube embed with `start=742` |

## Request flow: a cited tutor answer

1. `POST /chat` validates input and applies the per-IP rate limit.
2. The question is embedded (`RETRIEVAL_QUERY`); pgvector returns the top 30 units, Postgres full text the top 30; reciprocal rank fusion keeps 6.
3. **Gate:** if the best cosine similarity is below `COVERAGE_THRESHOLD`, the response is a decline that names the closest source. No answer model is called.
4. The answer model sees only the 6 excerpts and returns JSON sentences with unit ids. Unknown ids are dropped; uncited sentences never enter the answer.
5. A second model (OpenRouter) checks each sentence against its cited excerpts. Unsupported sentences are dropped, or shown in the labelled "Outside your material" box when the student opted in.
6. Citations are built from the surviving sentences' unit ids; one unseen verified check question on the main cited concept is attached; the turn is stored in `chat_messages`.

## Request flow: a quiz to a mastery update

1. `POST /assessments` picks concepts with `learner/policy.py` (due reviews first, then lowest mastery whose prerequisites are ready), then unseen, non-duplicate bank questions nearest the target difficulty (≈ the concept's P(known)). Served questions are recorded in `assessment_questions`.
2. `POST /assessments/{id}/answer` grades (exact for MCQ and numerical, rubric partial credit for short answers), applies BKT to the question's concept in one transaction (`select … for update`), writes `mastery_log`, and stores the attempt. A unique index makes a double submit impossible.
3. The response carries the correct answer, explanation, misconception label, citation chips for the anchor units and the mastery change.
4. `GET /assessments/{id}/report` aggregates topic scores, mastery change, weak topics, misconceptions and next units to study.

## Deployment

| Part | Where |
|---|---|
| Database | Supabase project "Tutor" (Postgres + pgvector, RLS on with no policies, API connects as owner) |
| API | `Dockerfile` + `render.yaml` (Render); health check `/health`, readiness `/ready` |
| Web | Vercel, `NEXT_PUBLIC_API_URL` pointing at the API |
| Assets | page/slide JPEGs under `data/derived/<source>/` are committed and baked into the image; video plays from YouTube |
