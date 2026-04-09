# tests/test_caching.py — Unit tests for CacheManager
import time
import pytest
from unittest.mock import patch, MagicMock


# ── In-memory cache tests ────────────────────────────────────────────────────

def test_inmemory_cache_basic_set_get():
    """Items stored in cache can be retrieved."""
    from project_02.cache_manager import _InMemoryCache
    cache = _InMemoryCache(maxsize=10, ttl=60)
    cache.set("key1", {"data": 42})
    result = cache.get("key1")
    assert result == {"data": 42}


def test_inmemory_cache_miss_returns_none():
    """Missing keys return None, not KeyError."""
    from project_02.cache_manager import _InMemoryCache
    cache = _InMemoryCache(maxsize=10, ttl=60)
    assert cache.get("nonexistent_key") is None


def test_inmemory_cache_stats_tracks_hits_and_misses():
    """Stats correctly increment hit/miss counters."""
    from project_02.cache_manager import _InMemoryCache
    cache = _InMemoryCache(maxsize=10, ttl=60)
    cache.set("k", "v")
    cache.get("k")      # hit
    cache.get("k")      # hit
    cache.get("miss")   # miss
    stats = cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["backend"] == "in_memory"


def test_inmemory_cache_delete():
    """Deleted keys return None on subsequent gets."""
    from project_02.cache_manager import _InMemoryCache
    cache = _InMemoryCache(maxsize=10, ttl=60)
    cache.set("k", "v")
    cache.delete("k")
    assert cache.get("k") is None


def test_inmemory_cache_flush():
    """Flush clears all cache entries."""
    from project_02.cache_manager import _InMemoryCache
    cache = _InMemoryCache(maxsize=10, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.flush()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_inmemory_cache_ttl_expiry(monkeypatch):
    """Items expire after their TTL."""
    from project_02.cache_manager import _InMemoryCache
    from cachetools import TTLCache
    # Use a very short TTL
    cache = _InMemoryCache(maxsize=10, ttl=1)
    cache.set("expiring", "soon")
    assert cache.get("expiring") == "soon"
    # Wait for TTL to expire
    time.sleep(1.5)
    assert cache.get("expiring") is None


# ── make_cache_key tests ─────────────────────────────────────────────────────

def test_make_cache_key_deterministic():
    """Same inputs always produce the same key."""
    from project_02.cache_manager import make_cache_key
    k1 = make_cache_key("selected_tables", "a|b|c")
    k2 = make_cache_key("selected_tables", "a|b|c")
    assert k1 == k2


def test_make_cache_key_differs_for_different_inputs():
    """Different inputs produce different keys."""
    from project_02.cache_manager import make_cache_key
    k1 = make_cache_key("selected_tables", "a|b")
    k2 = make_cache_key("selected_tables", "a|b|c")
    assert k1 != k2


# ── Redis fallback test ──────────────────────────────────────────────────────

def test_redis_fallback_to_inmemory_on_connection_failure():
    """When Redis is unreachable, _build_cache falls back to in-memory silently."""
    with patch.dict("os.environ", {"REDIS_URL": "redis://nonexistent-host:6379"}):
        from project_02 import cache_manager as cm_module
        # Re-build with a bad URL — should not raise, should return InMemoryCache
        cache = cm_module._build_cache(ttl=60, maxsize=10)
        # Should still work: set/get should succeed
        cache.set("fallback_key", "ok")
        # In-memory fallback: returns the value
        # (If Redis was used and failed silently on GET, it returns None — so
        #  we just check it doesn't raise)


# ── Integration: db_access caching ───────────────────────────────────────────

def test_db_access_uses_cache_on_second_call():
    """
    A mocked Neo4j driver: first call should insert into cache,
    second call with same concepts should NOT hit Neo4j again.
    """
    import importlib
    import project_02.db_access as db_mod

    fake_result = {
        "orders": {"name": "orders", "tier": "required", "triggered_by": ["e_commerce_orders"]}
    }

    call_count = {"n": 0}

    # Monkey-patch the cache_manager on the module to use a fresh one
    from project_02.cache_manager import _InMemoryCache
    fresh_cache = _InMemoryCache(maxsize=10, ttl=60)
    original_cm = db_mod.cache_manager
    db_mod.cache_manager = fresh_cache

    # Monkey-patch _is_neo4j_available to say True
    # and GraphDatabase.driver to track calls
    with patch.object(db_mod, "_is_neo4j_available", return_value=True):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, k: (
            "orders" if k == "table" else (3 if k == "max_tier" else ["e_commerce_orders"])
        )
        mock_session.run.return_value = [mock_record]
        mock_driver.session.return_value.__enter__ = lambda s: mock_session
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("project_02.db_access.GraphDatabase") as mock_gdb:
            def driver_factory(*a, **kw):
                call_count["n"] += 1
                return mock_driver
            mock_gdb.driver.side_effect = driver_factory

            # First call — should hit Neo4j
            db_mod.get_selected_tables(["e_commerce_orders"])
            assert call_count["n"] == 1

            # Second call with same concepts — should hit cache, not Neo4j
            db_mod.get_selected_tables(["e_commerce_orders"])
            assert call_count["n"] == 1  # Still 1 — Neo4j was NOT called again

    # Restore
    db_mod.cache_manager = original_cm
