"""Database side of the learner model: mastery rows, history and priors (LM-1, LM-2, LM-3)."""
import uuid
from datetime import date, datetime, timezone

from psycopg.types.json import Jsonb

from app.kb.graph import Graph
from app.learner import review
from app.learner.bkt import BKTParams, update
from app.learner.diagnostic import prior_for
from app.learner.policy import DEFAULT_P0


def get_mastery(conn, student_id: str) -> dict[str, dict]:
    rows = conn.execute(
        "select concept_id, p_known, stability, last_review, n_obs from mastery where student_id = %s", (student_id,)
    ).fetchall()
    return {r["concept_id"]: r for r in rows}


def p_known_map(mastery: dict[str, dict]) -> dict[str, float]:
    return {c: float(r["p_known"]) for c, r in mastery.items()}


def due_concepts(mastery: dict[str, dict], now: datetime | None = None) -> set[str]:
    now = now or datetime.now(timezone.utc)
    return {
        c for c, r in mastery.items()
        if r["last_review"] and review.is_due(r["p_known"], r["stability"], (now - r["last_review"]).total_seconds() / 86400)
    }


def apply_observation(conn, student_id: str, concept_id: str, correct: bool, weight: float, source: str, params: BKTParams) -> tuple[float, float]:
    """One graded observation: BKT update, review state, current row and history row."""
    conn.execute(
        "insert into mastery (student_id, concept_id, p_known) values (%s, %s, %s) on conflict do nothing",
        (student_id, concept_id, DEFAULT_P0),
    )
    row = conn.execute(
        "select p_known, stability from mastery where student_id = %s and concept_id = %s for update",
        (student_id, concept_id),
    ).fetchone()
    p_before = float(row["p_known"])
    p_after = update(p_before, correct, params, weight)
    conn.execute(
        """update mastery set p_known = %s, stability = %s, last_review = now(), n_obs = n_obs + 1, updated_at = now()
           where student_id = %s and concept_id = %s""",
        (p_after, review.next_stability(row["stability"], correct, p_after), student_id, concept_id),
    )
    conn.execute(
        "insert into mastery_log (student_id, concept_id, p_before, p_after, source) values (%s, %s, %s, %s, %s)",
        (student_id, concept_id, p_before, p_after, source),
    )
    return p_before, p_after


def init_priors(conn, student_id: str, familiarity: dict[str, int], graph: Graph) -> int:
    """Intake: self-rated familiarity sets P(L0) per concept. Concepts the student has already been
    assessed on keep their learned mastery, so re-submitting intake never erases progress."""
    existing = get_mastery(conn, student_id)
    count = 0
    for concept_id, concept in graph.concepts.items():
        level = familiarity.get(concept["topic_id"])
        current = existing.get(concept_id)
        if level is None or (current and current["n_obs"] > 0):
            continue
        prior = prior_for(level)
        conn.execute(
            """insert into mastery (student_id, concept_id, p_known) values (%s, %s, %s)
               on conflict (student_id, concept_id) do update set p_known = excluded.p_known, updated_at = now()""",
            (student_id, concept_id, prior),
        )
        conn.execute(
            "insert into mastery_log (student_id, concept_id, p_before, p_after, source) values (%s, %s, %s, %s, 'intake')",
            (student_id, concept_id, float(current["p_known"]) if current else DEFAULT_P0, prior),
        )
        count += 1
    return count


def create_student(conn, name: str | None) -> str:
    student_id = uuid.uuid4().hex
    conn.execute("insert into students (id, name) values (%s, %s)", (student_id, name))
    return student_id


def save_intake(conn, student_id: str, goal: str | None, exam_date: date | None, familiarity: dict[str, int], graph: Graph) -> int:
    """Store intake answers and turn familiarity into priors; returns how many concepts got one."""
    updated = conn.execute(
        "update students set exam_date = %s, profile = %s where id = %s",
        (exam_date, Jsonb({"goal": goal, "familiarity": familiarity}), student_id),
    ).rowcount
    if not updated:
        raise LookupError("student")
    return init_priors(conn, student_id, familiarity, graph)
