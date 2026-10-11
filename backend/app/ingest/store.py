"""Shared persistence for ingestion: sources, units, embeddings. Idempotent per source."""
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from pgvector import Vector

from app.db import connect
from app.llm import embed

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnitIn:
    locator: dict
    text: str
    figure_desc: str | None = None


def unit_id(source_id: str, locator: dict) -> str:
    """Deterministic, readable id: textbook-p87, slides-s14, lecture_01-t742."""
    if "page" in locator:
        return f"{source_id}-p{locator['page']}"
    if "slide" in locator:
        return f"{source_id}-s{locator['slide']}"
    return f"{source_id}-t{int(locator['t_start'])}"


def embedding_text(unit: UnitIn) -> str:
    return f"{unit.text}\n{unit.figure_desc}" if unit.figure_desc else unit.text


def public_error(exc: Exception) -> str:
    """The failure reason shown in the public library: our own messages only, never provider/DB internals."""
    if isinstance(exc, (ValueError, RuntimeError)):
        return str(exc)[:200]
    return f"{type(exc).__name__}: ingestion failed (details are in the server log)"


def set_status(source_id: str, status: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "update sources set status = %s, error = %s where id = %s",
            (status, error, source_id),
        )


def save_units(source_id: str, modality: str, units: list[UnitIn], prune: bool = True) -> int:
    """Upsert units (embedding them); with prune, delete units of this source that no longer exist."""
    vectors = embed([embedding_text(u) for u in units])
    ids = [unit_id(source_id, u.locator) for u in units]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """insert into units (id, source_id, modality, locator, text, figure_desc, embedding)
                   values (%s, %s, %s, %s::jsonb, %s, %s, %s)
                   on conflict (id) do update set locator = excluded.locator, text = excluded.text,
                     figure_desc = excluded.figure_desc, embedding = excluded.embedding""",
                [
                    (uid, source_id, modality, json.dumps(u.locator), u.text, u.figure_desc, Vector(v))
                    for uid, u, v in zip(ids, units, vectors)
                ],
            )
            if prune:
                cur.execute("delete from units where source_id = %s and id <> all(%s)", (source_id, ids))
    return len(units)


def ingest_source(
    source_id: str,
    *,
    title: str,
    modality: str,
    uri: str,
    license: str | None,
    build_units: Callable[[], list[UnitIn]],
    prune: bool = True,
) -> int:
    """Register the source, build its units, store them; mark ready or failed (re-runnable)."""
    with connect() as conn:
        conn.execute(
            """insert into sources (id, title, modality, uri, license, status)
               values (%s, %s, %s, %s, %s, 'ingesting')
               on conflict (id) do update set title = excluded.title, modality = excluded.modality,
                 uri = excluded.uri, license = excluded.license, status = 'ingesting', error = null""",
            (source_id, title, modality, uri, license),
        )
    try:
        units = build_units()
        if not units:
            raise ValueError("no content units were extracted")
        count = save_units(source_id, modality, units, prune)
    except Exception as exc:
        log.exception("ingestion failed for %s", source_id)
        set_status(source_id, "failed", public_error(exc))
        raise
    set_status(source_id, "ready")
    return count



def register_pending(source_id: str, title: str, modality: str, uri: str, license: str | None) -> None:
    """Create or reset a source row as 'pending' so the library shows it before ingestion starts."""
    with connect() as conn:
        conn.execute(
            """insert into sources (id, title, modality, uri, license, status) values (%s, %s, %s, %s, %s, 'pending')
               on conflict (id) do update set title = excluded.title, modality = excluded.modality,
                 uri = excluded.uri, license = excluded.license, status = 'pending', error = null""",
            (source_id, title, modality, uri, license),
        )
