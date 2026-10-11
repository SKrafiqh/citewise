import pytest

from app.assess import generate, grade, report, safe_eval, verify
from app.assess.models import validate_draft


def mcq_raw(**over):
    raw = {"stem": "Which is Bayes' rule?", "answer": "B", "explanation": "because",
           "options": [{"key": k, "text": f"opt {k}", "misconception": None if k == "B" else f"mis {k}"} for k in "ABCD"]}
    return {**raw, **over}


def test_validate_mcq_ok_and_rejections():
    assert validate_draft(mcq_raw(), "mcq").answer_key == "B"
    for bad in (mcq_raw(answer="E"), mcq_raw(options=mcq_raw()["options"][:3]), mcq_raw(stem=" ")):
        with pytest.raises(ValueError):
            validate_draft(bad, "mcq")
    opts = mcq_raw()["options"]
    opts[0]["misconception"] = None
    with pytest.raises(ValueError, match="misconception"):
        validate_draft(mcq_raw(options=opts), "mcq")
    opts = mcq_raw()["options"]
    opts[2]["text"] = opts[1]["text"]
    with pytest.raises(ValueError):
        validate_draft(mcq_raw(options=opts), "mcq")


def test_validate_numerical_and_short():
    d = validate_draft({"stem": "s", "explanation": "e", "answer": {"value": 0.25}}, "numerical")
    assert d.answer_key == {"value": 0.25, "tol": pytest.approx(0.0025)}
    with pytest.raises(ValueError):
        validate_draft({"stem": "s", "explanation": "e", "answer": {}}, "numerical")
    assert validate_draft({"stem": "s", "explanation": "e", "rubric": ["a", "b"]}, "short").answer_key == {"points": ["a", "b"]}
    with pytest.raises(ValueError):
        validate_draft({"stem": "s", "explanation": "e", "rubric": ["only one"]}, "short")


def test_generate_draft_skip_and_prompt(monkeypatch):
    monkeypatch.setattr(generate, "generate_json", lambda p, **kw: {"skip": True})
    with pytest.raises(generate.SkipQuestion):
        generate.generate_draft({"name": "c", "summary": "s"}, [{"id": "u1", "text": "t"}], "numerical", 0.5)
    seen = []
    monkeypatch.setattr(generate, "generate_json", lambda p, **kw: (seen.append(p), mcq_raw())[1])
    generate.generate_draft({"name": "Bayes", "summary": "s"}, [{"id": "u1", "text": "body", "figure_desc": "fig"}], "mcq", 0.5)
    assert "[u1] body" in seen[0] and "Figure: fig" in seen[0] and "Bayes" in seen[0]
    assert generate.question_id("c", "x") == generate.question_id("c", "x") != generate.question_id("c", "y")


def test_grade_mcq_reports_misconception():
    opts = mcq_raw()["options"]
    assert grade.grade_mcq(opts, "B", " b ").correct
    wrong = grade.grade_mcq(opts, "B", "C")
    assert not wrong.correct and wrong.misconception == "mis C"


def test_parse_number_variants():
    assert grade.parse_number("1,234.5") == 1234.5
    assert grade.parse_number("3/4") == 0.75
    assert grade.parse_number("12%") == 12
    assert grade.parse_number("abc") is None and grade.parse_number("1/0") is None


def test_grade_numerical_tolerance_and_percent():
    key = {"value": 0.25, "tol": 0.005}
    assert grade.grade_numerical(key, "1/4").correct and grade.grade_numerical(key, "0.252").correct
    assert not grade.grade_numerical(key, "0.3").correct and not grade.grade_numerical(key, "n/a").correct
    assert grade.grade_numerical(key, "25%").correct


def test_short_scoring_threshold():
    points = ["a", "b", "c"]
    assert grade.score_short(points, {0, 1}).correct and not grade.score_short(points, {0}).correct
    assert grade.score_short(points, {0, 9}).score == pytest.approx(1 / 3)


def test_grade_short_uses_model_verdicts(monkeypatch):
    monkeypatch.setattr(grade, "generate_json", lambda p, **kw: {"points": [{"i": 0, "met": True}, {"i": 1, "met": True}, {"i": 5, "met": True}]})
    assert grade.grade_short(["a", "b", "c"], "my answer").score == pytest.approx(2 / 3)


