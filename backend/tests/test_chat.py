from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.qa import chat, gate
from app.qa.answer import Draft, Sentence
from app.qa.retrieve import Hit, Retrieval

H1 = Hit("t-p1", "t", "Textbook", "file:x", "pdf", {"page": 1}, "Bayes rule text", None)
H2 = Hit("t-p2", "t", "Textbook", "file:x", "pdf", {"page": 2}, "Independence text", None)


@pytest.fixture
def patched(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []

    @contextmanager
    def fake_connect():
        yield conn

    monkeypatch.setattr(chat, "connect", fake_connect)
    monkeypatch.setattr(chat, "concepts_for_units", lambda c, ids: ["c1"])
    monkeypatch.setattr(chat.retrieve, "retrieve", lambda q, mode: Retrieval([H1, H2], 0.9))
    monkeypatch.setattr(gate, "covered", lambda sim, t=None: sim >= 0.6)
    monkeypatch.setattr(chat, "pick_check_question", lambda sid, cs: {"question_id": "q1"})
    return monkeypatch


def draft(*sentences, outside=()):
    return Draft(sentences=[Sentence(t, c) for t, c in sentences], outside=list(outside))


def test_gate_declines_without_calling_the_model(patched):
    patched.setattr(chat.retrieve, "retrieve", lambda q, mode: Retrieval([H1], 0.2))
    patched.setattr(chat.answer, "draft_answer", lambda *a, **k: pytest.fail("model must not be called"))
    result = chat.ask("who won the world cup")
    assert result["declined"] and result["citations"] == [] and "closest content" in result["message"]


def test_answer_has_ordered_deduped_citations(patched):
    patched.setattr(chat.answer, "draft_answer", lambda *a, **k: draft(("A.", ["t-p2"]), ("B.", ["t-p1", "t-p2"])))
    patched.setattr(chat.claimcheck, "check_claims", lambda s, h: [True, True])
    result = chat.ask("q")
    assert [c["unit_id"] for c in result["citations"]] == ["t-p2", "t-p1"]
    assert result["citations"][0]["label"] == "p. 2" and result["citations"][0]["asset_url"] == "/assets/t/pages/2.jpg"
    assert result["check_question"] is None  # no student


def test_unsupported_sentences_are_dropped_or_boxed(patched):
    patched.setattr(chat.answer, "draft_answer", lambda *a, **k: draft(("Good.", ["t-p1"]), ("Invented.", ["t-p2"])))
    patched.setattr(chat.claimcheck, "check_claims", lambda s, h: [True, False])
    assert chat.ask("q")["outside"] == []
    boxed = chat.ask("q", allow_outside=True)
    assert boxed["outside"] == ["Invented."] and [s["text"] for s in boxed["sentences"]] == ["Good."]


def test_everything_unsupported_declines(patched):
    patched.setattr(chat.answer, "draft_answer", lambda *a, **k: draft(("Invented.", ["t-p1"])))
    patched.setattr(chat.claimcheck, "check_claims", lambda s, h: [False])
    result = chat.ask("q")
    assert result["declined"] and "could not verify" in result["message"]


def test_claim_check_can_be_disabled(patched):
    patched.setattr(chat.answer, "draft_answer", lambda *a, **k: draft(("A.", ["t-p1"])))
    patched.setattr(chat.claimcheck, "check_claims", lambda s, h: pytest.fail("disabled"))
    assert not chat.ask("q", use_claim_check=False)["declined"]


def test_student_turn_attaches_check_question_and_persists(patched):
    patched.setattr(chat.answer, "draft_answer", lambda *a, **k: draft(("A.", ["t-p1"])))
    patched.setattr(chat.claimcheck, "check_claims", lambda s, h: [True])
    stored = []
    patched.setattr(chat, "_persist", lambda sid, q, r: stored.append((sid, q)))
    patched.setattr(chat, "_level_for", lambda conn, sid, cs: 0.2)
    result = chat.ask("q", student_id="s1")
    assert result["check_question"] == {"question_id": "q1"} and stored == [("s1", "q")]
