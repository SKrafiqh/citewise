from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps, learning, library, tutor
from app.assess import service
from app.config import get_settings
from app.main import create_app

SID = "a" * 32
TOKEN = "t" * 24


@pytest.fixture
def client(monkeypatch):
    deps._hits.clear()
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def fake_db(monkeypatch):
    conn = MagicMock()

    @contextmanager
    def fake_connect():
        yield conn

    for module in (library, learning):
        monkeypatch.setattr(module, "connect", fake_connect)
    return conn


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_validates_input(client):
    assert client.post("/chat", json={"question": ""}).status_code == 422
    assert client.post("/chat", json={"question": "x" * 1001}).status_code == 422
    assert client.post("/chat", json={"question": "hi", "student_id": "not-hex"}).status_code == 422
    assert client.post("/chat", json={"question": "hi", "lang": "fr"}).status_code == 422


def test_chat_passes_options_through(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(tutor, "ask", lambda q, sid, outside, lang: seen.update(q=q, sid=sid, outside=outside, lang=lang) or {"declined": False})
    assert client.post("/chat", json={"question": "what is Bayes", "student_id": SID, "allow_outside": True, "lang": "hi"}).status_code == 200
    assert seen == {"q": "what is Bayes", "sid": SID, "outside": True, "lang": "hi"}


def test_rate_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(tutor, "ask", lambda *a: {"declined": True})
    codes = [client.post("/chat", json={"question": "q"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_upload_requires_admin_token(client, monkeypatch):
    files = {"file": ("b.pdf", b"%PDF-1.4", "application/pdf")}
    data = {"title": "Book", "kind": "pdf"}
    assert client.post("/sources", files=files, data=data).status_code == 503  # token not configured
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    get_settings.cache_clear()
    assert client.post("/sources", files=files, data=data, headers={"X-Admin-Token": "w" * 24}).status_code == 401


def test_upload_rejects_wrong_type_and_bad_id(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    get_settings.cache_clear()
    headers = {"X-Admin-Token": TOKEN}
    bad_ext = client.post("/sources", files={"file": ("a.exe", b"x")}, data={"title": "T", "kind": "pdf"}, headers=headers)
    assert bad_ext.status_code == 422
    bad_id = client.post("/sources", files={"file": ("a.pdf", b"x")}, data={"title": "T", "kind": "pdf", "source_id": "../etc"}, headers=headers)
    assert bad_id.status_code == 422


def test_upload_accepts_pdf_and_schedules_ingest(client, monkeypatch, fake_db):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    get_settings.cache_clear()
    registered, ran = [], []
    monkeypatch.setattr(library, "register_pending", lambda *a: registered.append(a))
    monkeypatch.setattr(library, "_run", lambda sid, job, *a: ran.append(a))
    resp = client.post("/sources", files={"file": ("a.pdf", b"%PDF-1.4")}, data={"title": "My Book", "kind": "pdf", "pages": "1-5"}, headers={"X-Admin-Token": TOKEN})
    assert resp.status_code == 202 and resp.json() == {"source_id": "my-book", "status": "pending"}
    assert registered[0][:3] == ("my-book", "My Book", "pdf") and ran[0][-1] == "1-5"
    assert (get_settings().uploads_dir / "my-book.pdf").exists()


def test_upload_size_limit(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    big = b"0" * (1024 * 1024 + 10)
    resp = client.post("/sources", files={"file": ("a.pdf", big)}, data={"title": "Book", "kind": "pdf"}, headers={"X-Admin-Token": TOKEN})
    assert resp.status_code == 413


def test_url_source_only_accepts_youtube(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    get_settings.cache_clear()
    headers = {"X-Admin-Token": TOKEN}
    assert client.post("/sources/url", json={"url": "http://169.254.169.254/x", "title": "T"}, headers=headers).status_code == 422
    assert client.post("/sources/url", json={"url": "https://evil.com/watch?v=abcdefghijk", "title": "T"}, headers=headers).status_code == 422
    monkeypatch.setattr(library, "register_pending", lambda *a: None)
    monkeypatch.setattr(library, "_run", lambda *a: None)
    ok = client.post("/sources/url", json={"url": "https://www.youtube.com/watch?v=j9WZyLZCBzs", "title": "Lecture 1"}, headers=headers)
    assert ok.status_code == 202


def test_assessment_validation(client):
    base = {"student_id": SID}
    assert client.post("/assessments", json={**base, "n": 0}).status_code == 422
    assert client.post("/assessments", json={**base, "mix": {"essay": 1}}).status_code == 422
    assert client.post("/assessments", json={**base, "mix": {"mcq": 0}}).status_code == 422


def test_service_errors_map_to_http_codes(client, monkeypatch):
    def raise_(exc):
        def f(*a, **k):
            raise exc
        return f

    monkeypatch.setattr(learning.service, "submit_answer", raise_(service.AlreadyAnswered()))
    assert client.post("/assessments/abc/answer", json={"question_id": "q", "response": "A"}).status_code == 409
    monkeypatch.setattr(learning.service, "submit_answer", raise_(service.NotFound("assessment")))
    assert client.post("/assessments/abc/answer", json={"question_id": "q", "response": "A"}).status_code == 404
    monkeypatch.setattr(learning.service, "submit_answer", raise_(NotImplementedError("Shaik: implement the BKT update")))
    resp = client.post("/assessments/abc/answer", json={"question_id": "q", "response": "A"})
    assert resp.status_code == 501 and "BKT" in resp.json()["detail"]
    monkeypatch.setattr(learning.service, "submit_answer", raise_(RuntimeError("secret internals")))
    resp = client.post("/assessments/abc/answer", json={"question_id": "q", "response": "A"})
    assert resp.status_code == 500 and TOKEN not in resp.text


def test_intake_validates_familiarity(client):
    assert client.post(f"/students/{SID}/intake", json={"familiarity": {"t_a": 5}}).status_code == 422
    assert client.post("/students/not-a-valid-id/intake", json={}).status_code == 422


def test_rate_limit_ignores_forged_forwarded_for(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(tutor, "ask", lambda *a: {"declined": True})
    # the proxy appends the real caller last; earlier entries are forged and must not matter
    codes = [client.post("/chat", json={"question": "q"}, headers={"X-Forwarded-For": f"9.9.9.{i}, 1.2.3.4"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_rate_limit_buckets_by_route_not_by_path_parameter(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(learning.service, "submit_answer", lambda *a: {"correct": True})
    codes = [client.post(f"/assessments/id{i}/answer", json={"question_id": "q", "response": "A"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_daily_cap_stops_spending(client, monkeypatch):
    monkeypatch.setenv("DAILY_REQUEST_CAP", "1")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "100")
    get_settings.cache_clear()
    deps._daily.update(day=deps.date.min, count=0)
    monkeypatch.setattr(tutor, "ask", lambda *a: {"declined": True})
    assert [client.post("/chat", json={"question": "q"}).status_code for _ in range(2)] == [200, 503]


def test_short_admin_token_disables_ingestion(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "short")
    get_settings.cache_clear()
    resp = client.post("/sources", files={"file": ("a.pdf", b"x")}, data={"title": "Book", "kind": "pdf"}, headers={"X-Admin-Token": "short"})
    assert resp.status_code == 503


def test_admin_guessing_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    files = {"file": ("a.pdf", b"x")}
    codes = [client.post("/sources", files=files, data={"title": "Book", "kind": "pdf"}, headers={"X-Admin-Token": "w" * 24}).status_code for _ in range(3)]
    assert codes == [401, 401, 429]


def test_background_failure_marks_source_failed(monkeypatch):
    marked = []
    monkeypatch.setattr(library, "set_status", lambda sid, status, error=None: marked.append((sid, status, error)))

    def download_fails(*a):
        raise RuntimeError("yt-dlp exited with 1")

    library._run("lec1", download_fails, "url", "lec1")
    assert marked == [("lec1", "failed", "yt-dlp exited with 1")]


def test_unusable_model_output_is_a_502_not_a_422(client, monkeypatch):
    from app.llm.jsonutil import LLMOutputError

    def broken(*a):
        raise LLMOutputError("model returned invalid JSON: boom")

    monkeypatch.setattr(tutor, "ask", broken)
    resp = client.post("/chat", json={"question": "q"})
    assert resp.status_code == 502 and "boom" not in resp.text
