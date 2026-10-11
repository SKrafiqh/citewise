# PRD — Grounded Study Companion

| | |
|---|---|
| Product | Citewise |
| Owner | Shaik Rafiqhuddin |
| Context | Multimodal AI Hackathon 2026 (IIT Mandi), Track D: Personalized Tutoring & Adaptive Learning |
| Status | In development · v0.1 · 7 Oct 2026 |
| Deadline | Submit by Wed 14 Oct 2026, 10 PM IST (hard cutoff 15 Oct, 00:15 IST) |
| Related | [TRD.md](TRD.md) · [EVAL_PLAN.md](EVAL_PLAN.md) · [WORKFLOW.md](WORKFLOW.md) · [DECISIONS.md](DECISIONS.md) |

---

## 1. Problem

Students study from lecture videos, textbooks and slides spread across different places. General AI chatbots answer from outside knowledge that may not match the course, give no way to check where an answer came from, and know nothing about what the student already understands. Study time is spent searching, and answers cannot be trusted for exams.

## 2. Product vision

A study companion that only teaches from the student's own course material, shows exactly where every answer comes from (the page, the slide, the second of the lecture), and adapts what it teaches and tests to what that student has and has not mastered.

**One-line pitch:** OpenMAIC-style tools generate lessons from a topic; this one is grounded in *your* course material and adapts to *you*.

## 3. Users

| User | Need | How we serve it |
|---|---|---|
| **Student (primary)** | Understand concepts, practise for exams, trust the answers | Cited tutor chat, adaptive quizzes, mastery dashboard |
| **Student new to the course** | Know where to start | Intake conversation + diagnostic quiz |
| **Course owner / uploader** (same person in v1) | Add material without manual cleanup | One-step upload of video, PDF, PPTX |
| **Hackathon judge** | See requirements met with evidence | Demo video, evaluation report, clear docs |

## 4. Goals and success metrics

Targets are goals for the evaluation run, not promises. Report the real numbers either way.

| Goal | Metric | Target |
|---|---|---|
| Answers are grounded | RAGAS faithfulness on in-material questions | ≥ 0.85 |
| Citations point to the right place | Citation accuracy (same page/slide, video within 30 s) | ≥ 80% |
| Off-material questions are declined | Refusal recall on off-material set | ≥ 90% |
| Retrieval finds the right evidence | RAGAS context recall · hit@5 | ≥ 0.80 · ≥ 85% |
| Questions are correct | Hand audit of 20 released questions | ≥ 90% correct |
| No repeats | Repetition rate across 5 assessments | < 5% |
| Personalization works | True mastery gain, adaptive vs random (simulated) | Adaptive higher, with seeds and spread reported |
| Model learns the student | Mean abs. error, BKT estimate vs hidden truth | Falls across sessions |

## 5. Scope

### In scope (v1, by 14 Oct)

