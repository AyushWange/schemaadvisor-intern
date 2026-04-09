# project_02/cache_manager.py — Hybrid Redis / In-Memory TTL Cache
"""
CacheManager:
  - If REDIS_URL is set in the environment, uses Redis as the backend.
  - Otherwise falls back to an in-memory TTLCache (cachetools).
  - TTL defaults to 1 hour (3600 seconds).

Usage in db_access.py:
    from project_02.cache_manager import cache_manager
    key = "selected_tables:" + ":".join(sorted(concepts))
    result = cache_manager.get(key)
    if result is None:
        result = ... expensive Neo4j query ...
        cache_manager.set(key, result)
"""
import os
import json
import logging
import threading

logger = logging.getLogger(__name__)

# Default cache TTL: 1 hour
_DEFAULT_TTL = int(os.environ.get("CACHE_TTL_SECONDS", 3600))
# Max items stored in the in-memory cache
_DEFAULT_MAXSIZE = int(os.environ.get("CACHE_MAX_ENTRIES", 256))


class _InMemoryCache:
    """Thread-safe TTL cache backed by cachetools.TTLCache."""

    def __init__(self, maxsize: int, ttl: int):
        try:
            from cachetools import TTLCache
            self._cache = TTLCache(maxsize=maxsize, ttl=ttl)
            self._lock = threading.Lock()
            self._stats = {"hits": 0, "misses": 0}
            logger.info("CacheManager: using in-memory TTLCache (ttl=%ds, maxsize=%d)", ttl, maxsize)
        except ImportError:
            self._cache = None
            logger.warning("CacheManager: cachetools not installed — cache disabled")

    def get(self, key: str):
        if self._cache is None:
            return None
        with self._lock:
            value = self._cache.get(key)
            if value is not None:
                self._stats["hits"] += 1
            else:
                self._stats["misses"] += 1
            return value

    def set(self, key: str, value, ttl: int = None):
        """ttl is ignored for in-memory cache (set at construction time)."""
        if self._cache is None:
            return
        with self._lock:
            self._cache[key] = value

    def delete(self, key: str):
        if self._cache is None:
            return
        with self._lock:
            self._cache.pop(key, None)

    def flush(self):
        if self._cache is None:
            return
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict:
        if self._cache is None:
            return {"backend": "disabled", "hits": 0, "misses": 0}
        with self._lock:
            return {
                "backend": "in_memory",
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "current_size": len(self._cache),
                "maxsize": self._cache.maxsize,
                "ttl": self._cache.ttl,
            }


class _RedisCache:
    """Redis-backed cache with JSON serialization."""

    def __init__(self, url: str, ttl: int):
        try:
            import redis as _redis
            self._client = _redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            self._client.ping()   # fail fast if Redis is unreachable
            self._ttl = ttl
            self._stats = {"hits": 0, "misses": 0}
            logger.info("CacheManager: connected to Redis at %s (ttl=%ds)", url, ttl)
        except Exception as e:
            logger.warning("CacheManager: Redis connection failed (%s) — falling back to in-memory", e)
            raise

    def get(self, key: str):
        try:
            raw = self._client.get(key)
            if raw is not None:
                self._stats["hits"] += 1
                return json.loads(raw)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            logger.warning("CacheManager: Redis GET error (%s)", e)
            return None

    def set(self, key: str, value, ttl: int = None):
        try:
            self._client.setex(key, ttl or self._ttl, json.dumps(value))
        except Exception as e:
            logger.warning("CacheManager: Redis SET error (%s)", e)

    def delete(self, key: str):
        try:
            self._client.delete(key)
        except Exception as e:
            logger.warning("CacheManager: Redis DELETE error (%s)", e)

    def flush(self):
        try:
            self._client.flushdb()
        except Exception as e:
            logger.warning("CacheManager: Redis FLUSH error (%s)", e)

    def stats(self) -> dict:
        try:
            info = self._client.info()
            return {
                "backend": "redis",
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "redis_used_memory": info.get("used_memory_human"),
                "redis_connected_clients": info.get("connected_clients"),
                "redis_uptime_days": info.get("uptime_in_days"),
            }
        except Exception:
            return {"backend": "redis", "hits": self._stats["hits"], "misses": self._stats["misses"]}


def _build_cache(ttl: int, maxsize: int):
    """Try Redis first; fall back to in-memory."""
    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        try:
            return _RedisCache(url=redis_url, ttl=ttl)
        except Exception:
            logger.warning("CacheManager: falling back to in-memory cache")
    return _InMemoryCache(maxsize=maxsize, ttl=ttl)


# ── Singleton ────────────────────────────────────────────────────────────────
cache_manager = _build_cache(ttl=_DEFAULT_TTL, maxsize=_DEFAULT_MAXSIZE)


def make_cache_key(*parts) -> str:
    """Deterministic cache key from arbitrary string parts."""
    return ":".join(str(p) for p in parts)
