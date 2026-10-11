"""Grading: exact for MCQ and numerical, rubric-based partial credit for short answers (AS-5)."""
import re
from dataclasses import dataclass

from app.llm import generate_json
from app.prompts import render

CORRECT_SCORE = 0.6  # short answers at or above this count as correct for BKT


@dataclass(frozen=True)
class Grade:
    correct: bool
    score: float
    misconception: str | None = None


def parse_number(text: str) -> float | None:
    """'1,234.5', '3/4', '12%' -> float (percent sign dropped; caller also tries value/100)."""
    cleaned = str(text).strip().replace(",", "").rstrip("%").strip()
    if match := re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", cleaned):
        return float(match[1]) / float(match[2]) if float(match[2]) else None
    try:
        return float(cleaned)
    except ValueError:
        return None


def grade_mcq(options: list[dict], key: str, response: str) -> Grade:
    chosen = str(response).strip().upper()
    if chosen == key:
        return Grade(True, 1.0)
    label = next((o["misconception"] for o in options if o["key"] == chosen), None)
    return Grade(False, 0.0, label)


def grade_numerical(key: dict, response: str) -> Grade:
    value = parse_number(response)
    if value is None:
        return Grade(False, 0.0)
    candidates = [value, value / 100] if str(response).strip().endswith("%") else [value]
    ok = any(abs(c - key["value"]) <= key["tol"] for c in candidates)
    return Grade(ok, 1.0 if ok else 0.0)


def score_short(points: list[str], met: set[int]) -> Grade:
    score = len(met & set(range(len(points)))) / len(points)
    return Grade(score >= CORRECT_SCORE, score)


def grade_short(points: list[str], response: str) -> Grade:
    listing = "\n".join(f"{i}. {p}" for i, p in enumerate(points))
    result = generate_json(render("grade_short", points=listing, response=response[:2000]), temperature=0.0)
    met = {p.get("i") for p in result.get("points", []) if p.get("met") is True and isinstance(p.get("i"), int)}
    return score_short(points, met)


def grade(question: dict, response: str) -> Grade:
    if question["qtype"] == "mcq":
        return grade_mcq(question["options"], question["answer_key"], response)
    if question["qtype"] == "numerical":
        return grade_numerical(question["answer_key"], response)
    return grade_short(question["answer_key"]["points"], response)


def correct_answer_text(question: dict) -> str:
    key = question["answer_key"]
    if question["qtype"] == "mcq":
        return next(f"{o['key']}. {o['text']}" for o in question["options"] if o["key"] == key)
    if question["qtype"] == "numerical":
        return f"{key['value']:g}"
    return "; ".join(key["points"])
