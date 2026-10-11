"""Hybrid retrieval: pgvector + full-text search fused with reciprocal rank fusion (GR-1)."""
import re
from dataclasses import dataclass

from pgvector import Vector

from app.db import connect
from app.llm import embed

RRF_K = 60
POOL = 30
MODES = ("vector", "hybrid")


@dataclass(frozen=True)
class Hit:
    unit_id: str
    source_id: str
    source_title: str
    source_uri: str
    modality: str
    locator: dict
    text: str
    figure_desc: str | None


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit]
    top_sim: float  # best cosine similarity of any unit to the query (used by the coverage gate)


def or_tsquery(question: str) -> str | None:
    """Alphanumeric words joined with OR; safe to pass to to_tsquery."""
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 1]
    return " | ".join(dict.fromkeys(words)) or None


def rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal rank fusion of several ranked id lists."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores


def fetch_hits(conn, ids: list[str]) -> list[Hit]:
    rows = conn.execute(
        """select u.id, u.source_id, s.title, s.uri, u.modality, u.locator, u.text, u.figure_desc
           from units u join sources s on s.id = u.source_id where u.id = any(%s)""",
        (ids,),
    ).fetchall()
    by_id = {r["id"]: Hit(r["id"], r["source_id"], r["title"], r["uri"], r["modality"], r["locator"], r["text"], r["figure_desc"]) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def retrieve(question: str, mode: str = "hybrid", top_k: int = 6) -> Retrieval:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    query_vec = Vector(embed([question], task_type="RETRIEVAL_QUERY")[0])
    with connect() as conn:
        vector_rows = conn.execute(
            """select id, 1 - (embedding <=> %(q)s) as sim from units where embedding is not null
               order by embedding <=> %(q)s limit %(n)s""",
            {"q": query_vec, "n": POOL},
        ).fetchall()
        rankings = [[r["id"] for r in vector_rows]]
        tsquery = or_tsquery(question) if mode == "hybrid" else None
        if tsquery:
            rankings.append([r["id"] for r in conn.execute(
                """select id from units where tsv @@ to_tsquery('english', %(t)s)
                   order by ts_rank_cd(tsv, to_tsquery('english', %(t)s)) desc limit %(n)s""",
                {"t": tsquery, "n": POOL},
            ).fetchall()])
        fused = rrf(rankings)
        ids = sorted(fused, key=fused.get, reverse=True)[:top_k]
        hits = fetch_hits(conn, ids)
    return Retrieval(hits, float(vector_rows[0]["sim"]) if vector_rows else 0.0)
