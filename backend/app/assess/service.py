"""Assessment lifecycle on the database: create, answer, report (AS-1, AS-5, AS-6, AS-7, LM-2, LM-3)."""
import uuid

import psycopg
from psycopg.types.json import Jsonb

from app.assess.grade import Grade, correct_answer_text, grade
from app.assess.report import WEAK_BELOW, build_report
from app.assess.selection import apportion, select_questions
from app.assess.dedup import is_duplicate
from app.citations import build_citation
from app.config import get_settings
from app.db import as_floats, connect
from app.kb.graph import Graph, load_graph
from app.learner import diagnostic, policy, store
from app.qa.retrieve import fetch_hits

DEFAULT_MIX = {"mcq": 6, "short": 2, "numerical": 2}
KINDS = ("diagnostic", "quiz", "mock_exam")
CHECK_WEIGHT = 0.5
NEXT_UNITS_PER_CONCEPT = 2


class NotFound(Exception):
    pass


class AlreadyAnswered(Exception):
    pass


def public_question(row: dict, graph: Graph) -> dict:
    return {
        "question_id": row["id"],
        "qtype": row["qtype"],
        "stem": row["stem"],
        "options": [{"key": o["key"], "text": o["text"]} for o in row["options"]] if row["options"] else None,
        "concept_id": row["concept_id"],
        "concept_name": graph.concepts[row["concept_id"]]["name"],
        "difficulty": row["difficulty"],
    }


def seen_questions(conn, student_id: str) -> tuple[set[str], list[list[float]]]:
    ids = {r["question_id"] for r in conn.execute(
        """select question_id from attempts where student_id = %(s)s
           union select aq.question_id from assessment_questions aq
                 join assessments a on a.id = aq.assessment_id where a.student_id = %(s)s""",
        {"s": student_id}).fetchall()}
    rows = conn.execute("select embedding from questions where id = any(%s) and embedding is not null", (list(ids),)).fetchall()
    return ids, [as_floats(r["embedding"]) for r in rows]


def create_assessment(student_id: str, kind: str, scope: list[str], n: int, mix: dict[str, float] | None) -> dict:
    graph = load_graph()
    threshold = get_settings().dedup_threshold
    with connect() as conn:
        if not conn.execute("select 1 from students where id = %s", (student_id,)).fetchone():
            raise NotFound("student")
        mastery_rows = store.get_mastery(conn, student_id)
        p = store.p_known_map(mastery_rows)
        due = store.due_concepts(mastery_rows)
        scope_concepts = graph.expand_scope(scope)
        if not scope_concepts:
            raise ValueError("scope matches no concepts")
        seen_ids, seen_embs = seen_questions(conn, student_id)
        bank_rows = conn.execute(
            "select id, qtype, concept_id, difficulty, embedding from questions where verified and concept_id = any(%s)",
            (scope_concepts,),
        ).fetchall()
        bank: dict[str, list[dict]] = {}
        for r in bank_rows:
            bank.setdefault(r["concept_id"], []).append({**r, "embedding": as_floats(r["embedding"])})

        if kind == "diagnostic":
            order = iter(diagnostic.diagnostic_concepts(p, {c: graph.concepts[c]["topic_id"] for c in scope_concepts}, len(scope_concepts)))
            next_concept = lambda excluded: next((c for c in order if c not in excluded), None)
            qtypes = apportion({"mcq": 1}, n)
        else:
            next_concept = lambda excluded: policy.pick_next(scope_concepts, p, due, graph.prereqs, exclude=excluded)
            qtypes = apportion(mix or DEFAULT_MIX, n)
        chosen, shortfall = select_questions(
            bank, qtypes, next_concept,
            target_p=lambda c: policy.target_difficulty(p.get(c, policy.DEFAULT_P0)),
            seen_ids=seen_ids, seen_embeddings=seen_embs,
            is_duplicate=lambda new, seen: is_duplicate(new, seen, threshold),
        )
        assessment_id = uuid.uuid4().hex
        conn.execute("insert into assessments (id, student_id, kind, scope) values (%s, %s, %s, %s)", (assessment_id, student_id, kind, scope or None))
        for position, q in enumerate(chosen):
            conn.execute("insert into assessment_questions (assessment_id, question_id, position) values (%s, %s, %s)", (assessment_id, q["id"], position))
        rows = {r["id"]: r for r in conn.execute(
            "select id, qtype, stem, options, concept_id, difficulty from questions where id = any(%s)", ([q["id"] for q in chosen],)).fetchall()}
    return {"assessment_id": assessment_id, "kind": kind, "questions": [public_question(rows[q["id"]], graph) for q in chosen], "shortfall": shortfall}


