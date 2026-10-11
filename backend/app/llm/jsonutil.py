"""Parse JSON out of model output, tolerating markdown fences."""
import json
import re
from typing import Any

class LLMOutputError(ValueError):
    """The model answered, but not with usable output (empty, blocked, malformed JSON)."""


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json(text: str) -> Any:
    """json.loads that strips ```json fences. Raises ValueError on invalid JSON."""
    try:
        return json.loads(_FENCE.sub("", text.strip()))
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"model returned invalid JSON: {exc}") from exc
