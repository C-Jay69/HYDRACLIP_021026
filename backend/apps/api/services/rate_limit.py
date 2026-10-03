"""A small fixed-window rate limiter for authentication endpoints.

The spec calls for rate limiting on auth endpoints. This is an in-process
implementation: it is correct for a single worker and is the right shape to
swap for a Redis-backed counter once the API runs more than one process.
``REDIS_URL`` is already configured for exactly that.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

__all__ = ["RateLimiter", "login_rate_limiter"]


class RateLimiter:
    """Allow N attempts per key inside a rolling window."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        kept = [ts for ts in self._hits[key] if ts > cutoff]
        self._hits[key] = kept
        return kept

    def check(self, key: str) -> bool:
        """Return True if the key is currently under its limit."""
        with self._lock:
            return len(self._prune(key, time.monotonic())) < self.max_attempts

    def register_failure(self, key: str) -> None:
        """Record a failed attempt against the key."""
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            self._hits[key].append(now)

    def reset(self, key: str) -> None:
        """Clear a key's history, e.g. after a successful login."""
        with self._lock:
            self._hits.pop(key, None)

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest attempt in the window expires."""
        with self._lock:
            hits = self._hits.get(key) or []
            if not hits:
                return 0
            elapsed = time.monotonic() - min(hits)
            return max(1, int(self.window_seconds - elapsed))

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


def _build_login_limiter() -> RateLimiter:
    from apps.api.core.config import settings

    return RateLimiter(
        max_attempts=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


login_rate_limiter = _build_login_limiter()
