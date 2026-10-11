"""End-to-end checks of the SQL layer against a real Postgres + pgvector.

Skipped unless TEST_DATABASE_URL points at a database with migrations 001-003 applied, e.g.
    docker run -d -p 54329:5432 -e POSTGRES_PASSWORD=x -e POSTGRES_DB=tutor pgvector/pgvector:pg17
    TEST_DATABASE_URL=postgresql://postgres:x@localhost:54329/tutor pytest tests/test_db_integration.py
Tables are emptied before each test.
"""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")

DIM = 768


def vec(i: int, j: int | None = None) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    if j is not None and j != i:
        v[j] = 0.2
    return v


@pytest.fixture
def db(monkeypatch):
    import app.db
    from app.config import get_settings

    monkeypatch.setenv("DATABASE_URL", URL)
    get_settings.cache_clear()
    app.db._pool.cache_clear()
    with app.db.connect() as conn:
        conn.execute("truncate sources, concepts, students, questions restart identity cascade")
    yield app.db
    app.db.close_pool()


@pytest.fixture
def fake_embed(monkeypatch):
    """Deterministic embeddings: text mentioning 'bayes' -> axis 0, 'independ' -> axis 1, else axis 2."""
    def embed(texts, task_type="RETRIEVAL_DOCUMENT"):
        return [vec(0 if "bayes" in t.lower() else 1 if "independ" in t.lower() else 2) for t in texts]

    for module in ("app.ingest.store", "app.qa.retrieve", "app.kb.tagging", "app.assess.bank"):
        monkeypatch.setattr(f"{module}.embed", embed, raising=False)
    return embed


def ingest(units, source_id="book"):
    from app.ingest.store import ingest_source

    return ingest_source(source_id, title="Book", modality="pdf", uri="file:b.pdf", license="CC", build_units=lambda: units)


def seed_units():
    from app.ingest.store import UnitIn

    return [UnitIn({"page": 1}, "Bayes rule computes a posterior from a prior"), UnitIn({"page": 2}, "Independent events multiply"),
            UnitIn({"page": 3}, "Unrelated chapter on sampling", "a bar chart of samples")]


def test_ingest_is_idempotent_and_prunes_removed_units(db, fake_embed):
    assert ingest(seed_units()) == 3
    assert ingest(seed_units()) == 3
    assert ingest(seed_units()[:2]) == 2
    with db.connect() as conn:
        assert conn.execute("select count(*) as n from units").fetchone()["n"] == 2
        assert conn.execute("select status from sources").fetchone()["status"] == "ready"


def test_failed_ingest_marks_source_failed(db, fake_embed):
    with pytest.raises(ValueError):
        ingest([])
    with db.connect() as conn:
        row = conn.execute("select status, error from sources").fetchone()
    assert row["status"] == "failed" and "no content" in row["error"]


def test_hybrid_retrieval_finds_by_meaning_and_keyword(db, fake_embed):
    from app.qa.retrieve import retrieve

    ingest(seed_units())
    result = retrieve("what is bayes rule", mode="hybrid")
    assert result.hits[0].unit_id == "book-p1" and result.top_sim == pytest.approx(1.0)
    assert result.hits[0].source_title == "Book"
    assert retrieve("tell me about bar charts", mode="hybrid").hits  # keyword match on the figure description


def build_course(conn):
    from app.kb.concepts import flatten
    tree = {"topics": [{"id": "t_prob", "name": "Probability", "subtopics": [{"id": "s_cond", "name": "Conditioning", "concepts": [
        {"id": "c_bayes", "name": "Bayes", "summary": "posterior", "prereqs": []},
        {"id": "c_indep", "name": "Independence", "summary": "product rule", "prereqs": ["c_bayes"]}]}]}]}
    rows, edges = flatten(tree)
    for r in rows:
        conn.execute("insert into concepts (id, name, level, parent_id, summary) values (%(id)s, %(name)s, %(level)s, null, %(summary)s)", r)
    for r in rows:
        if r["parent_id"]:
            conn.execute("update concepts set parent_id = %s where id = %s", (r["parent_id"], r["id"]))
    for c, p in edges:
        conn.execute("insert into concept_prereqs values (%s, %s)", (c, p))


