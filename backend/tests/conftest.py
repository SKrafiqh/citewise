import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent))  # for the eval package


def call_or_skip(fn, *args, **kwargs):
    """Run a not-yet-implemented function; skip the test instead of failing."""
    try:
        return fn(*args, **kwargs)
    except NotImplementedError as exc:
        pytest.skip(f"TODO: {exc}")


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Point caches and data dirs at a temp folder so tests never touch real keys or files."""
    from app.config import get_settings
    from app.llm import gemini, openrouter

    def reset() -> None:
        get_settings.cache_clear()
        gemini._cache.cache_clear()
        getattr(gemini._client, "cache_clear", lambda: None)()  # may be monkeypatched
        openrouter._cache.cache_clear()

    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("ADMIN_TOKEN", "")
    monkeypatch.setenv("GEMINI_MAX_RPM", "0")  # .env throttles for free tiers; tests must not sleep
    monkeypatch.setenv("OPENROUTER_MAX_RPM", "0")
    monkeypatch.setenv("DATABASE_URL", "")  # unit tests must never reach a real database
    reset()
    yield
    reset()
