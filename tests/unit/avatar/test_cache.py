"""
Unit tests for AICache.

Tests caching, TTL expiry, thread safety, error handling.
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.avatar.cache import AICache, CacheEntry


# =============================================================================
# CacheEntry tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_to_dict_roundtrip(self):
        entry = CacheEntry(
            key="abc123",
            result={"steps": 20, "sampler": "Euler"},
            provider_id="avatar:gemini",
            model="gemini-test",
            created_at=1000000.0,
            execution_time_ms=150,
        )
        d = entry.to_dict()
        restored = CacheEntry.from_dict(d)
        assert restored.key == entry.key
        assert restored.result == entry.result
        assert restored.provider_id == entry.provider_id
        assert restored.model == entry.model
        assert restored.created_at == entry.created_at
        assert restored.execution_time_ms == entry.execution_time_ms

    def test_from_dict_missing_execution_time_defaults_zero(self):
        data = {
            "key": "k",
            "result": {},
            "provider_id": "p",
            "model": "m",
            "created_at": 1.0,
        }
        entry = CacheEntry.from_dict(data)
        assert entry.execution_time_ms == 0

    def test_from_dict_missing_required_raises_keyerror(self):
        with pytest.raises(KeyError):
            CacheEntry.from_dict({"key": "k"})

    def test_age_seconds(self):
        entry = CacheEntry(
            key="k", result={}, provider_id="p", model="m",
            created_at=time.time() - 60,
            execution_time_ms=0,
        )
        assert 59 <= entry.age_seconds() <= 62

    def test_age_days(self):
        entry = CacheEntry(
            key="k", result={}, provider_id="p", model="m",
            created_at=time.time() - 86400,
            execution_time_ms=0,
        )
        assert 0.99 <= entry.age_days() <= 1.01


# =============================================================================
# AICache basic operations
# =============================================================================


class TestAICacheBasic:
    """Tests for basic cache operations."""

    def test_cache_dir_created(self, tmp_path):
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        cache = AICache(cache_dir=str(cache_dir))
        assert cache_dir.exists()

    def test_cache_dir_creation_failure_logged(self, tmp_path, caplog):
        """Cache gracefully handles directory creation failure."""
        # Use a path that can't be created (file instead of dir)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")
        bad_dir = str(blocker / "cache")
        import logging
        with caplog.at_level(logging.WARNING):
            AICache(cache_dir=bad_dir)
        assert "Failed to create cache directory" in caplog.text

    def test_get_cache_key_deterministic(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        k1 = cache.get_cache_key("hello world")
        k2 = cache.get_cache_key("hello world")
        assert k1 == k2
        assert len(k1) == 16

    def test_get_cache_key_different_for_different_content(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        k1 = cache.get_cache_key("hello")
        k2 = cache.get_cache_key("world")
        assert k1 != k2

    def test_set_and_get(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        cache.set("desc", {"steps": 20}, "avatar:gemini", "gemini-test", 100)
        entry = cache.get("desc")
        assert entry is not None
        assert entry.result == {"steps": 20}
        assert entry.provider_id == "avatar:gemini"
        assert entry.model == "gemini-test"
        assert entry.execution_time_ms == 100

    def test_get_miss(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        assert cache.get("nonexistent") is None

    def test_invalidate(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        cache.set("desc", {"steps": 20}, "p", "m")
        assert cache.invalidate("desc") is True
        assert cache.get("desc") is None

    def test_invalidate_nonexistent(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        assert cache.invalidate("nonexistent") is False

    def test_clear(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        cache.set("a", {"a": 1}, "p", "m")
        cache.set("b", {"b": 2}, "p", "m")
        cleared = cache.clear()
        assert cleared == 2
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_stats(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        stats = cache.stats()
        assert stats["entry_count"] == 0
        assert stats["total_size_bytes"] == 0

        cache.set("desc", {"steps": 20}, "p", "m")
        stats = cache.stats()
        assert stats["entry_count"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["cache_dir"] == str(tmp_path)


# =============================================================================
# TTL / Expiry
# =============================================================================


class TestAICacheTTL:
    """Tests for TTL and expiry behaviour."""

    def test_expired_entry_returns_none(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path), ttl_days=1)
        # Write a cache file with old timestamp
        key = cache.get_cache_key("old")
        entry = CacheEntry(
            key=key, result={"old": True}, provider_id="p", model="m",
            created_at=time.time() - 86400 * 2,  # 2 days ago
            execution_time_ms=0,
        )
        cache_file = cache.cache_dir / f"{key}.json"
        with open(cache_file, "w") as f:
            json.dump(entry.to_dict(), f)

        result = cache.get("old")
        assert result is None
        # File should be removed
        assert not cache_file.exists()

    def test_ttl_zero_disables_expiry(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path), ttl_days=0)
        # Old entry should still be returned
        key = cache.get_cache_key("old")
        entry = CacheEntry(
            key=key, result={"old": True}, provider_id="p", model="m",
            created_at=time.time() - 86400 * 365,  # 1 year ago
            execution_time_ms=0,
        )
        cache_file = cache.cache_dir / f"{key}.json"
        with open(cache_file, "w") as f:
            json.dump(entry.to_dict(), f)

        result = cache.get("old")
        assert result is not None
        assert result.result == {"old": True}

    def test_cleanup_expired(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path), ttl_days=1)

        # Fresh entry
        cache.set("fresh", {"fresh": True}, "p", "m")

        # Expired entry
        key_old = cache.get_cache_key("old")
        old_entry = CacheEntry(
            key=key_old, result={"old": True}, provider_id="p", model="m",
            created_at=time.time() - 86400 * 5,
            execution_time_ms=0,
        )
        with open(cache.cache_dir / f"{key_old}.json", "w") as f:
            json.dump(old_entry.to_dict(), f)

        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.stats()["entry_count"] == 1  # Only fresh remains

    def test_cleanup_with_ttl_zero_removes_nothing(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path), ttl_days=0)
        cache.set("a", {"a": 1}, "p", "m")
        removed = cache.cleanup_expired()
        assert removed == 0


# =============================================================================
# Error handling
# =============================================================================


class TestAICacheErrorHandling:
    """Tests for corrupted files and edge cases."""

    def test_corrupted_json_returns_none(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        key = cache.get_cache_key("bad")
        cache_file = cache.cache_dir / f"{key}.json"
        cache_file.write_text("{invalid json")

        result = cache.get("bad")
        assert result is None
        # Corrupted file should be removed
        assert not cache_file.exists()

    def test_incomplete_json_returns_none(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path))
        key = cache.get_cache_key("incomplete")
        cache_file = cache.cache_dir / f"{key}.json"
        cache_file.write_text('{"key": "k"}')  # Missing required fields

        result = cache.get("incomplete")
        assert result is None
        assert not cache_file.exists()

    def test_cleanup_removes_corrupted_entries(self, tmp_path):
        cache = AICache(cache_dir=str(tmp_path), ttl_days=1)
        bad_file = cache.cache_dir / "corrupt.json"
        bad_file.write_text("not json at all")

        removed = cache.cleanup_expired()
        assert removed == 1
        assert not bad_file.exists()

    def test_set_write_failure_does_not_raise(self, tmp_path):
        """set() logs warning but doesn't raise on write failure."""
        cache = AICache(cache_dir=str(tmp_path))
        # Make cache dir read-only
        cache.cache_dir.chmod(0o444)
        try:
            # Should not raise
            entry = cache.set("fail", {"a": 1}, "p", "m")
            assert entry is not None  # Entry is still returned
        finally:
            cache.cache_dir.chmod(0o755)


