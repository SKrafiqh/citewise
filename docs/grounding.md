# Grounding method

Rule: tutor content is only ever produced from retrieved course units, and every sentence must point at them.

## How content is stored with its origin
Each unit is one PDF page, one slide or one 60–90 s video window. It keeps its `source_id`, modality and an exact locator (1-based page/slide numbers, whole seconds for video), the text, a vision description of its figures (`figure_desc`), a 768-d embedding and a generated `tsvector`. Page/slide images are rendered next to the text so the UI can show the exact place.

## Retrieval
Vector search (cosine, pgvector HNSW) and full-text search (OR-joined sanitized keywords, `ts_rank_cd`) each return 30 candidates; reciprocal rank fusion (k = 60) keeps the top 6. `mode=vector` skips the full-text list (ablation).

## Coverage gate and how the threshold is chosen
The gate declines when the best vector cosine similarity is below `COVERAGE_THRESHOLD` (default 0.6, a placeholder). `python -m eval.run_rag_eval --tune-gate` picks the value that maximises decline F1 on a seeded 70% split of the hand-written test set and reports precision/recall on the held-out 30%. No reranker is used in production: a cross-encoder would not fit the free hosting tier, and the gate does not depend on one.

## Cited generation
`prompts/answer.md` instructs the model to answer only from the excerpts and to return `{sentences:[{text, cites}], outside, declined}`. Code then enforces it: cites not in the retrieved set are removed, sentences without a surviving cite are removed from the answer (moved to "outside" only if the student opted in), and an answer with no grounded sentence becomes a decline.

## Claim check and the "Outside your material" box
A different-provider model judges each sentence against the text of its cited excerpts. Anything not explicitly marked supported is treated as unsupported. Unsupported sentences are dropped, or shown in a visibly separate "Outside your material" box when the student turned on general knowledge. If nothing survives, the tutor declines rather than guess.

## Measured results
See [results.md](results.md). No numbers are quoted here until they have been run.

## Known limitations
- The gate uses one similarity score; a question about a topic that is only *mentioned* in the material can pass it. The claim check is the second line of defence.
- Video windows are cut by time, not meaning, when captions have no punctuation.
- The claim check is an LLM judgement and can be wrong in both directions; the ablation (claim check on/off) quantifies it.
- Sentence-level citations are only as precise as the unit (a page or a 60–90 s window).
