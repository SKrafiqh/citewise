"""Question drafts: validated shape of what the generator returns."""
from dataclasses import dataclass
from typing import Any

MCQ_KEYS = ["A", "B", "C", "D"]
QTYPES = ("mcq", "short", "numerical")


@dataclass(frozen=True)
class QuestionDraft:
    qtype: str
    stem: str
    options: list[dict] | None   # mcq: [{"key","text","misconception"}]
    answer_key: Any              # mcq: "B"; numerical: {"value","tol"}; short: {"points":[...]}
    explanation: str


def validate_draft(raw: dict, qtype: str) -> QuestionDraft:
    """Raise ValueError unless the generator output has the exact shape for its type."""
    stem = str(raw.get("stem", "")).strip()
    explanation = str(raw.get("explanation", "")).strip()
    if not stem or not explanation:
        raise ValueError("stem and explanation are required")
    if qtype == "mcq":
        options = [
            {"key": o.get("key"), "text": str(o.get("text", "")).strip(), "misconception": o.get("misconception")}
            for o in raw.get("options", [])
        ]
        key = raw.get("answer")
        if [o["key"] for o in options] != MCQ_KEYS:
            raise ValueError("mcq needs exactly options A-D in order")
        if key not in MCQ_KEYS or len({o["text"] for o in options}) != 4 or not all(o["text"] for o in options):
            raise ValueError("mcq needs a valid answer key and four distinct non-empty options")
        for o in options:
            if o["key"] != key and not o["misconception"]:
                raise ValueError(f"distractor {o['key']} needs a misconception label")
        return QuestionDraft("mcq", stem, options, key, explanation)
    if qtype == "numerical":
        answer = raw.get("answer") or {}
        try:
            value = float(answer["value"])
            tol = float(answer.get("tol", abs(value) * 0.01 or 1e-6))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("numerical needs answer.value") from exc
        if tol < 0:
            raise ValueError("tol must be >= 0")
        return QuestionDraft("numerical", stem, None, {"value": value, "tol": tol}, explanation)
    if qtype == "short":
        points = [str(p).strip() for p in raw.get("rubric", []) if str(p).strip()]
        if not 2 <= len(points) <= 4:
            raise ValueError("short needs 2-4 rubric points")
        return QuestionDraft("short", stem, None, {"points": points}, explanation)
    raise ValueError(f"unknown question type {qtype}")