# =============================================================================
# Thread safety
# =============================================================================


class TestAICacheThreadSafety:
    """Tests for concurrent access patterns."""

    def test_concurrent_set_and_get(self, tmp_path):
        """Multiple threads can set and get without errors."""
        import concurrent.futures

        cache = AICache(cache_dir=str(tmp_path))
        errors = []

        def worker(i):
            try:
                desc = f"description-{i}"
                cache.set(desc, {"i": i}, "p", "m")
                result = cache.get(desc)
                if result is None or result.result["i"] != i:
                    errors.append(f"Worker {i}: unexpected result")
            except Exception as e:
                errors.append(f"Worker {i}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(worker, i) for i in range(20)]
            concurrent.futures.wait(futures)

        assert errors == [], f"Thread errors: {errors}"

    def test_concurrent_clear_and_get(self, tmp_path):
        """clear() during get() doesn't crash."""
        import concurrent.futures

        cache = AICache(cache_dir=str(tmp_path))
        cache.set("target", {"x": 1}, "p", "m")
        errors = []

        def getter():
            try:
                for _ in range(10):
                    cache.get("target")  # May return None after clear
            except Exception as e:
                errors.append(f"getter: {e}")

        def clearer():
            try:
                cache.clear()
            except Exception as e:
                errors.append(f"clearer: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(getter) for _ in range(3)]
            futures.append(pool.submit(clearer))
            concurrent.futures.wait(futures)

        assert errors == []
