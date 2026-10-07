"""Disk cache for LLM responses, keyed by a hash of the full request.

Identical requests return the stored response, so reruns cost nothing and
evaluation results are reproducible.
"""
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


class DiskCache:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(request: dict[str, Any]) -> str:
        canonical = json.dumps(request, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["response"]

    def put(self, key: str, request: dict[str, Any], response: Any) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"request": request, "response": response}, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)  # atomic, so a crash never leaves a half-written entry

    def get_or_call(self, request: dict[str, Any], call: Callable[[], Any]) -> Any:
        key = self.key(request)
        cached = self.get(key)
        if cached is not None:
            return cached
        response = call()
        self.put(key, request, response)
        return response