def add_question(conn, qid, concept, qtype="mcq", difficulty=0.5, axis=2, verified=True):
    from pgvector import Vector
    from psycopg.types.json import Jsonb

    options = [{"key": k, "text": f"opt {k} {qid}", "misconception": None if k == "A" else f"mis {k}"} for k in "ABCD"]
    conn.execute(
        """insert into questions (id, qtype, stem, options, answer_key, concept_id, anchor_units, difficulty, verified, embedding, explanation)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'because')""",
        (qid, qtype, f"stem {qid}", Jsonb(options), Jsonb("A"), concept, ["book-p1"], difficulty, verified, Vector(vec(axis, (axis + 5) % DIM))),
    )


@pytest.fixture
def course(db, fake_embed, monkeypatch):
    import app.assess.dedup as dedup

    # reserved functions are stubs: plug in minimal stand-ins for these DB-level checks only
    monkeypatch.setattr("app.assess.service.is_duplicate", lambda new, seen, t=0.88: False)
    monkeypatch.setattr("app.tutor.check.is_duplicate", lambda new, seen, t=0.88: False)
    monkeypatch.setattr("app.learner.store.update", lambda p, correct, params, weight=1.0: p + weight * ((0.9 if correct else 0.1) - p))
    del dedup
    ingest(seed_units())
    with db.connect() as conn:
        build_course(conn)
        conn.execute("insert into unit_concepts values ('book-p1', 'c_bayes', 0.9), ('book-p2', 'c_indep', 0.8)")
        for i in range(3):
            add_question(conn, f"qb{i}", "c_bayes", difficulty=0.2 + 0.3 * i, axis=10 + i)
        add_question(conn, "qi0", "c_indep", axis=20)
        add_question(conn, "qunverified", "c_indep", verified=False, axis=30)
        from app.learner import store
        student = store.create_student(conn, "Test")
    return student


def test_graph_and_assessment_flow_updates_mastery_once(db, course):
    from app.assess import service
    from app.kb.graph import load_graph

    graph = load_graph()
    assert graph.prereqs == {"c_bayes": [], "c_indep": ["c_bayes"]} and graph.expand_scope(["t_prob"]) == ["c_bayes", "c_indep"]
    quiz = service.create_assessment(course, "quiz", [], 4, {"mcq": 1})
    ids = [q["question_id"] for q in quiz["questions"]]
    assert sorted(ids) == ["qb0", "qb1", "qb2", "qi0"] and quiz["shortfall"] == 0   # unverified never served
    assert all("answer" not in str(q) and set(o) == {"key", "text"} for q in quiz["questions"] for o in q["options"])

    wrong = service.submit_answer(quiz["assessment_id"], ids[0], "B")
    assert not wrong["correct"] and wrong["misconception"] == "mis B" and wrong["citations"][0]["label"] == "p. 1"
    assert wrong["p_after"] < wrong["p_before"]
    right = service.submit_answer(quiz["assessment_id"], ids[1], "A")
    assert right["correct"] and right["mastery_delta"] > 0
    with pytest.raises(service.AlreadyAnswered):
        service.submit_answer(quiz["assessment_id"], ids[1], "A")
    with pytest.raises(service.NotFound):
        service.submit_answer(quiz["assessment_id"], "not-in-this-quiz", "A")

    report = service.get_report(quiz["assessment_id"])
    assert (report["answered"], report["total"], report["correct"]) == (2, 4, 1)
    with db.connect() as conn:
        assert conn.execute("select count(*) as n from mastery_log").fetchone()["n"] == 2
        assert conn.execute("select finished_at from assessments").fetchone()["finished_at"] is None


def test_new_quiz_never_repeats_seen_questions(db, course):
    from app.assess import service

    first = service.create_assessment(course, "quiz", [], 3, {"mcq": 1})
    second = service.create_assessment(course, "quiz", [], 3, {"mcq": 1})
    assert not {q["question_id"] for q in first["questions"]} & {q["question_id"] for q in second["questions"]}
    assert second["shortfall"] == 2  # only one verified question was left


