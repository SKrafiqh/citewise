"""Second model via OpenRouter (OpenAI-compatible), used for cross-model checks."""
from functools import lru_cache

import httpx

from app.config import get_settings
from app.llm.cache import DiskCache

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@lru_cache
def _cache() -> DiskCache:
    return DiskCache(get_settings().llm_cache_dir / "openrouter")


def verify_chat(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    model: str | None = None,
) -> str:
    settings = get_settings()
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    request = {
        "model": model or settings.openrouter_model,
        "messages": messages,
        "temperature": temperature,
        "json_mode": json_mode,
    }

    def call() -> str:
        body = {k: v for k, v in request.items() if k != "json_mode"}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        response = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    return _cache().get_or_call(request, call)
