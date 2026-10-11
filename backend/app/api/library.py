"""Knowledge-base endpoints: sources, units, concept graph (KB-1, KB-3, KB-6, GR-2)."""
import logging
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import AdminDep, LimitedDep
from app.citations import build_citation
from app.config import get_settings
from app.db import connect
from app.ingest import pdf, slides, video
from app.ingest.store import public_error, register_pending, set_status
from app.kb.graph import load_graph
from app.qa.retrieve import fetch_hits

log = logging.getLogger(__name__)
router = APIRouter()
SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
YOUTUBE_URL = re.compile(r"^https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]{11}(?:[&?][\w=&%-]*)?$")
CHUNK = 1024 * 1024


class UrlSourceIn(BaseModel):
    url: str = Field(max_length=200)
    title: str = Field(min_length=1, max_length=200)
    license: str | None = Field(default=None, max_length=100)
    source_id: str | None = None


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or uuid.uuid4().hex[:8]


def _source_id(requested: str | None, title: str) -> str:
    source_id = requested or _slug(title)
    if not SOURCE_ID.fullmatch(source_id):
        raise HTTPException(422, "source_id must be 2-41 characters of a-z, 0-9, '-' or '_'")
    return source_id


def _save_upload(file: UploadFile, destination: Path) -> None:
    limit = get_settings().max_upload_mb * CHUNK
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with destination.open("wb") as out:
        while chunk := file.file.read(CHUNK):
            written += len(chunk)
            if written > limit:
                out.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(413, f"File is larger than {get_settings().max_upload_mb} MB.")
            out.write(chunk)


@router.get("/sources")
def list_sources() -> list[dict]:
    with connect() as conn:
        return conn.execute(
            """select s.id, s.title, s.modality, s.license, s.status, s.error, s.created_at, count(u.id) as units
               from sources s left join units u on u.source_id = s.id group by s.id order by s.created_at"""
        ).fetchall()


@router.post("/sources", status_code=202, dependencies=[LimitedDep, AdminDep])
def upload_source(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200),
    kind: Literal["pdf", "slides"] = Form(...),
    license: str | None = Form(default=None, max_length=100),
    pages: str | None = Form(default=None, max_length=20),
    source_id: str | None = Form(default=None),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    allowed = {".pdf"} if kind == "pdf" else {".pdf", ".pptx"}
    if suffix not in allowed:
        raise HTTPException(422, f"{kind} sources must be one of {sorted(allowed)}")
    source_id = _source_id(source_id, title)
    path = get_settings().uploads_dir / f"{source_id}{suffix}"
    _save_upload(file, path)
    modality = "pdf" if kind == "pdf" else "slide"
    register_pending(source_id, title, modality, f"file:{path.name}", license)
    job = pdf.ingest_pdf if kind == "pdf" else slides.ingest_slides
    background.add_task(_run, source_id, job, path, source_id, title, license, pages)
    return {"source_id": source_id, "status": "pending"}


@router.post("/sources/url", status_code=202, dependencies=[LimitedDep, AdminDep])
def add_youtube_source(body: UrlSourceIn, background: BackgroundTasks) -> dict:
    if not YOUTUBE_URL.match(body.url):
        raise HTTPException(422, "Only YouTube watch URLs are supported.")
    source_id = _source_id(body.source_id, body.title)
    register_pending(source_id, body.title, "video", body.url, body.license)
    background.add_task(_run, source_id, video.ingest_youtube_url, body.url, source_id, body.title, body.license)
    return {"source_id": source_id, "status": "pending"}


def _run(source_id: str, job, *args) -> None:
    """Background ingestion. Failures before ingest_source starts (download, conversion) are recorded here."""
    try:
        job(*args)
    except Exception as exc:
        log.exception("ingestion of %s failed", source_id)
        try:
            set_status(source_id, "failed", public_error(exc))
        except Exception:
            log.exception("could not mark %s as failed", source_id)


@router.get("/units/{unit_id}")
def get_unit(unit_id: str) -> dict:
    with connect() as conn:
        hits = fetch_hits(conn, [unit_id])
    if not hits:
        raise HTTPException(404, "Unit not found")
    return {**build_citation(hits[0]), "text": hits[0].text, "figure_desc": hits[0].figure_desc}


@router.get("/concepts")
def get_concepts() -> dict:
    graph = load_graph()
    topics = []
    for topic_id, topic_name in graph.topics.items():
        subtopics = []
        for sub_id, sub in graph.subtopics.items():
            if sub["topic_id"] != topic_id:
                continue
            concepts = [
                {"id": cid, "name": c["name"], "summary": c["summary"], "prereqs": graph.prereqs[cid]}
                for cid, c in graph.concepts.items() if c["subtopic_id"] == sub_id
            ]
            subtopics.append({"id": sub_id, "name": sub["name"], "concepts": concepts})
        topics.append({"id": topic_id, "name": topic_name, "subtopics": subtopics})
    edges = [{"concept_id": c, "prereq_id": p} for c, ps in graph.prereqs.items() for p in ps]
    return {"topics": topics, "edges": edges}
