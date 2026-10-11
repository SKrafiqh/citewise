"""Grounded question generation from anchor units (AS-1, AS-2)."""
import hashlib

from app.assess.models import QuestionDraft, validate_draft
from app.llm import generate_json
from app.prompts import render

TYPE_RULES = {
    "mcq": (
        'Return JSON: {"stem":"...","options":[{"key":"A","text":"...","misconception":null},...4 options A-D...],'
        '"answer":"B","explanation":"..."}. Exactly one option is correct. Every WRONG option has a short '
        '"misconception" label naming the mistake it represents (e.g. "confuses P(A|B) with P(B|A)").'
    ),
    "numerical": (
        'Return JSON: {"stem":"...","answer":{"value":0.25,"tol":0.005},"explanation":"..."}. The answer is a single '
        "number computed from quantities in the stem. If the excerpts contain nothing to compute, return {\"skip\": true}."
    ),
    "short": (
        'Return JSON: {"stem":"...","rubric":["key point 1","key point 2"],"explanation":"..."}. 2-4 rubric points, '
        "each a fact stated in the excerpts."
    ),
}
EXCERPT_CHARS = 1200


class SkipQuestion(Exception):
    """The model declared the excerpts unsuitable for this question type."""


def question_id(concept_id: str, stem: str) -> str:
    return "q_" + hashlib.sha1(f"{concept_id}|{stem}".encode()).hexdigest()[:12]


def format_anchors(units: list[dict]) -> str:
    return "\n\n".join(
        f"[{u['id']}] {u['text'][:EXCERPT_CHARS]}" + (f"\nFigure: {u['figure_desc'][:EXCERPT_CHARS]}" if u.get("figure_desc") else "")
        for u in units
    )


def generate_draft(concept: dict, units: list[dict], qtype: str, difficulty: float, temperature: float = 0.4) -> QuestionDraft:
    prompt = render(
        "question",
        concept=f"{concept['name']}: {concept['summary']}",
        qtype=qtype,
        difficulty=f"{difficulty:.2f}",
        type_rules=TYPE_RULES[qtype],
        excerpts=format_anchors(units),
    )
    raw = generate_json(prompt, temperature=temperature)
    if raw.get("skip"):
        raise SkipQuestion(qtype)
    return validate_draft(raw, qtype)
