"""In-memory TTL cache for BDNS API responses."""

import time
from typing import Any


class TTLCache:
    """Simple in-memory cache with per-entry TTL.

    Thread-safe for single-process use (FastAPI with uvicorn).
    Entries expire individually based on their TTL.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        """Get a value if it exists and hasn't expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Set a value with TTL in seconds."""
        if len(self._store) >= self._max_size:
            self._evict_expired()
        if len(self._store) >= self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][1])
            del self._store[oldest_key]
        self._store[key] = (value, time.monotonic() + ttl)

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    def clear(self) -> None:
        """Clear all entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        """Number of entries (including potentially expired ones)."""
        return len(self._store)


# Singleton cache instance
cache = TTLCache(max_size=1000)
