"""Second-model claim check: does each cited excerpt support its sentence? (GR-4)"""
from app.llm import verify_json
from app.prompts import render
from app.qa.answer import Sentence
from app.qa.retrieve import Hit

CITED_CHARS = 1500


def check_claims(sentences: list[Sentence], hits: list[Hit]) -> list[bool]:
    """One bool per sentence. Anything the judge does not explicitly mark supported counts as unsupported."""
    by_id = {h.unit_id: h for h in hits}
    items = []
    for i, s in enumerate(sentences):
        cited = "\n".join(f"[{c}] {by_id[c].text[:CITED_CHARS]} {by_id[c].figure_desc or ''}" for c in s.cites if c in by_id)
        items.append(f"Sentence {i}: {s.text}\nCited excerpts:\n{cited}")
    result = verify_json(render("claim_check", items="\n\n".join(items)))
    verdicts = {r.get("i"): r.get("supported") is True for r in result.get("results", []) if isinstance(r, dict)}
    return [verdicts.get(i, False) for i in range(len(sentences))]
