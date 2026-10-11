"""Cross-model verification of generated questions (AS-3). Every outcome is logged."""
from app.assess.models import QuestionDraft
from app.assess.safe_eval import UnsafeExpression, evaluate
from app.llm import verify_json
from app.prompts import render


def _mcq(draft: QuestionDraft, excerpts: str) -> dict:
    options = "\n".join(f"{o['key']}. {o['text']}" for o in draft.options)
    result = verify_json(render("verify_mcq", excerpts=excerpts, options=options, stem=draft.stem))
    correct = sorted(str(c) for c in result.get("correct", []))
    return {"checker": "blind_mcq", "passed": correct == [draft.answer_key], "detail": {"second_model": correct, "key": draft.answer_key}}


def _numerical(draft: QuestionDraft, excerpts: str) -> dict:
    expression = str(verify_json(render("verify_numerical", excerpts=excerpts, stem=draft.stem)).get("expression", ""))
    key = draft.answer_key
    try:
        value = evaluate(expression)
    except UnsafeExpression as exc:
        return {"checker": "expression", "passed": False, "detail": {"error": str(exc), "expression": expression[:120]}}
    return {"checker": "expression", "passed": abs(value - key["value"]) <= key["tol"],
            "detail": {"computed": value, "key": key["value"], "expression": expression[:120]}}


def _short(draft: QuestionDraft, excerpts: str) -> dict:
    points = "\n".join(f"{i}. {p}" for i, p in enumerate(draft.answer_key["points"]))
    result = verify_json(render("verify_short", excerpts=excerpts, points=points))
    found = {p.get("i") for p in result.get("points", []) if p.get("found") is True}
    missing = [i for i in range(len(draft.answer_key["points"])) if i not in found]
    return {"checker": "rubric_in_source", "passed": not missing, "detail": {"missing_points": missing}}


_CHECKERS = {"mcq": _mcq, "numerical": _numerical, "short": _short}


def verify(draft: QuestionDraft, excerpts: str) -> dict:
    """Run the type's checker. A checker crash counts as a failed verification, never a pass."""
    try:
        check = _CHECKERS[draft.qtype](draft, excerpts)
    except Exception as exc:  # TRD §7: failures are logged and the question is not released
        check = {"checker": draft.qtype, "passed": False, "detail": {"error": f"{type(exc).__name__}: {exc}"}}
    return {"passed": check["passed"], "checks": [check]}
