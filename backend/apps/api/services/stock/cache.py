"""A small TTL cache for stock search results.

Pixabay's terms say plainly: "requests must be cached for 24 hours". This is
that cache. It is process-local, which is the honest limit -- several workers
each keep their own copy, so the effective request rate scales with worker
count. A shared Redis cache would fix that and is the obvious upgrade once
Redis is actually wired up.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 512) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.max_entries:
                # Drop whatever expires soonest rather than growing without
                # bound.
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.time() + self.ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
