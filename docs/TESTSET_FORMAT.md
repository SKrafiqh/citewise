# Test set format (`eval/testset.json`)

The test set measures retrieval, grounding, citation accuracy and refusal. It is written by hand from the course material, and **every gold answer and locator is checked by a person** (PRD EV-2). Commit it to the repo.

## Composition (~60 items)

| Slice | `kind` | Count | Notes |
|---|---|---|---|
| In-material, one source | `single` | 40 | ~15 video, ~15 textbook, ~10 slides; at least 5 must need a figure or diagram to answer |
| Multi-hop across sources | `multi_hop` | 10 | Needs evidence from two locations (e.g. textbook page + lecture moment) |
| Off-material | `off_material` | 10 | Plausible for the subject but not covered by the uploaded material; expected outcome is a decline |

## Item schema

```json
{
  "id": "q001",
  "kind": "single",
  "question": "What does the denominator in Bayes' rule represent?",
  "reference_answer": "The total probability of the evidence, summed over all hypotheses.",
  "gold": [
    {"source_id": "textbook", "modality": "pdf", "locator": {"page": 87}}
  ],
  "needs_figure": false,
  "concept_ids": ["c_bayes_rule"],
  "difficulty": "easy",
  "expected": "answer",
  "author_checked": true
}
```

| Field | Rules |
|---|---|
| `id` | `q001` … unique |
| `kind` | `single` · `multi_hop` · `off_material` |
| `question` | Phrased the way a student would ask it, not copied from the text |
| `reference_answer` | 1–3 sentences, true according to the material; empty for off-material |
| `gold` | 1 locator for single, 2+ for multi_hop, `[]` for off_material. Pages and slides are 1-based; video windows in seconds |
| `needs_figure` | `true` if the answer is only in a figure, diagram or chart |
| `concept_ids` | Filled after the concept graph exists (can be `[]` before Fri 9 Oct) |
| `difficulty` | `easy` · `medium` · `hard` |
| `expected` | `answer` or `decline` |
| `author_checked` | Set to `true` only after you opened the gold location and confirmed it |

## Writing tips

- Write questions while watching or reading; note the timestamp or page right away.
- Video gold windows: use the 20–40 s where the point is made, not the whole lecture.
- Off-material questions should be close to the topic (e.g. a related method the course never mentions), otherwise refusal is too easy and the number means little.
- Avoid questions whose answer appears in many places; they inflate citation scores.