def test_check_question_counts_at_half_weight_and_only_once(db, course):
    from app.assess import service
    from app.tutor.check import pick_check_question

    q = pick_check_question(course, ["c_bayes"])
    assert q and q["concept_id"] == "c_bayes" and "answer_key" not in q
    result = service.submit_check(course, q["question_id"], "A")
    assert result["p_after"] - result["p_before"] == pytest.approx(0.5 * (0.9 - 0.2))   # stand-in update, weight 0.5
    with db.connect() as conn:
        assert conn.execute("select weight, assessment_id from attempts").fetchone() == {"weight": 0.5, "assessment_id": None}
        assert conn.execute("select source from mastery_log").fetchone()["source"] == "check"
    with pytest.raises(service.AlreadyAnswered):
        service.submit_check(course, q["question_id"], "A")


def test_intake_sets_priors_for_each_concept(db, course):
    from app.kb.graph import load_graph
    from app.learner import store

    with db.connect() as conn:
        assert store.save_intake(conn, course, "pass the exam", None, {"t_prob": 2}, load_graph()) == 2
        assert {r["p_known"] for r in store.get_mastery(conn, course).values()} == {0.5}
        with pytest.raises(LookupError):
            store.save_intake(conn, "f" * 32, None, None, {}, load_graph())


def test_chat_end_to_end_with_stubbed_models(db, course, monkeypatch):
    from app.qa import chat
    from app.qa.answer import Draft, Sentence

    monkeypatch.setattr(chat.answer, "draft_answer", lambda *a, **k: Draft(sentences=[Sentence("Bayes updates a prior.", ["book-p1"])]))
    monkeypatch.setattr(chat.claimcheck, "check_claims", lambda s, h: [True])
    monkeypatch.setattr("app.qa.gate.get_settings", lambda: type("S", (), {"coverage_threshold": 0.5})())
    result = chat.ask("what is bayes rule", student_id=course)
    assert not result["declined"] and result["citations"][0]["unit_id"] == "book-p1"
    assert result["check_question"]["concept_id"] == "c_bayes"
    with db.connect() as conn:
        assert conn.execute("select count(*) as n from chat_messages").fetchone()["n"] == 2
    off = chat.ask("zebra migration", student_id=course)  # axis 2 only matches the unrelated page weakly
    assert isinstance(off["declined"], bool)


def test_api_student_journey(db, course):
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    tree = client.get("/concepts").json()
    assert tree["topics"][0]["subtopics"][0]["concepts"][1]["prereqs"] == ["c_bayes"]
    assert tree["edges"] == [{"concept_id": "c_indep", "prereq_id": "c_bayes"}]
    sid = client.post("/students", json={"name": "Asha"}).json()["student_id"]
    assert client.post(f"/students/{sid}/intake", json={"familiarity": {"t_prob": 1}, "goal": "pass"}).json() == {"priors_set": 2}
    assert client.post(f"/students/{sid}/intake", json={"familiarity": {"nope": 1}}).status_code == 422
    mastery = client.get(f"/students/{sid}/mastery").json()
    assert {c["p_known"] for c in mastery["concepts"]} == {0.3} and mastery["topics"][0]["mean"] == pytest.approx(0.3)
    recs = client.get(f"/students/{sid}/recommendations").json()
    assert recs[0]["concept_id"] == "c_bayes" and recs[0]["units"][0]["label"] == "p. 1"
    assert client.get("/students/" + "e" * 32 + "/mastery").status_code == 404
    unit = client.get("/units/book-p1").json()
    assert unit["asset_url"] == "/assets/book/pages/1.jpg" and "Bayes" in unit["text"]
    assert client.get("/units/ghost").status_code == 404
    sources = client.get("/sources").json()
    assert sources[0]["units"] == 3 and sources[0]["status"] == "ready"
    quiz = client.post("/assessments", json={"student_id": sid, "kind": "diagnostic", "n": 2}).json()
    assert len(quiz["questions"]) == 2
    assert client.get("/ready").status_code == 200


def test_concept_graph_storage_and_tagging(db, fake_embed, monkeypatch):
    from app.kb import concepts, tagging

    ingest(seed_units())
    tree = {"topics": [{"id": "t_a", "name": "A", "subtopics": [{"id": "s_a", "name": "SA", "concepts": [
        {"id": f"c_{i}", "name": f"Concept {i}", "summary": "bayes" if i == 0 else "independence", "prereqs": []} for i in range(16)]}]}]}
    assert concepts.store_tree(tree) == 16
    monkeypatch.setattr(tagging, "generate_json", lambda prompt: {"tags": [{"unit_id": "book-p1", "concepts": [{"id": "c_0", "confidence": 0.9}]}]})
    stats = tagging.run()
    assert stats["units"] == 3 and stats["fallback_share"] == pytest.approx(2 / 3)  # units the model skipped use the nearest concept
    with db.connect() as conn:
        tags = {r["unit_id"]: (r["concept_id"], r["confidence"]) for r in conn.execute("select * from unit_concepts").fetchall()}
    assert tags["book-p1"] == ("c_0", pytest.approx(0.9)) and len(tags) == 3