One course unit: MIT 6.041 lectures 1–3 (probability models, conditioning and Bayes' rule, independence) with their slides, and OpenStax *Introductory Statistics 2e* chapter 3, all openly licensed.

### Out of scope (v1)

- Multiple courses or multi-tenant accounts, authentication beyond a simple student id
- Training or fine-tuning neural models
- Full audio tutoring (only optional text-to-speech read-out)
- Mobile apps (responsive web only)
- Teacher dashboards and class analytics

## 6. Requirements

Priority: **P0** = required by the hackathon statement, **P1** = scored optional enhancement, **P2** = only if time remains. IDs map to the statement's requirement numbers.

### 6.1 Multimodal knowledge base (Req 1)

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| KB-1 | Ingest MP4/YouTube URL, PDF and PPTX with no manual preprocessing | P0 | Upload any of the three; status goes pending → ready without manual steps |
| KB-2 | Every content unit stores its origin | P0 | Each unit has a locator: page, slide number, or start/end seconds |
| KB-3 | Organise content into topic → subtopic → concept with prerequisites | P0 | Concept graph has 15–40 concepts, every concept has a parent topic, no prerequisite cycles |
| KB-4 | Tag every unit to concepts | P0 | ≥ 95% of units have 1–3 concept tags with confidence |
| KB-5 | Extract information from images, diagrams and figures | P0 | Figures in PDFs and slides, and keyframes in videos, have stored descriptions that are searchable |
| KB-6 | Show ingestion progress | P1 | Library screen shows per-source status and unit counts |

### 6.2 Source grounding (Req 2)

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| GR-1 | Answers use cited excerpts | P0 | Every sentence in an answer carries ≥ 1 unit citation |
| GR-2 | Citations open the exact location | P0 | Clicking a citation opens the PDF page, slide image, or video seeked to the start time |
| GR-3 | Decline queries the material does not cover | P0 | Below the coverage threshold, the tutor declines and says what is missing |
| GR-4 | Separate outside knowledge from source-backed content | P0 | Unsupported sentences appear only in a labelled "Outside your material" box |
| GR-5 | Student can opt into general knowledge | P1 | A toggle allows outside answers, always shown in the separate box |

### 6.3 Adaptive assessment (Req 3)

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| AS-1 | Generate quizzes and mock exams on student-chosen scope | P0 | Student picks concepts/topics and a mix of MCQ, short answer, numerical |
| AS-2 | Tag each question with topic, source location and difficulty | P0 | Every question stores concept id, anchor units and difficulty 0–1 |
| AS-3 | Verify question correctness | P0 | Every released question passed its type's check (blind second-model answer, SymPy run, or rubric check); log kept |
| AS-4 | No repeated questions across assessments | P0 | New questions above the similarity threshold to any seen question are rejected |
| AS-5 | Cited feedback on each answer | P0 | Feedback explains the correct answer with a citation chip |
| AS-6 | Post-assessment report | P0 | Shows score per topic, mastery change, weak topics, likely misconceptions, next units to study |
| AS-7 | Difficulty adapts to mastery | P0 | Target difficulty comes from the learner model |

### 6.4 Learner model (Req 4)

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| LM-1 | Per-concept mastery estimate | P0 | BKT P(known) per student per concept, stored with history |
| LM-2 | Update after every quiz answer | P0 | Each graded attempt updates mastery and writes a log row |
| LM-3 | Update after conversations | P0 | Tutor check questions update mastery at half weight |
| LM-4 | Handle new students | P0 | Intake sets priors; diagnostic quiz of ~10 questions targets highest-uncertainty topics |
| LM-5 | Forgetting and review | P1 | Mastered concepts become due for review as estimated recall decays |
| LM-6 | Prerequisite-aware recommendations | P1 | Weak concept with weak prerequisite → recommend the prerequisite first |

### 6.5 System evaluation (Req 5)

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| EV-1 | Framework-based RAG evaluation | P0 | RAGAS faithfulness, answer relevancy, context precision, context recall reported |
| EV-2 | Team-built test set | P0 | ~40 questions with gold locators, including ≥ 10 off-material (see TESTSET_FORMAT.md) |
| EV-3 | Personalization evaluation | P0 | Simulated students across sessions; mastery gain and repetition rate reported vs a baseline |
| EV-4 | Ablations and honest reporting | P1 | Retrieval and claim-check ablations; failures listed |

### 6.6 Optional enhancements (Req 6)

| ID | Requirement | Priority |
|---|---|---|
| OP-1 | Course flow map of topics and prerequisites, coloured by mastery | P1 |
| OP-2 | Flashcards for weak concepts | P1 |
| OP-3 | Study schedule from weak topics, review due dates and exam date | P1 |
| OP-4 | Hindi explanations of English material | P1 |
| OP-5 | Audio tutoring | P2 (text-to-speech read-out only) |

## 7. Key user flows

1. **Upload:** Library → upload file or paste URL → watch status → see unit counts and the concept map appear.
2. **Start:** New student → intake (goal, exam date, self-rated familiarity) → 10-question diagnostic → dashboard with initial mastery.
3. **Learn:** Ask the tutor → cited answer → click a chip → source opens at the exact place → answer the tutor's check question → mastery updates.
4. **Practise:** Assess → choose scope and mix → answer → cited feedback per question → report with weak topics and misconceptions.
5. **Plan:** Dashboard → reviews due, recommended next units, study schedule to the exam date.

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | Tutor answer < 10 s typical; quiz of 10 questions generated < 60 s (pre-generation allowed) |
| Cost | All LLM calls cached on disk; total API spend kept within free tiers plus a few dollars (estimate) |
| Reproducibility | Evaluation runs from one command with fixed seeds and cached calls |
| Reliability | Ingestion is idempotent; a failed source can be re-run without duplicates |
| Security | Keys only in `.env`; numerical-verification code runs in a sandboxed subprocess with a timeout and no network |
| Licensing | Every course source has an open license stated in the README |
| Accessibility | Readable at phone width; keyboard-usable chat and quiz |

## 9. Deliverables (from the statement)

- [ ] Working prototype at a public URL: ingestion, grounded chat, assessment generator, dashboard
- [ ] Documentation: architecture, grounding method, learner model (`docs/architecture.md`, `docs/grounding.md`, `docs/learner_model.md`)
- [ ] Evaluation results: RAGAS tables, ablations, simulation charts, committed test set (`docs/results.md`)
- [ ] Demo video, 3–10 minutes on YouTube: upload workflow, grounded chat, assessment pipeline, architecture

## 10. Milestones

Compressed after a 3-day slip (DECISIONS #10).

| Date | Milestone |
|---|---|
| Sat 10 Oct | Setup verified; textbook and slides ingested; BKT written |
| Sun 11 Oct | Video ingested; concept graph; grounded chat API; question bank; test set at 40 |
| Mon 12 Oct | Learner model; core frontend (chat + source viewer, quiz, report, dashboard) |
| Tue 13 Oct | Library, intake, course map; deployed; simulation + RAGAS results |
| Wed 14 Oct | Fixes, docs, demo video, submit by 10 PM |

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Whisper too slow locally | Video ingestion blocked | Transcribe on Colab GPU, import segments JSON |
| Rate limits / cost | Pipeline stalls | Disk cache, small course scope, batch calls |
| Verifier rejects many questions | Thin question bank | Pre-generate early; relax to two-model agreement and report the rate |
| Frontend overruns | Weak demo | Build chat + source viewer first; plain components elsewhere |
| Low RAGAS scores | Lower eval impression | Report honestly with ablations; rigor is scored |
| Solo time limits | Missed deliverables | Cut P1/P2 first; never cut evaluation or the demo video |

## 12. Open questions

- [x] Course unit: MIT 6.041 lectures 1–3 + slides, OpenStax Introductory Statistics 2e ch. 3 (DECISIONS #9)
- [ ] Which OpenRouter model for verification (different provider from Gemini)?
- [ ] Hosting for the API: Render or Railway?
