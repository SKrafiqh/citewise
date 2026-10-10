# Claude Code session prompts (compressed schedule, from Sat 10 Oct)

Follow the loop in WORKFLOW.md for every session: plan mode (Shift+Tab twice) → fix the plan → approve → build → read every diff → run it yourself → commit → close the session.

Course unit: MIT 6.041 lectures 1–3 (videos + slides) and OpenStax *Introductory Statistics 2e*, chapter 3 "Probability Topics". See README for links and licenses.

Submit target: **Wed 14 Oct, 10 PM IST** (1 hour buffer before the 11 PM plan, 2 h 15 min before the hard cutoff).

---

## Sat 10 Oct · 3:30 – 11 PM · setup + PDF + slides

**You first (45 min)**
1. Unzip the repo, open a terminal in it, `git log` to confirm 3 commits.
2. Supabase: new project → SQL editor → paste `migrations/001_init.sql` → Run.
3. `cp .env.example .env`, fill in both API keys and `DATABASE_URL` (Supabase → Connect → Session pooler string).
4. Download the course material: `bash scripts/download_material.sh`, then download the OpenStax PDF by hand (see the script's last message).
5. Find the PDF page range of chapter 3 in the OpenStax PDF (open it, note first and last page numbers as the PDF viewer shows them).

**Session 1: setup check**

> Read CLAUDE.md and migrations/001_init.sql. Create a venv, install backend/requirements.txt, and confirm `pytest -q` passes. Then write `backend/scripts/check_setup.py` that: loads settings, makes one tiny Gemini generate call, one embed call (assert 768 dims), one OpenRouter call, and connects to the database and lists tables. Print a clear PASS/FAIL per check. Do not print any key.

You: run `python backend/scripts/check_setup.py`. All four must PASS before moving on.

**Session 2: PDF ingestion**

> Implement `app/ingest/pdf.py` per CLAUDE.md and docs/TRD.md §4.1. Given a PDF path, source_id, title and license, plus an optional `--pages START-END` range (PDF page numbers, 1-based, inclusive): extract text per page with PyMuPDF, render each page to PNG in data/derived/<source_id>/pages/, extract embedded images larger than 150×150 px and describe each with `app.llm.generate` using prompts/figure_describe.md. One unit per page with locator {"page": n}, where n is the page number in the original PDF. Embed text + figure_desc with `app.llm.embed` and insert into `sources` and `units` through a shared `app/ingest/store.py`. Idempotent per source. Retry LLM calls 3 times with backoff. CLI: `python -m app.ingest.pdf <path> <source_id> --title ... --license ... --pages 150-200`. Tests with a generated 2-page PDF and mocked LLM calls.

You: ingest chapter 3, then open 5 random units in Supabase and check page number, text and figure description against the PDF.

**Session 3: slides**

> Implement `app/ingest/slides.py` using `app/ingest/store.py`. Accept PPTX (convert with `soffice --headless --convert-to pdf`) or PDF, with an optional `--pages START-END`. One unit per slide with locator {"slide": n} (n = page in the original slide PDF). Render each slide to PNG and send the image to the vision model with prompts/slide_read.md, so diagrams and charts are read even when the slide has little text. CLI like pdf.py. Tests with mocked LLM calls.

You: ingest the slides for lectures 1–3 only (find their page range in the combined slides PDF), spot-check 5 slides that contain diagrams.

**Tonight (yours):** implement `backend/app/learner/bkt.py` until `pytest -q tests/test_bkt.py` passes.

---

## Sun 11 Oct · full day · video + knowledge graph + chat + assessment

**Session 4: video (captions first, Whisper fallback)**

> Implement `app/ingest/video.py` using `app/ingest/store.py`. Inputs: a local MP4 plus either (a) a VTT captions file, (b) a precomputed segments JSON, or (c) neither, in which case transcribe with faster-whisper (model from env WHISPER_MODEL, default "small"). Parse VTT into segments with start/end seconds, removing duplicated rolling-caption lines. Extract keyframes with ffmpeg scene detection (threshold 0.3, at most one per 20 s) and describe each with the vision model (prompts/slide_read.md). Merge segments into 60–90 s windows that end at sentence boundaries; attach keyframe descriptions whose timestamp falls inside a window as figure_desc. Locator {"t_start": s, "t_end": s}. Store the video's YouTube id in sources.uri as `youtube:<id>` plus the local path, so the UI can embed and seek. CLI: `python -m app.ingest.video <mp4> <source_id> --title ... --license ... --captions file.vtt --youtube-id ID`. Tests for VTT parsing and window merging.

You (while it runs): write test-set questions in `eval/testset.json` (docs/TESTSET_FORMAT.md). Target today: 25.

**Session 5: concept graph and tagging**

> Implement `app/kb/concepts.py` and `app/kb/tagging.py` per docs/TRD.md §4.2. Summarise units per source, one LLM pass returns a JSON hierarchy (topic → subtopic → concept, 15–30 concepts) with prerequisite edges; validate it (unique ids, every concept has a topic, prerequisites acyclic). Tag each unit: cosine shortlist of 5 concepts, then the LLM picks 1–3 with confidence. Add `GET /concepts`. Then backfill `concept_ids` in eval/testset.json by matching gold locators to tagged units.

**Session 6: grounded chat**

> Implement `app/qa/` per docs/TRD.md §4.3: `retrieve.py` (pgvector top 30 + tsvector top 30, reciprocal rank fusion k=60, rerank to 6 with BAAI/bge-reranker-v2-m3 via sentence-transformers, falling back to fused order if unavailable; make vector-only, hybrid and hybrid+rerank selectable for ablations), `gate.py` (coverage threshold from env COVERAGE_THRESHOLD), `answer.py` (prompts/answer.md, JSON sentences with cited unit ids), `claimcheck.py` (`app.llm.verify_chat` judges each sentence against its cited units; unsupported → outside box; can be disabled for ablation). Expose `POST /chat` per the API contract in TRD §5, plus `GET /units/{id}` and static serving of page/slide PNGs and video files under `/assets`.

You: ask 10 real questions and 3 off-topic ones with curl or the FastAPI docs page; note failures for the fix list.

**Session 7: assessment**

> Implement `app/assess/` generate.py, verify.py, grade.py, report.py per docs/TRD.md §4.4. Use my `app.assess.dedup.is_duplicate` (do not rewrite it; if it still raises NotImplementedError, stop and tell me). Numerical verification: the second model writes a SymPy script, run in a subprocess with a 10 s timeout and no network. Log every check in questions.verify_log. Pre-generate a question bank of ~60 verified questions across all concepts via a CLI, so quizzes are fast. Endpoints: POST /assessments, POST /assessments/{id}/answer, GET /assessments/{id}/report.

**Tonight (yours):** implement `dedup.py`; finish the test set to 40 items.

---

## Mon 12 Oct · 4 – 11 PM · learner model + frontend core

**Session 8: learner**

> Implement `app/learner/` review.py, diagnostic.py, policy.py per docs/TRD.md §4.5, using my `app.learner.bkt.update` (do not rewrite it). Every graded attempt updates mastery and writes mastery_log; tutor check questions use weight 0.5. Endpoints: POST /students, POST /students/{id}/intake, GET /students/{id}/mastery, GET /students/{id}/recommendations. Add the tutor check question to /chat: after an answer, return one verified question on the main cited concept.

**Session 9: frontend core** (tell Claude Code to load the frontend-design skill first)

> Create `web/` with Next.js + shadcn/ui, API base from NEXT_PUBLIC_API_URL. Build in this order: (1) Tutor chat with a split pane: citation chips like [p. 87], [slide 14], [12:22]; clicking opens the source on the right (PDF page PNG, slide PNG, or the YouTube embed seeked to t_start), "Outside your material" box clearly separated, declined answers styled distinctly, check question inline; (2) Assess: scope picker, question mix, one question at a time, cited feedback; (3) Report; (4) Dashboard: mastery per concept, weak topics, recommendations. Clean, readable at phone width.

You: click through every screen; write the 5 most important UX fixes.

---

## Tue 13 Oct · 4 – 11 PM · finish UI + deploy + evaluation

**Session 10: frontend finish + deploy**

> Apply these UX fixes: <paste your list>. Add Library (upload + ingestion status), new-student intake + diagnostic flow, and Course map (React Flow, nodes coloured by mastery). Then prepare deployment: Dockerfile for the API (Render), env var docs, Vercel config for web.

You: deploy (Render for API, Vercel for web), test the public URL on your phone.

**Session 11: simulation**

> Implement eval/simulate.py per docs/EVAL_PLAN.md §C with 5 profiles × 10 seeds × 8 sessions × 10 questions, adaptive policy vs random on the same question bank. Output CSV and PNG charts (true mastery gain; |BKT estimate − truth| per session; repetition rate). Fit T and S by grid search on the simulated data and report them.

**Session 12: RAG evaluation**

> Implement eval/run_rag_eval.py per docs/EVAL_PLAN.md §A: run eval/testset.json through the QA pipeline; RAGAS faithfulness, answer relevancy, context precision, context recall (judge = OpenRouter model through its OpenAI-compatible endpoint); plus `eval.metrics.citation_accuracy`, hit@5, refusal precision/recall. Ablations: vector-only, hybrid, hybrid+rerank; with/without claim check. Write tables to docs/results.md with n for every number.

You: implement `eval/metrics.py` before Session 12 (or hand it to Claude if behind); hand-audit 20 generated questions and record results in docs/results.md.

---

## Wed 14 Oct · 3:30 – 10 PM · fix, document, record, submit

**Session 13: fixes + docs**

> Fix these issues from the evaluation: <top 3>. Then fill docs/architecture.md, docs/grounding.md and docs/learner_model.md from the code and TRD, and update README with results, the public URL and the architecture diagram. Do not invent numbers; use only docs/results.md.

You:
1. Read every doc; delete any claim you cannot back up.
2. Record the demo (5–7 min): upload → cited chat (click a video citation) → off-topic decline → quiz with cited feedback → report → dashboard/course map → architecture + results slide.
3. Upload to YouTube (unlisted is fine), add the link to README, push.
4. Submit on Unstop by 10 PM.
