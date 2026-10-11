"""Students, learner model and assessments (AS-1..AS-7, LM-1..LM-6)."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, field_validator

from app.api.deps import STUDENT_ID, LimitedDep
from app.assess import service
from app.assess.models import QTYPES
from app.citations import build_citation
from app.db import connect
from app.kb.graph import load_graph
from app.learner import policy, store
from app.qa.retrieve import fetch_hits

router = APIRouter()
ID = Field(max_length=40)
ASSESSMENT_ID = Path(max_length=40)


class StudentIn(BaseModel):
    name: str | None = Field(default=None, max_length=80)


class IntakeIn(BaseModel):
    goal: str | None = Field(default=None, max_length=200)
    exam_date: date | None = None
    familiarity: dict[str, int] = Field(default_factory=dict, max_length=50)

    @field_validator("familiarity")
    @classmethod
    def levels_in_range(cls, value: dict[str, int]) -> dict[str, int]:
        if any(v not in (0, 1, 2) for v in value.values()):
            raise ValueError("familiarity levels must be 0, 1 or 2")
        return value


class AssessmentIn(BaseModel):
    student_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    kind: Literal["diagnostic", "quiz", "mock_exam"] = "quiz"
    scope: list[str] = Field(default_factory=list, max_length=50)
    n: int = Field(default=10, ge=1, le=30)
    mix: dict[str, float] | None = None

    @field_validator("mix")
    @classmethod
    def valid_mix(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is None:
            return None
        if set(value) - set(QTYPES) or any(w < 0 for w in value.values()) or sum(value.values()) <= 0:
            raise ValueError(f"mix needs non-negative weights over {list(QTYPES)}")
        return value


class AnswerIn(BaseModel):
    question_id: str = ID
    response: str = Field(min_length=1, max_length=2000)


@router.post("/students", status_code=201, dependencies=[LimitedDep])
def create_student(body: StudentIn) -> dict:
    with connect() as conn:
        return {"student_id": store.create_student(conn, body.name)}


@router.post("/students/{student_id}/intake", dependencies=[LimitedDep])
def save_intake(body: IntakeIn, student_id: str = STUDENT_ID) -> dict:
    graph = load_graph()
    unknown = set(body.familiarity) - set(graph.topics)
    if unknown:
        raise HTTPException(422, f"unknown topic ids: {sorted(unknown)}")
    with connect() as conn:
        try:
            count = store.save_intake(conn, student_id, body.goal, body.exam_date, body.familiarity, graph)
        except LookupError:
            raise HTTPException(404, "Student not found") from None
    return {"priors_set": count}


def _mastery_view(student_id: str):
    graph = load_graph()
    with connect() as conn:
        if not conn.execute("select 1 from students where id = %s", (student_id,)).fetchone():
            raise HTTPException(404, "Student not found")
        rows = store.get_mastery(conn, student_id)
    return graph, rows, store.p_known_map(rows), store.due_concepts(rows)


@router.get("/students/{student_id}/mastery")
def get_mastery(student_id: str = STUDENT_ID) -> dict:
    graph, rows, p, due = _mastery_view(student_id)
    concepts = [
        {"concept_id": cid, "name": c["name"], "topic_id": c["topic_id"], "topic_name": graph.topics[c["topic_id"]],
         "p_known": p.get(cid, policy.DEFAULT_P0), "n_obs": rows[cid]["n_obs"] if cid in rows else 0, "due": cid in due}
        for cid, c in graph.concepts.items()
    ]
    topics = [
        {"topic_id": t, "name": name, "mean": sum(c["p_known"] for c in concepts if c["topic_id"] == t) / max(1, sum(c["topic_id"] == t for c in concepts))}
        for t, name in graph.topics.items()
    ]
    return {"concepts": concepts, "topics": topics}


@router.get("/students/{student_id}/recommendations")
def get_recommendations(student_id: str = STUDENT_ID) -> list[dict]:
    graph, _, p, due = _mastery_view(student_id)
    recs = policy.recommend(sorted(graph.concepts), p, graph.prereqs, due)
    with connect() as conn:
        for rec in recs:
            ids = [r["unit_id"] for r in conn.execute(
                "select unit_id from unit_concepts where concept_id = %s order by confidence desc limit 2", (rec["concept_id"],)).fetchall()]
            rec["name"] = graph.concepts[rec["concept_id"]]["name"]
            rec["units"] = [build_citation(h) for h in fetch_hits(conn, ids)]
    return recs


@router.post("/assessments", status_code=201, dependencies=[LimitedDep])
def create_assessment(body: AssessmentIn) -> dict:
    return service.create_assessment(body.student_id, body.kind, body.scope, body.n, body.mix)


@router.post("/assessments/{assessment_id}/answer", dependencies=[LimitedDep])
def answer_question(body: AnswerIn, assessment_id: str = ASSESSMENT_ID) -> dict:
    return service.submit_answer(assessment_id, body.question_id, body.response)


@router.get("/assessments/{assessment_id}/report")
def get_report(assessment_id: str = ASSESSMENT_ID) -> dict:
    return service.get_report(assessment_id)
