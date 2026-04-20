"""
Lightweight in-memory TTL cache backed by a plain dictionary.

MVP replacement for Redis — same interface so the swap is trivial later.
Thread-safe enough for asyncio (single-threaded event loop).
"""
from __future__ import annotations

import time
from typing import Any, Optional


class TTLCache:
    """Key-value store where entries expire after `default_ttl` seconds."""

    def __init__(self, default_ttl: int = 60) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Return cached value, or None if missing / expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with an optional per-entry TTL override."""
        ttl = ttl if ttl is not None else self.default_ttl
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> list[str]:
        """Return all non-expired keys."""
        now = time.monotonic()
        return [k for k, (_, exp) in list(self._store.items()) if exp > now]

    def __len__(self) -> int:
        return len(self.keys())

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def evict_expired(self) -> int:
        """Remove all expired entries; return count removed."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp <= now]
        for k in expired:
            del self._store[k]
        return len(expired)


# ─── Singletons ───────────────────────────────────────────────────────────────

# Shared price cache — 60 s TTL matches the alert polling interval.
price_cache = TTLCache(default_ttl=60)

# News headline cache — 5-minute TTL to avoid hammering NewsAPI.
news_cache = TTLCache(default_ttl=300)