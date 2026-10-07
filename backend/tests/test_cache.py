from app.llm.cache import DiskCache


def test_key_is_order_independent():
    assert DiskCache.key({"a": 1, "b": 2}) == DiskCache.key({"b": 2, "a": 1})


def test_get_or_call_hits_cache(tmp_path):
    cache = DiskCache(tmp_path)
    calls = []

    def call():
        calls.append(1)
        return {"answer": "ok"}

    request = {"model": "m", "prompt": "hi"}
    assert cache.get_or_call(request, call) == {"answer": "ok"}
    assert cache.get_or_call(request, call) == {"answer": "ok"}
    assert len(calls) == 1


def test_different_request_misses(tmp_path):
    cache = DiskCache(tmp_path)
    cache.get_or_call({"prompt": "a"}, lambda: "A")
    assert cache.get_or_call({"prompt": "b"}, lambda: "B") == "B"
