"""Tag every unit with 1-3 concepts and a confidence (KB-4)."""
import logging

import numpy as np

from app.db import as_floats, connect
from app.llm import embed, generate_json
from app.prompts import render

log = logging.getLogger(__name__)
SHORTLIST = 5
MAX_TAGS = 3
BATCH = 10
UNIT_CHARS = 600


def shortlist(unit_vec: np.ndarray, concept_ids: list[str], concept_matrix: np.ndarray, k: int = SHORTLIST) -> list[str]:
    """Top-k concepts by cosine similarity to a unit embedding."""
    norms = np.linalg.norm(concept_matrix, axis=1) * (np.linalg.norm(unit_vec) or 1.0)
    sims = concept_matrix @ unit_vec / np.where(norms == 0, 1.0, norms)
    return [concept_ids[i] for i in np.argsort(-sims)[:k]]


def clean_tags(raw: list[dict] | None, candidates: list[str]) -> list[tuple[str, float]]:
    """Keep tags from the candidate list, clamp confidence, at most MAX_TAGS, best first."""
    best: dict[str, float] = {}
    for tag in raw or []:
        cid = tag.get("id")
        try:
            confidence = min(1.0, max(0.0, float(tag.get("confidence", 0))))
        except (TypeError, ValueError):
            continue
        if cid in candidates:
            best[cid] = max(confidence, best.get(cid, 0.0))
    return sorted(best.items(), key=lambda kv: -kv[1])[:MAX_TAGS]


def tag_batch(units: list[dict], candidates: dict[str, list[str]], concepts: dict[str, dict]) -> dict[str, list[tuple[str, float]]]:
    blocks = []
    for u in units:
        options = "; ".join(f"{c} = {concepts[c]['name']}: {concepts[c]['summary']}" for c in candidates[u["id"]])
        text = " ".join(f"{u['text']} {u['figure_desc'] or ''}".split())[:UNIT_CHARS]
        blocks.append(f"UNIT {u['id']}\nText: {text}\nCandidates: {options}")
    result = generate_json(render("tag_units", units="\n\n".join(blocks)))
    by_unit = {t.get("unit_id"): t.get("concepts") for t in result.get("tags", [])}
    return {u["id"]: clean_tags(by_unit.get(u["id"]), candidates[u["id"]]) for u in units}


def run() -> dict[str, float]:
    with connect() as conn:
        concepts = {r["id"]: r for r in conn.execute("select id, name, summary from concepts where level = 'concept'").fetchall()}
        units = conn.execute("select id, text, figure_desc, embedding from units where embedding is not null order by id").fetchall()
    if not concepts or not units:
        raise SystemExit("need ingested units and a concept graph first")
    ids = list(concepts)
    matrix = np.array(embed([f"{concepts[c]['name']}: {concepts[c]['summary']}" for c in ids]))
    candidates = {u["id"]: shortlist(np.array(as_floats(u["embedding"])), ids, matrix) for u in units}

    tags: dict[str, list[tuple[str, float]]] = {}
    for start in range(0, len(units), BATCH):
        tags.update(tag_batch(units[start : start + BATCH], candidates, concepts))
    fallbacks = 0
    for unit_id_, chosen in tags.items():
        if not chosen:  # model gave nothing usable: fall back to the nearest concept, low confidence
            tags[unit_id_] = [(candidates[unit_id_][0], 0.3)]
            fallbacks += 1

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from unit_concepts where unit_id = any(%s)", ([u["id"] for u in units],))
            cur.executemany(
                "insert into unit_concepts (unit_id, concept_id, confidence) values (%s, %s, %s)",
                [(uid, cid, conf) for uid, chosen in tags.items() for cid, conf in chosen],
            )
    log.info("tagged %d units (%d used the nearest-concept fallback)", len(units), fallbacks)
    return {"units": len(units), "fallback_share": fallbacks / len(units)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
