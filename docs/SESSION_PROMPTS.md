# Claude Code session prompts

One session per block. Follow the loop in WORKFLOW.md. Start each with plan mode (Shift+Tab twice), approve the plan, then let it build. Review every diff, run the tests yourself, commit, then close the session.

---

## Day 1 · Wed 7 Oct — setup + PDF ingestion

**Session 1: setup check**

> Read CLAUDE.md and migrations/001_init.sql. Create a venv, install backend/requirements.txt, and confirm `pytest -q` passes. Then write `backend/scripts/check_setup.py` that: loads settings, makes one tiny Gemini generate call, one embed call (assert 768 dims), one OpenRouter call, and connects to the database and lists tables. Print a clear PASS/FAIL per check. Do not print any key.

You: run `python backend/scripts/check_setup.py`. All four must PASS before moving on.

**Session 2: PDF ingestion**

> Implement `app/ingest/pdf.py` per CLAUDE.md. Given a PDF path and source_id: extract text per page with PyMuPDF, render each page to PNG in data/derived/<source_id>/pages/, extract embedded images larger than 150×150 px, and send each to `app.llm.generate` with prompts/figure_describe.md to get a figure description. Produce one unit per page with locator {"page": n} (1-based, matching the printed page index). Embed text+figure_desc with `app.llm.embed` and insert into `sources` and `units`. Make it idempotent (re-running replaces that source's units). Add a CLI: `python -m app.ingest.pdf <path> <source_id>`. Tests with a 2-page generated PDF and mocked LLM calls.

You: ingest the textbook, then open 5 random units and check the page numbers and figure descriptions by hand.

---

## Day 2 · Thu 8 Oct — slides + video + start the test set

**Session 3: slides**

> Implement `app/ingest/slides.py`. Accept PPTX (convert to PDF with `soffice --headless --convert-to pdf`) or PDF. One unit per slide with locator {"slide": n}. Render each slide to PNG and send the whole slide image to the vision model with prompts/slide_read.md, so diagrams and charts are read even when there is little text. Reuse the embedding and insert code from pdf.py by extracting a shared `app/ingest/store.py`.

**Session 4: video**

> Implement `app/ingest/video.py`. Input: a local MP4 or a YouTube URL (download with yt-dlp). Transcribe with faster-whisper (model size from env WHISPER_MODEL, default "small") into segments with start/end times; also accept a precomputed segments JSON (from Colab) via `--segments`. Extract keyframes with ffmpeg scene detection (threshold 0.3, max one per 20 s) and describe each with the vision model. Merge into 60–90 s windows that do not split sentences; attach keyframe descriptions whose timestamps fall inside each window as figure_desc. Locator {"t_start": s, "t_end": s}.

You: while ingestion runs, start eval/testset.json (see docs/TESTSET_FORMAT.md).

---

## Day 3 · Fri 9 Oct — concept graph + grounded chat

**Session 5: concept graph and tagging**

> Implement `app/kb/concepts.py` and `app/kb/tagging.py` per the build spec. Summarise units per source, then one LLM pass returns a JSON hierarchy (topic → subtopic → concept, 15–40 concepts) with prerequisite edges; validate it (no cycles, every concept has a parent topic). Tag each unit: embedding shortlist of 5 concepts, then the LLM picks 1–3 with confidence. Then backfill `concept_ids` in eval/testset.json by matching gold locators to tagged units.

**Session 6: retrieval + answer**

> Implement `app/qa/`: `retrieve.py` (pgvector top 30 + tsvector top 30, reciprocal rank fusion, then rerank to 6 using the cross-encoder BAAI/bge-reranker-v2-m3 via sentence-transformers, with a fallback to fused order if it is unavailable), `gate.py` (coverage threshold on best rerank score, configurable), `answer.py` (JSON output: sentences each with cited unit ids; prompt in prompts/answer.md forbids uncited claims), `claimcheck.py` (verify_chat checks each sentence against its cited units; unsupported → outside box). Expose `POST /chat` returning sentences, citations with locators, outside box and a declined flag.

---

## Day 4 · Sat 10 Oct — assessment

**Session 7: generate + verify + grade**

> Implement `app/assess/` generate.py, verify.py, grade.py, report.py per the build spec. Dedup uses `app.assess.dedup.is_duplicate` (already implemented by me — do not rewrite it). Numerical verification: the second model writes a SymPy script; run it in a subprocess with a 10 s timeout and no network. Log pass/fail per check into questions.verify_log. Endpoints: POST /assessments, POST /assessments/{id}/answer, GET /assessments/{id}/report.

---

## Day 5 · Sun 11 Oct (full day) — learner model + frontend

**Session 8: learner**

> Implement `app/learner/` review.py (stability-based forgetting), diagnostic.py (intake → priors; next question targets mastery closest to 0.5), policy.py (next concept: due or in 0.3–0.8 with prerequisites ≥0.6). Use my `app.learner.bkt.update` — do not rewrite it. Write every change to mastery and mastery_log. Hook grading so each graded attempt updates mastery.

**Session 9–10: frontend** (load the frontend-design skill first)

> Create `web/` with Next.js + shadcn/ui. Build first: the tutor chat with a split pane — clicking a citation chip opens pdf.js at the page, the slide image, or the video seeked to t_start, with the excerpt highlighted. Then: Library (upload + ingestion status), Assess, Report, Dashboard (mastery heatmap, reviews due, recommendations), Course map (React Flow, nodes coloured by mastery).

---

## Day 6 · Mon 12 Oct — evaluation

**Session 11: simulation**

> Implement eval/simulate.py per the build spec "System evaluation" section C: 5 profiles × 20 seeds × 8 sessions × 10 questions, adaptive policy vs random baseline on the same question bank. Output CSV + charts (true mastery gain, |BKT estimate − truth| per session, repetition rate). Fit BKT T and S on the simulated data and report them.

**Session 12: RAGAS**

> Implement eval/run_rag_eval.py: run the test set through /chat, compute RAGAS faithfulness, answer relevancy, context precision and recall (judge = OpenRouter model via its OpenAI-compatible endpoint), plus my `eval.metrics.citation_accuracy`, refusal precision/recall and hit@5. Ablations: vector-only, hybrid, hybrid+rerank; with and without claim check. Write results to docs/results.md as tables.

---

## Day 7–8 · Tue 13 – Wed 14 Oct

> Fix the top issues the evaluation exposed. Then: flashcards for weak concepts, study schedule, Hindi toggle. Then docs/architecture.md, docs/grounding.md, docs/learner_model.md and the README results section.

You: record the demo video, upload to YouTube, submit on Unstop before 11 PM Wed 14 Oct.
