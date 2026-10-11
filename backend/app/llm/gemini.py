"""Gemini: main multimodal model and embeddings, with disk caching."""
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.llm.cache import DiskCache
from app.llm.http import TIMEOUT_S, ipv4_transport
from app.llm.jsonutil import LLMOutputError, parse_json
from app.llm.retry import RateGate, with_retry

_gate = RateGate()
EMBED_BATCH = 100  # Gemini embed_content accepts up to 100 texts per request


@lru_cache
def _client():
    from google import genai  # imported lazily so tests run without the SDK
    from google.genai import types

    options = types.HttpOptions(timeout=TIMEOUT_S * 1000, client_args={"transport": ipv4_transport()})
    return genai.Client(api_key=get_settings().gemini_api_key, http_options=options)


@lru_cache
def _cache() -> DiskCache:
    return DiskCache(get_settings().llm_cache_dir / "gemini")


def _image_part(path: Path) -> Any:
    from google.genai import types

    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def generate(
    prompt: str,
    *,
    system: str | None = None,
    images: list[Path] | None = None,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """Text (optionally with images) in, text out. Cached by request content."""
    from google.genai import types

    settings = get_settings()
    images = images or []
    request = {
        "model": settings.gemini_model,
        "system": system,
        "prompt": prompt,
        # hash image bytes so the cache key changes if an image changes
        "images": [DiskCache.key({"bytes": p.read_bytes().hex()}) for p in images],
        "temperature": temperature,
        "json_mode": json_mode,
    }

    def call() -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else None,
        )
        contents = [*[_image_part(p) for p in images], prompt]
        def request():
            _gate.wait(settings.gemini_max_rpm)
            return _client().models.generate_content(model=settings.gemini_model, contents=contents, config=config)

        response = with_retry(request)
        if not response.text:  # blocked or empty: never cache it
            raise LLMOutputError("Gemini returned an empty response")
        return response.text

    return _cache().get_or_call(request, call)


def generate_json(prompt: str, **kwargs: Any) -> Any:
    """Like generate, but asks for JSON and parses it; one repair re-prompt on bad JSON."""
    text = generate(prompt, json_mode=True, **kwargs)
    try:
        return parse_json(text)
    except LLMOutputError:
        repair = f"{prompt}\n\nYour previous reply was not valid JSON. Reply with valid JSON only."
        return parse_json(generate(repair, json_mode=True, **{**kwargs, "temperature": 0.0}))


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed texts at EMBED_DIM dimensions. Use task_type RETRIEVAL_QUERY for queries."""
    from google.genai import types

    settings = get_settings()
    cache = _cache()

    def request_for(text: str) -> dict[str, Any]:
        return {
            "model": settings.gemini_embed_model,
            "dim": settings.embed_dim,
            "task": task_type,
            "text": text,
        }

    vectors: dict[str, list[float]] = {}
    missing: list[str] = []
    for text in dict.fromkeys(texts):  # unique, order-preserving
        cached = cache.get(DiskCache.key(request_for(text)))
        if cached is not None:
            vectors[text] = cached
        else:
            missing.append(text)

    for start in range(0, len(missing), EMBED_BATCH):
        batch = missing[start : start + EMBED_BATCH]
        response = with_retry(
            lambda b=batch: _client().models.embed_content(
                model=settings.gemini_embed_model,
                contents=b,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=settings.embed_dim
                ),
            )
        )
        if len(response.embeddings) != len(batch):
            raise LLMOutputError("Gemini returned a different number of embeddings than inputs")
        for text, emb in zip(batch, response.embeddings):
            vectors[text] = list(emb.values)
            cache.put(DiskCache.key(request_for(text)), request_for(text), vectors[text])

    return [vectors[t] for t in texts]
