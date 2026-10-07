# TRD — Technical Design

Implements [PRD.md](PRD.md). Schema source of truth: [`migrations/001_init.sql`](../migrations/001_init.sql). Rules for building: [`CLAUDE.md`](../CLAUDE.md).

---

## 1. Architecture

```
 Lecture videos      Textbook PDFs        Slide decks
 (Whisper + frames)  (pages + figures)    (slide text + vision)
        \                  |                    /
         ------------ ingest/ + kb/ -----------
                           |
        Postgres + pgvector: units (with locators), concept graph
                           |
        +------------------+------------------+
        |                  |                  |
    qa/ grounded QA   assess/ engine     learner/ BKT
        |                  |   <-------->     |
        +-------- tutor/ agent (tool loop) ---+
                           |
                 FastAPI  ->  Next.js web app
                           |
                 eval/ (RAGAS + simulation) measures everything
```

The assessment engine and learner model feed each other: graded answers update mastery, mastery sets the next question's concept and difficulty.

## 2. Modules

| Module | Files | Responsibility | Owner |
|---|---|---|---|
| `llm/` | gemini.py, openrouter.py, cache.py | All model calls, disk-cached by request hash | done |
| `ingest/` | pdf.py, slides.py, video.py, store.py | Source → units with locators, figure descriptions, embeddings | Claude |
| `kb/` | concepts.py, tagging.py | Concept graph with prerequisites; unit → concept tags | Claude |
| `qa/` | retrieve.py, gate.py, answer.py, claimcheck.py | Hybrid retrieval, coverage gate, cited answer, claim check | Claude |
| `assess/` | generate.py, verify.py, **dedup.py**, grade.py, report.py | Question lifecycle | Claude + **Shaik (dedup)** |
| `learner/` | **bkt.py**, review.py, diagnostic.py, policy.py | Mastery estimation and next-step policy | Claude + **Shaik (bkt)** |
| `tutor/` | agent.py | Tool-calling loop combining qa, learner, assess | Claude |
| `eval/` | **metrics.py**, run_rag_eval.py, simulate.py | Evaluation | Claude + **Shaik (metrics)** |
| `web/` | Next.js app | UI | Claude |

## 3. Data model (summary)

| Table | Purpose |
|---|---|
| `sources` | One row per uploaded file or URL, with license and ingestion status |
| `units` | Searchable content unit: text, figure description, locator, 768-d embedding, tsvector |
| `concepts`, `concept_prereqs` | Topic/subtopic/concept tree and prerequisite edges |
| `unit_concepts` | Unit → concept tags with confidence |
| `questions` | Question, options with misconception tags, answer key, anchor units, difficulty, verify log, embedding |
| `students` | Real or simulated learner; profile holds intake answers or hidden truth |
| `assessments`, `attempts` | Quiz sessions and graded answers (with evidence weight) |
| `mastery`, `mastery_log` | Current BKT/review state and full history |
| `chat_messages` | Tutor conversation with cited content |

**Locator formats**

| Modality | Locator | Deep link in UI |
|---|---|---|
| pdf | `{"page": 87}` (1-based) | pdf.js viewer at page 87 |
| slide | `{"slide": 14}` (1-based) | slide image 14 |
| video | `{"t_start": 742, "t_end": 808}` (seconds) | video player seeked to 742 s |

## 4. Pipelines

### 4.1 Ingestion

| Step | PDF | Slides | Video |
|---|---|---|---|
| Read | PyMuPDF text per page | PPTX → PDF (LibreOffice), text per slide | yt-dlp download if URL |
| Visual | Embedded images > 150 px → vision description | Whole slide image → vision reading | ffmpeg scene keyframes (≤ 1 per 20 s) → vision description |
| Text | Page text | Slide text + vision text | faster-whisper segments (or Colab JSON) |
| Unit | 1 per page | 1 per slide | 60–90 s windows, sentence-aligned |
| Assets | Page PNGs | Slide PNGs | Video file served for playback |
| Store | embed → `units` (shared `store.py`, idempotent per source) | same | same |

### 4.2 Knowledge structure

1. Summarise units per source (cached).
2. One LLM call → JSON hierarchy (topics → subtopics → concepts, 15–40 concepts) with prerequisite edges.
3. Validate: unique ids, every concept has a topic, prerequisites acyclic (topological sort), no orphan topics.
4. Tagging: cosine shortlist of 5 concepts per unit → LLM picks 1–3 with confidence.

### 4.3 Grounded QA

1. Embed query (`RETRIEVAL_QUERY`).
2. Candidates: pgvector top 30 ∪ tsvector top 30 → reciprocal rank fusion (k = 60).
3. Rerank top 30 → 6 with a cross-encoder; fall back to fused order if unavailable.
4. **Gate:** best rerank score < τ → declined response. τ tuned on the off-material slice of the test set.
5. **Answer:** `prompts/answer.md` → JSON sentences with cited unit ids; level hint from mastery.
6. **Claim check:** OpenRouter model judges each sentence against its cited units' text → supported / unsupported. Unsupported sentences move to `outside` (or are dropped).
7. Return sentences, citations (unit id, source, locator, excerpt), outside box, declined flag.

### 4.4 Assessment

