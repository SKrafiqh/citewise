"""Shared API dependencies: admin gate, rate limit, daily cost cap, id validation."""
import hmac
import threading
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import Depends, Header, HTTPException, Path, Request

from app.config import get_settings

STUDENT_ID = Path(pattern=r"^[a-f0-9]{32}$")
MIN_ADMIN_TOKEN_CHARS = 16
_hits: dict[str, deque[float]] = defaultdict(deque)
_daily = {"day": date.min, "count": 0}
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """Caller address. With N trusted proxies, the Nth-from-last X-Forwarded-For entry is the one our
    own proxy observed; earlier entries are client-supplied and can be forged."""
    hops = get_settings().trusted_proxy_hops
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops > 0 and len(forwarded) >= hops:
        return forwarded[-hops]
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """Per-IP sliding one-minute window per route template, plus a global daily request cap.
    In-memory: one process, resets on restart."""
    settings = get_settings()
    route = request.scope.get("route")
    key = f"{client_ip(request)}:{getattr(route, 'path', request.url.path)}"
    now, today = time.monotonic(), date.today()
    with _lock:
        if _daily["day"] != today:
            _daily.update(day=today, count=0)
        if _daily["count"] >= settings.daily_request_cap:
            raise HTTPException(503, "Daily request limit reached; please try again tomorrow.")
        window = _hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            raise HTTPException(429, "Too many requests; please wait a moment.")
        window.append(now)
        _daily["count"] += 1
        if len(_hits) > 10_000:  # drop idle buckets so the table cannot grow without bound
            for stale in [k for k, w in _hits.items() if not w or now - w[-1] > 60]:
                del _hits[stale]


def require_admin(x_admin_token: str = Header(default="")) -> None:
    """Ingestion spends money and writes the knowledge base, so it needs the admin token."""
    expected = get_settings().admin_token
    if len(expected) < MIN_ADMIN_TOKEN_CHARS:
        raise HTTPException(503, f"Ingestion is disabled: set ADMIN_TOKEN to {MIN_ADMIN_TOKEN_CHARS}+ random characters.")
    if not hmac.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(401, "Invalid admin token.")


LimitedDep = Depends(rate_limit)
AdminDep = Depends(require_admin)
