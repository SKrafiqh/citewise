"""Gemini: main multimodal model and embeddings, with disk caching."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.llm.cache import DiskCache


@lru_cache
def _client():
    from google import genai  # imported lazily so tests run without the SDK

    return genai.Client(api_key=get_settings().gemini_api_key)


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
        response = _client().models.generate_content(
            model=settings.gemini_model, contents=contents, config=config
        )
        return response.text

    return _cache().get_or_call(request, call)


def generate_json(prompt: str, **kwargs: Any) -> Any:
    """Like generate, but asks for JSON and parses it."""
    return json.loads(generate(prompt, json_mode=True, **kwargs))


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed texts at EMBED_DIM dimensions. Use task_type RETRIEVAL_QUERY for queries."""
    from google.genai import types

    settings = get_settings()
    results: list[list[float]] = []
    for text in texts:  # one cache entry per text, so re-ingesting reuses old vectors
        request = {
            "model": settings.gemini_embed_model,
            "dim": settings.embed_dim,
            "task": task_type,
            "text": text,
        }

        def call(text: str = text) -> list[float]:
            response = _client().models.embed_content(
                model=settings.gemini_embed_model,
                contents=[text],
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=settings.embed_dim
                ),
            )
            return list(response.embeddings[0].values)

        results.append(_cache().get_or_call(request, call))
    return results
