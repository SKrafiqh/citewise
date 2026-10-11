from types import SimpleNamespace

import httpx
import pytest

from app.llm import gemini, openrouter
from app.llm.jsonutil import LLMOutputError, parse_json
from app.llm.retry import RateGate, is_retryable, suggested_delay, with_retry


def test_parse_json_strips_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_rejects_garbage():
    with pytest.raises(LLMOutputError):
        parse_json("not json")


def test_retry_succeeds_after_transient_error(monkeypatch):
    monkeypatch.setattr("app.llm.retry.time.sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise SimpleNamespace_error(503)
        return "ok"

    assert with_retry(flaky) == "ok"
    assert len(calls) == 3


def test_retry_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr("app.llm.retry.time.sleep", lambda s: None)
    calls = []

    def bad():
        calls.append(1)
        raise SimpleNamespace_error(400)

    with pytest.raises(Exception):
        with_retry(bad)
    assert len(calls) == 1


def test_is_retryable_for_http_status_and_transport():
    req = httpx.Request("POST", "http://x")
    assert is_retryable(httpx.HTTPStatusError("x", request=req, response=httpx.Response(429, request=req)))
    assert not is_retryable(httpx.HTTPStatusError("x", request=req, response=httpx.Response(401, request=req)))
    assert is_retryable(httpx.ConnectError("boom"))


def SimpleNamespace_error(code):
    err = Exception(f"http {code}")
    err.code = code
    return err


class FakeModels:
    def __init__(self):
        self.embed_calls = []

    def embed_content(self, model, contents, config):
        self.embed_calls.append(list(contents))
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[float(len(c))] * 4) for c in contents])

    def generate_content(self, model, contents, config):
        return SimpleNamespace(text=self.reply)


def fake_client(monkeypatch):
    models = FakeModels()
    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=models))
    return models


def test_embed_batches_dedupes_and_caches(monkeypatch):
    models = fake_client(monkeypatch)
    first = gemini.embed(["aa", "bbb", "aa"])
    assert first == [[2.0] * 4, [3.0] * 4, [2.0] * 4]
    assert models.embed_calls == [["aa", "bbb"]]  # one batched request, duplicate collapsed
    gemini.embed(["aa", "bbb"])
    assert len(models.embed_calls) == 1  # second call fully cached


def test_generate_json_repairs_once(monkeypatch):
    models = fake_client(monkeypatch)
    replies = iter(["oops", '{"ok": true}'])

    def gen(model, contents, config):
        return SimpleNamespace(text=next(replies))

    models.generate_content = gen
    assert gemini.generate_json("give json") == {"ok": True}


def test_generate_rejects_empty_response(monkeypatch):
    models = fake_client(monkeypatch)
    models.reply = ""
    with pytest.raises(LLMOutputError):
        gemini.generate("hi")


def test_openrouter_verify_json_parses(monkeypatch):
    monkeypatch.setattr(openrouter, "verify_chat", lambda prompt, **kw: '{"answer": "B"}')
    assert openrouter.verify_json("q") == {"answer": "B"}


def test_suggested_delay_reads_provider_hint():
    assert suggested_delay(Exception("Quota exceeded. Please retry in 13.14s.")) == pytest.approx(14.14)
    assert suggested_delay(Exception("Please retry in 9999s")) == 90
    assert suggested_delay(Exception("boom")) == 0


def test_retry_waits_for_provider_hint(monkeypatch):
    sleeps = []
    monkeypatch.setattr("app.llm.retry.time.sleep", sleeps.append)
    calls = []

    def limited():
        calls.append(1)
        if len(calls) == 1:
            err = Exception("Please retry in 20s")
            err.code = 429
            raise err
        return "ok"

    assert with_retry(limited) == "ok" and sleeps == [21.0]


def test_rate_gate_spaces_calls(monkeypatch):
    now, sleeps = [100.0], []
    monkeypatch.setattr("app.llm.retry.time.monotonic", lambda: now[0])
    monkeypatch.setattr("app.llm.retry.time.sleep", sleeps.append)
    gate = RateGate()
    gate.wait(15)           # first call goes through immediately
    gate.wait(15)           # second must wait 60/15 = 4 s
    assert sleeps == [pytest.approx(4.0)]
    gate.wait(0)            # disabled
    assert len(sleeps) == 1
