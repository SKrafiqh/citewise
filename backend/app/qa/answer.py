"""Cited answer generation: JSON sentences, each tied to excerpt ids (GR-1, GR-4)."""
from dataclasses import dataclass, field

from app.llm import generate_json
from app.prompts import render
from app.qa.retrieve import Hit

EXCERPT_CHARS = 1800
OUTSIDE_ALLOWED = (
    'The student opted into general knowledge: you may add up to 3 short sentences of it, '
    'but ONLY in "outside", with no citations.'
)
OUTSIDE_FORBIDDEN = 'Leave "outside" empty.'
LANGUAGES = {
    "en": "Write the answer in English.",
    "hi": "Write each sentence's text in Hindi (Devanagari); keep technical terms and formulas in English; keep ids unchanged.",
}


@dataclass(frozen=True)
class Sentence:
    text: str
    cites: list[str]


@dataclass
class Draft:
    declined: bool = False
    reason: str = ""
    sentences: list[Sentence] = field(default_factory=list)
    outside: list[str] = field(default_factory=list)


def level_hint(p_known: float | None) -> str:
    if p_known is None:
        return "an intermediate student; define terms briefly"
    if p_known < 0.4:
        return "a beginner; use simple words, short steps and recall prerequisites"
    if p_known > 0.8:
        return "an advanced student; be concise and end by posing a harder related question"
    return "an intermediate student; define terms briefly"


def format_excerpts(hits: list[Hit]) -> str:
    blocks = []
    for h in hits:
        body = h.text[:EXCERPT_CHARS] + (f"\nFigure: {h.figure_desc[:EXCERPT_CHARS]}" if h.figure_desc else "")
        blocks.append(f"[{h.unit_id}] ({h.source_title})\n{body}")
    return "\n\n".join(blocks)


def normalize(raw: dict, allowed_ids: set[str], allow_outside: bool) -> Draft:
    """Enforce grounding: unknown cite ids are dropped; uncited sentences never reach the main answer."""
    sentences: list[Sentence] = []
    outside = [str(o) for o in raw.get("outside", [])][:3] if allow_outside else []
    for item in raw.get("sentences", []):
        text = str(item.get("text", "")).strip()
        cites = [c for c in item.get("cites", []) if c in allowed_ids]
        if not text:
            continue
        if cites:
            sentences.append(Sentence(text, list(dict.fromkeys(cites))))
        elif allow_outside:
            outside.append(text)  # uncited claim -> labelled outside box, never the grounded answer
    if raw.get("declined") or not sentences:
        return Draft(declined=True, reason=str(raw.get("reason", "")).strip(), outside=outside)
    return Draft(sentences=sentences, outside=outside)


def draft_answer(question: str, hits: list[Hit], level: str, allow_outside: bool = False, lang: str = "en") -> Draft:
    prompt = render(
        "answer",
        outside_rule=OUTSIDE_ALLOWED if allow_outside else OUTSIDE_FORBIDDEN,
        level_hint=level,
        language_rule=LANGUAGES.get(lang, LANGUAGES["en"]),
        excerpts=format_excerpts(hits),
        question=question,  # untrusted: substituted last
    )
    return normalize(generate_json(prompt), {h.unit_id for h in hits}, allow_outside)
