# Decision log

Short records of choices and why. Add one whenever you pick between options; judges and interviewers ask about these.

| # | Date | Decision | Alternatives | Why |
|---|---|---|---|---|
| 1 | 6 Oct | Track D (tutoring) | Tracks A, B, C | Fits RAG/agent skills; no neural training needed; clear gaps vs existing tools |
| 2 | 6 Oct | Build our own system, not fork OpenMAIC | Fork OpenMAIC | Large TS codebase; would read as repackaged; our edge is grounding + learner model, which it lacks |
| 3 | 6 Oct | Python + FastAPI backend | Node/Next.js only | RAGAS, Whisper, pyBKT are Python |
| 4 | 6 Oct | Postgres + pgvector for everything | Separate vector DB | One store for units, graph, attempts and mastery; hybrid search via tsvector |
| 5 | 6 Oct | BKT per concept | IRT, deep knowledge tracing | Interpretable, works with little data, no training; spaced repetition added for forgetting |
| 6 | 7 Oct | Gemini for generation/vision/embeddings, OpenRouter second model for verification | Single provider | Cross-model validation needs an independent model (Req 3b) |
| 7 | 7 Oct | 768-dim embeddings | 3072 | pgvector HNSW index limit and storage; quality adequate for one course |
| 8 | 7 Oct | Disk cache on every LLM call | No cache | Free reruns, reproducible evaluation |
| 9 | 10 Oct | Course unit: MIT 6.041 lectures 1–3 (probability models, conditioning and Bayes' rule, independence) + slides, with OpenStax *Introductory Statistics 2e* ch. 3 | Other subjects | Open licenses, real lecture videos with captions, slides with tree and Venn diagrams, textbook with figures and numericals; answers easy to verify by hand |
| 10 | 10 Oct | Compressed scope after losing 3 days: test set 40, audit 20, simulation 10 seeds, optional features limited to course map + Hindi toggle | Original scope | Keeps every P0 requirement; cuts only volume and P1 extras |
| 11 | 10 Oct | Video text from YouTube captions first, Whisper as fallback | Whisper only | Saves transcription time; same timestamped segments |
