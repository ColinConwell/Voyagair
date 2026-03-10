"""Caching layer using diskcache with in-memory LRU for hot data."""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import diskcache

logger = logging.getLogger(__name__)


class SearchCache:
    """Two-tier cache: in-memory LRU for hot data, diskcache for persistence."""

    def __init__(self, cache_dir: str = ".voyagair_cache", ttl: int = 3600, max_size_mb: int = 500):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._disk = diskcache.Cache(
            str(self._dir),
            size_limit=max_size_mb * 1024 * 1024,
            eviction_policy="least-recently-used",
        )
        self._ttl = ttl
        self._memory: dict[str, Any] = {}
        self._memory_max = 1000

    @staticmethod
    def make_key(prefix: str, **kwargs: Any) -> str:
        """Create a deterministic cache key from parameters."""
        filtered = {k: v for k, v in sorted(kwargs.items()) if v is not None}
        raw = json.dumps(filtered, default=str, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"

    def get(self, key: str) -> Any | None:
        if key in self._memory:
            return self._memory[key]
        val = self._disk.get(key)
        if val is not None:
            self._memory_put(key, val)
        return val

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._disk.set(key, value, expire=(ttl or self._ttl))
        self._memory_put(key, value)

    def delete(self, key: str) -> None:
        self._disk.delete(key)
        self._memory.pop(key, None)

    def clear(self) -> None:
        self._disk.clear()
        self._memory.clear()

    def _memory_put(self, key: str, value: Any) -> None:
        if len(self._memory) >= self._memory_max:
            oldest = next(iter(self._memory))
            del self._memory[oldest]
        self._memory[key] = value

    def close(self) -> None:
        self._disk.close()

    def __del__(self) -> None:
        try:
            self._disk.close()
        except Exception:
            pass


_cache: SearchCache | None = None


def get_cache(cache_dir: str = ".voyagair_cache", ttl: int = 3600) -> SearchCache:
    global _cache
    if _cache is None:
        _cache = SearchCache(cache_dir=cache_dir, ttl=ttl)
    return _cache