def test_safe_eval_computes_probability_expressions():
    assert safe_eval.evaluate("comb(5,2)/comb(10,2)") == pytest.approx(10 / 45)
    assert safe_eval.evaluate("1 - (1 - 0.1)**3") == pytest.approx(0.271)
    assert safe_eval.evaluate("exp(-2) * 2**3 / factorial(3)") == pytest.approx(0.18045, abs=1e-4)
    assert safe_eval.evaluate("-sqrt(16) + pi - pi") == -4.0


@pytest.mark.parametrize("bad", [
    "__import__('os').system('id')", "open('/etc/passwd')", "(1).__class__", "x + 1", "[1, 2]", "'a' * 3",
    "lambda: 1", "sympify('1')", "sqrt(2, key=3)", "9**9**9", "10**10000", "factorial(100000)", "", "1 +", "1/0", "a" * 400,
    "[c for c in ().__class__.__bases__]", "((9**999)**999)**999", "comb(100000, 3)", "factorial(399)**9",
])
def test_safe_eval_rejects_everything_else(bad):
    with pytest.raises(safe_eval.UnsafeExpression):
        safe_eval.evaluate(bad)


def test_verify_mcq_blind(monkeypatch):
    draft = validate_draft(mcq_raw(), "mcq")
    monkeypatch.setattr(verify, "verify_json", lambda p: {"correct": ["B"]})
    assert verify.verify(draft, "ex")["passed"]
    monkeypatch.setattr(verify, "verify_json", lambda p: {"correct": ["B", "C"]})
    assert not verify.verify(draft, "ex")["passed"]


def test_verify_numerical_evaluates_expression(monkeypatch):
    draft = validate_draft({"stem": "s", "explanation": "e", "answer": {"value": 0.25, "tol": 0.01}}, "numerical")
    monkeypatch.setattr(verify, "verify_json", lambda p: {"expression": "1/4"})
    assert verify.verify(draft, "ex")["passed"]
    monkeypatch.setattr(verify, "verify_json", lambda p: {"expression": "1/3"})
    log = verify.verify(draft, "ex")
    assert not log["passed"] and log["checks"][0]["detail"]["computed"] == pytest.approx(1 / 3)
    monkeypatch.setattr(verify, "verify_json", lambda p: {"expression": "__import__('os')"})
    assert not verify.verify(draft, "ex")["passed"]


def test_verify_short_and_crash_is_failure(monkeypatch):
    draft = validate_draft({"stem": "s", "explanation": "e", "rubric": ["a", "b"]}, "short")
    monkeypatch.setattr(verify, "verify_json", lambda p: {"points": [{"i": 0, "found": True}, {"i": 1, "found": False}]})
    log = verify.verify(draft, "ex")
    assert not log["passed"] and log["checks"][0]["detail"]["missing_points"] == [1]

    def boom(p):
        raise RuntimeError("api down")

    monkeypatch.setattr(verify, "verify_json", boom)
    assert not verify.verify(draft, "ex")["passed"]


def test_report_aggregates():
    concepts = {"c1": {"name": "C1", "topic_id": "t1"}, "c2": {"name": "C2", "topic_id": "t2"}}
    attempts = [
        {"concept_id": "c1", "correct": True, "misconception": None, "p_before": 0.2, "p_after": 0.5},
        {"concept_id": "c1", "correct": False, "misconception": "mixes up A|B", "p_before": 0.5, "p_after": 0.3},
        {"concept_id": "c2", "correct": False, "misconception": "mixes up A|B", "p_before": 0.2, "p_after": 0.1},
    ]
    r = report.build_report(attempts, concepts, {"t1": "T1", "t2": "T2"}, total_questions=4)
    assert (r["answered"], r["total"], r["correct"]) == (3, 4, 1)
    assert r["score_by_topic"][0]["name"] == "T2"
    assert next(c for c in r["mastery_changes"] if c["concept_id"] == "c1")["delta"] == pytest.approx(0.1)
    assert [w["name"] for w in r["weak_topics"]] == ["T2", "T1"]
    assert r["misconceptions"] == [{"label": "mixes up A|B", "count": 2}]
