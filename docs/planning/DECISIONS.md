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
| 12 | 10 Oct | Concept graph built from compact unit digests in one LLM pass (with validation feedback loop) | Per-source summarisation stage first | Fewer calls; course is small enough for one context; validation catches bad graphs |
| 13 | 10 Oct | No cross-encoder reranker; gate on top-1 cosine similarity; retrieval ablations are vector vs hybrid and claim check on/off | bge-reranker-v2-m3 | The reranker needs ~2 GB RAM and would not fit the free API host; the gate must not depend on it |
| 14 | 10 Oct | Deterministic chat pipeline plus one check question per answer, no LLM tool-calling loop (`tutor/agent.py` dropped) | TRD §4.6 tool loop | Same behaviour with fewer failure modes and cost; the check question gives the half-weight evidence |
| 15 | 10 Oct | Quizzes pick all questions at creation time from a pre-verified bank | Generate each question live | Instant quizzes, verification already logged; adaptation happens between quizzes |
| 16 | 10 Oct | Ingestion endpoints need `ADMIN_TOKEN`; LLM-spending routes are rate-limited per IP; RLS enabled with no policies | Open endpoints | The API spends the owner's API budget; the DB is reached only through the API |
| 17 | 10 Oct | RAGAS pinned to 0.2.15 with langchain < 1 | Latest ragas | ragas 0.4.3 and 0.2.15 fail to import against langchain-community ≥ 0.4 |
| 18 | 10 Oct | Numerical verification: the second model writes ONE arithmetic expression, evaluated by an `ast` allowlist (`assess/safe_eval.py`); no code execution, no subprocess | TRD §4.4: model-written SymPy run in a sandboxed subprocess | A security review escaped the AST-allowlisted SymPy sandbox (`from sympy.utilities.misc import os`); an expression evaluator has nothing to escape from and covers probability/statistics arithmetic (comb, factorial, exp, ...) |

