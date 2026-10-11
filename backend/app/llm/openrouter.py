"""Second model via OpenRouter (OpenAI-compatible), used for cross-model checks."""
from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings
from app.llm.cache import DiskCache
from app.llm.http import TIMEOUT_S, ipv4_transport
from app.llm.jsonutil import LLMOutputError, parse_json
from app.llm.retry import RateGate, with_retry

_gate = RateGate()
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

    def post() -> str:
        _gate.wait(settings.openrouter_max_rpm)
        body = {k: v for k, v in request.items() if k != "json_mode"}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        with httpx.Client(transport=ipv4_transport(), timeout=TIMEOUT_S) as client:
            response = client.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {settings.openrouter_api_key}"}, json=body)
        response.raise_for_status()
        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMOutputError(f"OpenRouter returned no completion: {str(body.get('error', body))[:120]}") from exc
        if not content:
            raise LLMOutputError("OpenRouter returned an empty response")
        return content

    return _cache().get_or_call(request, lambda: with_retry(post))


def verify_json(prompt: str, **kwargs: Any) -> Any:
    """verify_chat in JSON mode, parsed; one repair re-prompt on bad JSON."""
    try:
        return parse_json(verify_chat(prompt, json_mode=True, **kwargs))
    except LLMOutputError:
        repair = f"{prompt}\n\nYour previous reply was not valid JSON. Reply with valid JSON only."
        return parse_json(verify_chat(repair, json_mode=True, **kwargs))
