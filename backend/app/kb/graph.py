"""Read-only view of the concept graph shared by the learner, assessment and API layers."""
from dataclasses import dataclass

from app.db import connect


@dataclass(frozen=True)
class Graph:
    concepts: dict[str, dict]      # concept id -> {name, summary, subtopic_id, topic_id}
    topics: dict[str, str]         # topic id -> name
    subtopics: dict[str, dict]     # subtopic id -> {name, topic_id}
    prereqs: dict[str, list[str]]  # concept id -> prerequisite concept ids

    def expand_scope(self, ids: list[str]) -> list[str]:
        """Topic / subtopic / concept ids -> concept ids (all concepts when ids is empty)."""
        if not ids:
            return sorted(self.concepts)
        wanted = set(ids)
        return sorted(
            cid for cid, c in self.concepts.items()
            if cid in wanted or c["subtopic_id"] in wanted or c["topic_id"] in wanted
        )


def build_graph(rows: list[dict], prereq_rows: list[dict]) -> Graph:
    by_id = {r["id"]: r for r in rows}
    topics = {r["id"]: r["name"] for r in rows if r["level"] == "topic"}
    subtopics = {r["id"]: {"name": r["name"], "topic_id": r["parent_id"]} for r in rows if r["level"] == "subtopic"}
    concepts = {}
    for r in rows:
        if r["level"] != "concept":
            continue
        sub = by_id[r["parent_id"]]
        concepts[r["id"]] = {"name": r["name"], "summary": r["summary"], "subtopic_id": sub["id"], "topic_id": sub["parent_id"]}
    prereqs: dict[str, list[str]] = {cid: [] for cid in concepts}
    for p in prereq_rows:
        prereqs[p["concept_id"]].append(p["prereq_id"])
    return Graph(concepts, topics, subtopics, prereqs)


def load_graph() -> Graph:
    with connect() as conn:
        rows = conn.execute("select id, name, level, parent_id, summary from concepts").fetchall()
        prereqs = conn.execute("select concept_id, prereq_id from concept_prereqs").fetchall()
    return build_graph(rows, prereqs)
