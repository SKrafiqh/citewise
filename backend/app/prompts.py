"""Versioned prompt templates live in prompts/*.md; placeholders are {name}."""
from functools import lru_cache

from app.config import get_settings


@lru_cache
def _template(name: str) -> str:
    return (get_settings().prompts_dir / f"{name}.md").read_text(encoding="utf-8")


def render(name: str, **values: str) -> str:
    """Fill {placeholders} by plain replacement (templates contain literal JSON braces).

    Values are substituted in the given order, so pass untrusted text (user input) last.
    """
    text = _template(name)
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text
