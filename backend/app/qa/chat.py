"""Grounded tutoring turn: retrieve -> gate -> cited answer -> claim check -> citations (GR-1..GR-5)."""
import logging
from collections import defaultdict

from psycopg.types.json import Jsonb

from app.citations import build_citation
from app.db import connect
from app.learner import store
from app.qa import answer, claimcheck, gate, retrieve
from app.qa.retrieve import Hit
from app.tutor.check import pick_check_question

log = logging.getLogger(__name__)
LEVEL_CONCEPTS = 2
CHECK_CONCEPTS = 3


def _declined(message: str, retrieval: retrieve.Retrieval) -> dict:
    return {
        "declined": True, "message": message, "sentences": [], "citations": [], "outside": [],
        "top_sim": retrieval.top_sim, "retrieved": [h.unit_id for h in retrieval.hits], "check_question": None,
    }


def concepts_for_units(conn, unit_ids: list[str]) -> list[str]:
    """Concept ids ranked by total tag confidence across the given units."""
    weight: dict[str, float] = defaultdict(float)
    for r in conn.execute("select concept_id, confidence from unit_concepts where unit_id = any(%s)", (unit_ids,)).fetchall():
        weight[r["concept_id"]] += r["confidence"]
    return sorted(weight, key=lambda c: -weight[c])


def _level_for(conn, student_id: str | None, concept_ids: list[str]) -> float | None:
    if not student_id or not concept_ids:
        return None
    mastery = store.p_known_map(store.get_mastery(conn, student_id))
    values = [mastery.get(c, 0.2) for c in concept_ids[:LEVEL_CONCEPTS]]
    return sum(values) / len(values)


def _cited_hits(sentences: list[answer.Sentence], hits: list[Hit]) -> list[Hit]:
    by_id = {h.unit_id: h for h in hits}
    order = dict.fromkeys(c for s in sentences for c in s.cites)
    return [by_id[c] for c in order if c in by_id]


def _persist(student_id: str, question: str, response: dict) -> None:
    try:
        with connect() as conn:
            conn.execute("insert into chat_messages (student_id, role, content) values (%s, 'user', %s)", (student_id, Jsonb({"text": question})))
            conn.execute("insert into chat_messages (student_id, role, content) values (%s, 'assistant', %s)", (student_id, Jsonb(response)))
    except Exception:  # the answer is still valid; losing history must not fail the turn
        log.exception("could not store chat history")


def ask(question: str, student_id: str | None = None, allow_outside: bool = False, lang: str = "en",
        mode: str = "hybrid", use_claim_check: bool = True) -> dict:
    retrieval = retrieve.retrieve(question, mode)
    if not gate.covered(retrieval.top_sim):
        return _declined(gate.decline_reason(retrieval.hits), retrieval)

    with connect() as conn:
        hit_concepts = concepts_for_units(conn, [h.unit_id for h in retrieval.hits])
        level = answer.level_hint(_level_for(conn, student_id, hit_concepts))
    draft = answer.draft_answer(question, retrieval.hits, level, allow_outside, lang)
    if draft.declined:
        return _declined(draft.reason or gate.decline_reason(retrieval.hits), retrieval)

    sentences, outside = draft.sentences, list(draft.outside)
    if use_claim_check:
        verdicts = claimcheck.check_claims(sentences, retrieval.hits)
        outside += [s.text for s, ok in zip(sentences, verdicts) if not ok] if allow_outside else []
        sentences = [s for s, ok in zip(sentences, verdicts) if ok]
        if not sentences:
            return _declined("I could not verify an answer against your material, so I am not giving one.", retrieval)

    cited = _cited_hits(sentences, retrieval.hits)
    check_question = None
    if student_id:
        with connect() as conn:
            concepts = concepts_for_units(conn, [h.unit_id for h in cited])[:CHECK_CONCEPTS]
        check_question = pick_check_question(student_id, concepts)
    response = {
        "declined": False, "message": None,
        "sentences": [{"text": s.text, "cites": s.cites} for s in sentences],
        "citations": [build_citation(h) for h in cited],
        "outside": outside, "top_sim": retrieval.top_sim,
        "retrieved": [h.unit_id for h in retrieval.hits], "check_question": check_question,
    }
    if student_id:
        _persist(student_id, question, response)
    return response
