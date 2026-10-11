"""Retry with exponential backoff for transient provider errors."""
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

T = TypeVar("T")
log = logging.getLogger(__name__)
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    if isinstance(exc, httpx.TransportError):
        return True
    # google-genai errors expose the HTTP status as `code`
    return getattr(exc, "code", None) in RETRYABLE_STATUS


_RETRY_IN = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)
MAX_SUGGESTED_DELAY_S = 90


def suggested_delay(exc: Exception) -> float:
    """Seconds the provider asked us to wait ("Please retry in 13.1s"), 0 if it did not say."""
    match = _RETRY_IN.search(str(exc))
    return min(float(match[1]) + 1, MAX_SUGGESTED_DELAY_S) if match else 0.0


class RateGate:
    """Spaces calls at least 60/rpm seconds apart (stay under a provider's requests-per-minute quota)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self, rpm: int) -> None:
        if rpm <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + 60.0 / rpm
        if start > now:
            time.sleep(start - now)


def with_retry(call: Callable[[], T], tries: int = 5, base_delay: float = 2.0) -> T:
    for attempt in range(1, tries + 1):
        try:
            return call()
        except Exception as exc:
            if attempt == tries or not is_retryable(exc):
                raise
            delay = max(base_delay * 2 ** (attempt - 1), suggested_delay(exc))
            log.warning("LLM call failed (%s); retry %d/%d in %.0fs", type(exc).__name__, attempt, tries - 1, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")
