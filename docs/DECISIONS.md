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
| 9 | | Course unit: _TBD_ | | |
