"""Concept graph: topic -> subtopic -> concept with prerequisite edges (KB-3)."""
import argparse
import logging
import re
from contextlib import nullcontext

from app.db import connect
from app.llm import generate_json
from app.prompts import render

log = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
MIN_CONCEPTS, MAX_CONCEPTS = 15, 40
DIGEST_CHARS = 220
MAX_ATTEMPTS = 3


def _walk(tree: dict):
    for topic in tree.get("topics", []):
        for sub in topic.get("subtopics", []):
            yield topic, sub, sub.get("concepts", [])


def _has_cycle(prereqs: dict[str, list[str]]) -> bool:
    """Kahn's algorithm: True if the prerequisite graph is not a DAG."""
    indegree = {c: 0 for c in prereqs}
    children: dict[str, list[str]] = {c: [] for c in prereqs}
    for concept, deps in prereqs.items():
        for dep in deps:
            children[dep].append(concept)
            indegree[concept] += 1
    ready = [c for c, n in indegree.items() if n == 0]
    seen = 0
    while ready:
        node = ready.pop()
        seen += 1
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    return seen != len(prereqs)


def validate_tree(tree: dict) -> list[str]:
    """Return a list of problems; empty means the tree is valid."""
    problems: list[str] = []
    ids: list[str] = []
    concepts: dict[str, list[str]] = {}
    topics = tree.get("topics", [])
    if not topics:
        return ["no topics"]
    for topic in topics:
        ids.append(topic.get("id", ""))
        if not topic.get("subtopics"):
            problems.append(f"topic {topic.get('id')} has no subtopics")
    for _topic, sub, subconcepts in _walk(tree):
        ids.append(sub.get("id", ""))
        if not subconcepts:
            problems.append(f"subtopic {sub.get('id')} has no concepts")
        for concept in subconcepts:
            ids.append(concept.get("id", ""))
            concepts[concept.get("id", "")] = list(concept.get("prereqs", []))
    for item in ids:
        if not ID_PATTERN.match(item):
            problems.append(f"bad id {item!r}")
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        problems.append(f"duplicate ids: {sorted(duplicates)}")
    if not MIN_CONCEPTS <= len(concepts) <= MAX_CONCEPTS:
        problems.append(f"{len(concepts)} concepts; need {MIN_CONCEPTS}-{MAX_CONCEPTS}")
    for concept, deps in concepts.items():
        for dep in deps:
            if dep not in concepts:
                problems.append(f"{concept} has unknown prerequisite {dep}")
            elif dep == concept:
                problems.append(f"{concept} lists itself as a prerequisite")
    if not problems and _has_cycle(concepts):
        problems.append("prerequisites contain a cycle")
    return problems


def flatten(tree: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    """Tree -> (concept rows with level and parent, (concept, prereq) edges)."""
    rows: list[dict] = []
    edges: list[tuple[str, str]] = []
    for topic in tree["topics"]:
        rows.append({"id": topic["id"], "name": topic["name"], "level": "topic", "parent_id": None, "summary": None})
    for topic, sub, subconcepts in _walk(tree):
        rows.append({"id": sub["id"], "name": sub["name"], "level": "subtopic", "parent_id": topic["id"], "summary": None})
        for concept in subconcepts:
            rows.append({"id": concept["id"], "name": concept["name"], "level": "concept",
                         "parent_id": sub["id"], "summary": concept.get("summary")})
            edges.extend((concept["id"], dep) for dep in concept.get("prereqs", []))
    return rows, edges


def build_tree(digest: str) -> dict:
    """Ask the model for the hierarchy; feed validation problems back for up to MAX_ATTEMPTS."""
    problems_text = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        tree = generate_json(render("concepts", problems=problems_text, digest=digest), temperature=0.2 * (attempt - 1))
        problems = validate_tree(tree)
        if not problems:
            return tree
        log.warning("concept graph attempt %d invalid: %s", attempt, problems)
        problems_text = "Your previous answer had these problems; fix them:\n- " + "\n- ".join(problems) + "\n"
    raise ValueError(f"could not build a valid concept graph: {problems}")


def make_digest(units: list[dict]) -> str:
    return "\n".join(f"[{u['id']}] {' '.join(u['text'].split())[:DIGEST_CHARS]}" for u in units)


def store_tree(tree: dict, conn=None) -> int:
    """Insert the graph. Pass `conn` to share a transaction (used by run to replace atomically)."""
    rows, edges = flatten(tree)
    with (connect() if conn is None else nullcontext(conn)) as active:
        with active.cursor() as cur:
            cur.executemany(
                "insert into concepts (id, name, level, parent_id, summary) values (%(id)s, %(name)s, %(level)s, null, %(summary)s)",
                rows,
            )
            cur.executemany("update concepts set parent_id = %(parent_id)s where id = %(id)s", [r for r in rows if r["parent_id"]])
            cur.executemany("insert into concept_prereqs (concept_id, prereq_id) values (%s, %s)", edges)
    return sum(1 for r in rows if r["level"] == "concept")


def run(force: bool = False) -> int:
    """Build and store the graph. --force replaces an existing one (this also deletes mastery rows and
    fails if questions already reference the concepts), but only after a valid new graph exists."""
    with connect() as conn:
        exists = conn.execute("select 1 from concepts limit 1").fetchone()
        units = conn.execute("select id, text from units order by source_id, id").fetchall()
    if exists and not force:
        raise SystemExit("concept graph already exists; pass --force to rebuild")
    if not units:
        raise SystemExit("no units yet; ingest sources first")
    tree = build_tree(make_digest(units))
    with connect() as conn:  # one transaction: a failure leaves the old graph untouched
        conn.execute("delete from concepts")
        return store_tree(tree, conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the concept graph from ingested units")
    parser.add_argument("--force", action="store_true", help="replace an existing graph (deletes student mastery)")
    logging.basicConfig(level=logging.INFO)
    print(f"stored {run(parser.parse_args().force)} concepts")


if __name__ == "__main__":
    main()