def _load_question(conn, question_id: str) -> dict:
    row = conn.execute(
        "select id, qtype, stem, options, answer_key, explanation, concept_id, anchor_units from questions where id = %s and verified",
        (question_id,),
    ).fetchone()
    if not row:
        raise NotFound("question")
    return row


def _feedback(question: dict, g: Grade, p_before: float, p_after: float, citations: list[dict]) -> dict:
    return {
        "correct": g.correct,
        "score": g.score,
        "correct_answer": correct_answer_text(question),
        "explanation": question["explanation"],
        "misconception": g.misconception,
        "citations": citations,
        "p_before": p_before,
        "p_after": p_after,
        "mastery_delta": p_after - p_before,
    }


def _record(student_id: str, question: dict, response: str, g: Grade, assessment_id: str | None, weight: float, source: str) -> dict:
    params = policy.bkt_params_for(question["qtype"], len(question["options"] or []) or 4)
    with connect() as conn:
        p_before, p_after = store.apply_observation(conn, student_id, question["concept_id"], g.correct, weight, source, params)
        citations = [build_citation(h) for h in fetch_hits(conn, question["anchor_units"])]
        feedback = _feedback(question, g, p_before, p_after, citations)
        try:
            conn.execute(
                """insert into attempts (assessment_id, student_id, question_id, response, correct, score, weight, feedback)
                   values (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (assessment_id, student_id, question["id"], Jsonb({"answer": response}), g.correct, g.score, weight, Jsonb(feedback)),
            )
        except psycopg.errors.UniqueViolation as exc:
            raise AlreadyAnswered() from exc
    return feedback


def submit_answer(assessment_id: str, question_id: str, response: str) -> dict:
    with connect() as conn:
        assessment = conn.execute("select student_id, kind from assessments where id = %s", (assessment_id,)).fetchone()
        if not assessment:
            raise NotFound("assessment")
        if not conn.execute("select 1 from assessment_questions where assessment_id = %s and question_id = %s", (assessment_id, question_id)).fetchone():
            raise NotFound("question in this assessment")
        if conn.execute("select 1 from attempts where assessment_id = %s and question_id = %s", (assessment_id, question_id)).fetchone():
            raise AlreadyAnswered()
        question = _load_question(conn, question_id)
    g = grade(question, response)  # may call an LLM, so it runs outside the transaction
    source = "diagnostic" if assessment["kind"] == "diagnostic" else "quiz"
    return _record(assessment["student_id"], question, response, g, assessment_id, 1.0, source)


def submit_check(student_id: str, question_id: str, response: str) -> dict:
    """Tutor check question: counts at half weight (LM-3) and is never asked twice."""
    with connect() as conn:
        if not conn.execute("select 1 from students where id = %s", (student_id,)).fetchone():
            raise NotFound("student")
        if conn.execute("select 1 from attempts where student_id = %s and question_id = %s", (student_id, question_id)).fetchone():
            raise AlreadyAnswered()
        question = _load_question(conn, question_id)
    return _record(student_id, question, response, grade(question, response), None, CHECK_WEIGHT, "check")


def get_report(assessment_id: str) -> dict:
    graph = load_graph()
    with connect() as conn:
        assessment = conn.execute("select student_id from assessments where id = %s", (assessment_id,)).fetchone()
        if not assessment:
            raise NotFound("assessment")
        total = conn.execute("select count(*) as n from assessment_questions where assessment_id = %s", (assessment_id,)).fetchone()["n"]
        rows = conn.execute(
            """select q.concept_id, a.correct, a.feedback from attempts a join questions q on q.id = a.question_id
               where a.assessment_id = %s order by a.answered_at""", (assessment_id,)).fetchall()
        attempts = [{"concept_id": r["concept_id"], "correct": r["correct"], "misconception": r["feedback"].get("misconception"),
                     "p_before": r["feedback"]["p_before"], "p_after": r["feedback"]["p_after"]} for r in rows]
        report = build_report(attempts, graph.concepts, graph.topics, total)
        weak = [c["concept_id"] for c in report["mastery_changes"] if c["after"] < WEAK_BELOW]
        report["next_units"] = _next_units(conn, weak)
        conn.execute(
            "update assessments set report = %s, finished_at = case when %s then coalesce(finished_at, now()) else finished_at end where id = %s",
            (Jsonb(report), len(attempts) >= total > 0, assessment_id),
        )
    return report


def _next_units(conn, concept_ids: list[str]) -> list[dict]:
    units: list[dict] = []
    for concept_id in concept_ids:
        ids = [r["unit_id"] for r in conn.execute(
            "select unit_id from unit_concepts where concept_id = %s order by confidence desc limit %s",
            (concept_id, NEXT_UNITS_PER_CONCEPT)).fetchall()]
        units.extend({"concept_id": concept_id, **build_citation(h)} for h in fetch_hits(conn, ids))
    return units