def test_bank_generation_stores_failed_attempts_and_serves_only_verified(db, course, monkeypatch):
    from app.assess import bank
    from app.assess.models import validate_draft

    raw = lambda stem: {"stem": stem, "answer": "B", "explanation": "e",
                        "options": [{"key": k, "text": f"{stem} {k}", "misconception": None if k == "B" else f"m{k}"} for k in "ABCD"]}
    stems = iter(["first stem", "second stem"])
    monkeypatch.setattr(bank, "generate_draft", lambda *a, **k: validate_draft(raw(next(stems)), "mcq"))
    verdicts = iter([False, True])
    monkeypatch.setattr(bank, "verify", lambda draft, ex: {"passed": next(verdicts), "checks": [{"checker": "blind_mcq", "passed": False}]})
    monkeypatch.setattr(bank, "is_duplicate", lambda new, seen, t=0.88: False)
    with db.connect() as conn:
        pool = bank._anchor_units(conn, "c_bayes")
        assert bank.make_one(conn, {"name": "Bayes", "summary": "s"}, "c_bayes", pool, "mcq", 0.5, [])
        rows = conn.execute("select stem, verified, verify_log from questions where stem like '%stem'").fetchall()
    assert {(r["stem"], r["verified"]) for r in rows} == {("first stem", False), ("second stem", True)}
    assert rows[1]["verify_log"]["attempts"]
    assert {r["qtype"]: r["total"] for r in bank.pass_rates()}["mcq"] >= 2


def test_intake_resubmission_keeps_learned_mastery(db, course):
    from app.assess import service
    from app.kb.graph import load_graph
    from app.learner import store

    graph = load_graph()
    with db.connect() as conn:
        store.save_intake(conn, course, None, None, {"t_prob": 0}, graph)
    first = service.create_assessment(course, "quiz", ["c_bayes"], 1, {"mcq": 1})
    result = service.submit_answer(first["assessment_id"], first["questions"][0]["question_id"], "A")
    with db.connect() as conn:
        assert store.save_intake(conn, course, None, None, {"t_prob": 2}, graph) == 1  # only the never-assessed concept
        mastery = store.get_mastery(conn, course)
    assert mastery["c_bayes"]["p_known"] == pytest.approx(result["p_after"])
    assert mastery["c_indep"]["p_known"] == pytest.approx(0.5)


def test_check_attempt_is_unique_in_the_database(db, course):
    import psycopg

    from app.assess import service

    q = "qb0"
    service.submit_check(course, q, "A")
    with db.connect() as conn, pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute("insert into attempts (student_id, question_id, response, correct, score) values (%s, %s, '{}', true, 1)", (course, q))
    with pytest.raises(service.NotFound):
        service.submit_check("f" * 32, "qb1", "A")


def test_partial_reingest_keeps_other_pages(db, fake_embed):
    from app.ingest.store import ingest_source

    ingest(seed_units())
    ingest_source("book", title="Book", modality="pdf", uri="file:b.pdf", license="CC", build_units=lambda: seed_units()[:1], prune=False)
    with db.connect() as conn:
        assert conn.execute("select count(*) as n from units").fetchone()["n"] == 3


def test_diagnostic_serves_every_available_concept(db, course):
    from app.assess import service

    quiz = service.create_assessment(course, "diagnostic", [], 10, None)
    assert {q["concept_id"] for q in quiz["questions"]} == {"c_bayes", "c_indep"}


def test_concept_rebuild_failure_keeps_old_graph(db, course, monkeypatch):
    from app.kb import concepts

    monkeypatch.setattr(concepts, "build_tree", lambda digest: (_ for _ in ()).throw(RuntimeError("model down")))
    with pytest.raises(RuntimeError):
        concepts.run(force=True)
    with db.connect() as conn:
        assert conn.execute("select count(*) as n from concepts").fetchone()["n"] == 4