1. **Select** concepts from scope + learner policy; target difficulty from mastery.
2. **Generate** from 1–2 anchor units per question (types: mcq, short, numerical); MCQ distractors carry misconception labels.
3. **Verify** (per type):
   - MCQ: second model answers blind from anchor text; must equal key; exactly one option correct.
   - Numerical: second model writes SymPy code → subprocess, 10 s timeout, no network; result within tolerance of key.
   - Short: rubric of 2–4 key points, each found in anchor text by the second model.
   - Fail → regenerate ≤ 2 times → drop. Log every outcome in `verify_log`.
4. **Dedup** against this student's seen question embeddings (`assess/dedup.py`, threshold ≈ 0.88).
5. **Grade:** exact for MCQ/numerical; rubric-based LLM grading with partial credit for short answers.
6. **Feedback:** explanation + citation chip to anchor units.
7. **Report:** score per topic, mastery deltas, weak topics (mastery < 0.5), misconceptions (chosen distractor labels + repeated error patterns), next units.

### 4.5 Learner model

- **BKT** per concept (`learner/bkt.py`): P(L0)=0.2 (or intake prior), T=0.15, S=0.1, G=1/options for MCQ, 0.05 numerical, ~0.1 short. Evidence weight 1.0 for quiz answers, 0.5 for tutor check questions. Score ≥ 0.6 counts as correct for short answers.
- **Forgetting** (`learner/review.py`): stability s (days) grows ×2 after each correct review once mastered (P ≥ 0.8); recall = exp(−Δdays / s); due when < 0.85.
- **Cold start** (`learner/diagnostic.py`): intake familiarity → P(L0) ∈ {0.1, 0.3, 0.5}; diagnostic picks the topic with P closest to 0.5 each step, ~10 questions.
- **Policy** (`learner/policy.py`): candidate concepts = due for review ∪ {0.3 ≤ P ≤ 0.8 with all prerequisites ≥ 0.6}; pick highest priority (due first, then lowest P); difficulty ≈ P.
- Parameters T and S are re-fit on simulated data (grid search or pyBKT) and reported.

### 4.6 Tutor agent

Plain function-calling loop (max 5 tool steps):

| Tool | Does |
|---|---|
| `search_course(query, scope?)` | Runs the grounded QA retrieval |
| `get_learner_state(concepts)` | Returns mastery and prerequisites status |
| `ask_check_question(concept)` | Pulls or generates one verified question |
| `record_observation(concept, correct)` | Updates mastery at weight 0.5 |
| `open_source(unit_id)` | Returns locator for the UI |

Explanation depth: P < 0.4 → simple, cover prerequisites; P > 0.8 → Socratic and harder problems.

## 5. API contract (FastAPI)

| Method | Path | Body / params | Returns |
|---|---|---|---|
| GET | `/health` | | `{status}` |
| POST | `/sources` | multipart file or `{url, title, license}` | `{source_id, status}` (ingestion runs in background) |
| GET | `/sources` | | list with status and unit counts |
| GET | `/units/{id}` | | text, figure_desc, source, locator, asset URL |
| GET | `/concepts` | | tree + prerequisite edges |
| POST | `/students` | `{name}` | `{student_id}` |
| POST | `/students/{id}/intake` | `{goal, exam_date, familiarity: {topic_id: 0-2}}` | priors set |
| POST | `/chat` | `{student_id, question, allow_outside}` | `{declined, sentences[{text, cites}], citations[], outside[]}` |
| POST | `/assessments` | `{student_id, kind, scope[], n, mix{mcq,short,numerical}}` | `{assessment_id, questions[]}` (no answer keys) |
| POST | `/assessments/{id}/answer` | `{question_id, response}` | `{correct, score, feedback, mastery_delta}` |
| GET | `/assessments/{id}/report` | | report JSON |
| GET | `/students/{id}/mastery` | | per-concept mastery + due flags |
| GET | `/students/{id}/recommendations` | | next concepts and units |
| GET | `/students/{id}/schedule` | `exam_date?` | day-by-day plan |
| GET | `/assets/{path}` | | page/slide PNGs, video files |

## 6. Configuration

All settings come from `.env` via `app/config.py`: Gemini key and model names, embedding dimension (768), OpenRouter key and model, database URL, cache directory. Planned additions: `WHISPER_MODEL`, `COVERAGE_THRESHOLD`, `DEDUP_THRESHOLD`.

## 7. Error handling

| Case | Behaviour |
|---|---|
| LLM call fails | Retry with backoff (3 tries); ingestion marks the source `failed` with the error, re-runnable |
| Invalid JSON from model | One repair re-prompt, then fail that item |
| Vision call fails on one figure | Store unit without figure_desc; log warning |
| Verification sandbox timeout | Question counted as failed verification |
| No candidates retrieved | Declined response |

## 8. Testing

- Unit tests for pure logic: cache, BKT, dedup, metrics, locator building, RRF, graph validation, policy.
- LLM calls mocked in tests; integration runs on the real course material use the cache.
- Smoke test of the demo flow (Playwright) before recording.

## 9. Deployment

| Part | Where |
|---|---|
| Database | Supabase (dev project) |
| API | Render or Railway (Docker or `uvicorn`), env vars set in dashboard |
| Web | Vercel, `NEXT_PUBLIC_API_URL` pointing at the API |
| Assets | Served by the API from `data/derived/` (small scope keeps this feasible) |
