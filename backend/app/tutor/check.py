"""Tutor check question: one unseen, verified question on the concept just discussed (LM-3)."""
from app.assess.dedup import is_duplicate
from app.assess.selection import select_questions
from app.assess.service import public_question, seen_questions
from app.config import get_settings
from app.db import as_floats, connect
from app.kb.graph import load_graph


def pick_check_question(student_id: str, concept_ids: list[str]) -> dict | None:
    """First concept (in relevance order) that still has an unseen, non-duplicate question."""
    if not concept_ids:
        return None
    graph = load_graph()
    threshold = get_settings().dedup_threshold
    with connect() as conn:
        seen_ids, seen_embs = seen_questions(conn, student_id)
        rows = conn.execute(
            "select id, qtype, concept_id, difficulty, embedding from questions where verified and concept_id = any(%s)",
            (concept_ids,),
        ).fetchall()
        bank: dict[str, list[dict]] = {}
        for r in rows:
            bank.setdefault(r["concept_id"], []).append({**r, "embedding": as_floats(r["embedding"])})
        chosen, _ = select_questions(
            bank, ["mcq"], lambda excluded: next((c for c in concept_ids if c not in excluded), None),
            target_p=lambda c: 0.5, seen_ids=seen_ids, seen_embeddings=seen_embs,
            is_duplicate=lambda new, seen: is_duplicate(new, seen, threshold),
        )
        if not chosen:
            return None
        row = conn.execute(
            "select id, qtype, stem, options, concept_id, difficulty from questions where id = %s", (chosen[0]["id"],)
        ).fetchone()
    return public_question(row, graph)
