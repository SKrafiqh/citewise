"""Pre-generate and verify the question bank so quizzes are instant (AS-1, AS-2, AS-3, AS-4).

    python -m app.assess.bank --per-concept 8        # generate
    python -m app.assess.bank --report               # verification pass rate by type
"""
import argparse
import logging
from itertools import cycle, islice

from pgvector import Vector
from psycopg.types.json import Jsonb

from app.assess.dedup import is_duplicate
from app.assess.generate import SkipQuestion, format_anchors, generate_draft, question_id
from app.assess.verify import verify
from app.config import get_settings
from app.db import as_floats, connect
from app.kb.graph import load_graph
from app.llm import embed

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3  # first try + 2 regenerations (TRD §4.4)
QTYPE_CYCLE = ["mcq", "mcq", "numerical", "short", "mcq"]
DIFFICULTIES = [0.25, 0.5, 0.75]
ANCHOR_POOL = 6


def _anchor_units(conn, concept_id: str) -> list[dict]:
    return conn.execute(
        """select u.id, u.text, u.figure_desc from unit_concepts uc join units u on u.id = uc.unit_id
           where uc.concept_id = %s order by uc.confidence desc limit %s""",
        (concept_id, ANCHOR_POOL),
    ).fetchall()


def _store(conn, concept_id, anchors, difficulty, draft, vec, passed, log_entry) -> None:
    conn.execute(
        """insert into questions (id, qtype, stem, options, answer_key, concept_id, anchor_units, difficulty,
                                  verified, verify_log, embedding, explanation)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (id) do update set verified = excluded.verified, verify_log = excluded.verify_log,
             options = excluded.options, answer_key = excluded.answer_key, explanation = excluded.explanation,
             anchor_units = excluded.anchor_units, embedding = excluded.embedding""",
        (question_id(concept_id, draft.stem), draft.qtype, draft.stem, Jsonb(draft.options) if draft.options else None,
         Jsonb(draft.answer_key), concept_id, [a["id"] for a in anchors], difficulty, passed, Jsonb(log_entry),
         Vector(vec), draft.explanation),
    )


def make_one(conn, concept: dict, concept_id: str, pool: list[dict], qtype: str, difficulty: float, seen: list[list[float]]) -> bool:
    """Generate -> dedup -> verify, regenerating up to MAX_ATTEMPTS. True if a verified question was stored.

    Unverified attempts are stored too (verified = false) so pass rates can be reported honestly."""
    threshold = get_settings().dedup_threshold
    attempts: list[dict] = []
    for attempt in range(MAX_ATTEMPTS):
        anchors = list({u["id"]: u for u in (pool[attempt % len(pool)], pool[(attempt + 1) % len(pool)])}.values())
        try:
            draft = generate_draft(concept, anchors, qtype, difficulty, temperature=0.4 + 0.2 * attempt)
        except SkipQuestion:
            return False
        except Exception as exc:  # invalid draft or a provider error: count the attempt, keep the bank run alive
            attempts.append({"attempt": attempt, "error": f"{type(exc).__name__}: {str(exc)[:150]}"})
            continue
        vec = embed([draft.stem + " " + " ".join(o["text"] for o in draft.options or [])])[0]
        if is_duplicate(vec, seen, threshold):
            attempts.append({"attempt": attempt, "error": "duplicate of an existing question"})
            continue
        result = verify(draft, format_anchors(anchors))
        entry = {"attempts": attempts + [{"attempt": attempt, **result}]}
        _store(conn, concept_id, anchors, difficulty, draft, vec, result["passed"], entry)
        conn.commit()  # keep every outcome even if a later call fails
        attempts = entry["attempts"]
        if result["passed"]:
            seen.append(vec)
            return True
    return False


def build_bank(per_concept: int) -> dict[str, int]:
    graph = load_graph()
    made = 0
    with connect() as conn:
        seen = [as_floats(r["embedding"]) for r in conn.execute("select embedding from questions where verified and embedding is not null").fetchall()]
        for concept_id, concept in graph.concepts.items():
            pool = _anchor_units(conn, concept_id)
            if not pool:
                log.warning("no tagged units for %s; skipped", concept_id)
                continue
            have = conn.execute("select count(*) as n from questions where concept_id = %s and verified", (concept_id,)).fetchone()["n"]
            tries = islice(zip(cycle(QTYPE_CYCLE), cycle(DIFFICULTIES)), per_concept * 3)  # bounds API spend
            for qtype, difficulty in tries:
                if have >= per_concept:
                    break
                if make_one(conn, concept, concept_id, pool, qtype, difficulty, seen):
                    have += 1
                    made += 1
            conn.commit()
    return {"verified_new": made}


def pass_rates() -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "select qtype, count(*) as total, count(*) filter (where verified) as verified from questions group by qtype order by qtype"
        ).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or report on the verified question bank")
    parser.add_argument("--per-concept", type=int, default=8)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.report:
        for row in pass_rates():
            print(f"{row['qtype']:>10}: {row['verified']}/{row['total']} verified ({row['verified'] / row['total']:.0%})")
    else:
        print(build_bank(args.per_concept))


if __name__ == "__main__":
    main()
