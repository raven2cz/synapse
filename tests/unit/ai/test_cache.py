"""
Unit tests for AI cache.
"""

import json
import os
import tempfile
import time
import pytest

from src.ai.cache import AICache, CacheEntry


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        entry = CacheEntry(
            key="abc123",
            result={"param": "value"},
            provider_id="ollama",
            model="qwen2.5:14b",
            created_at=time.time(),
            execution_time_ms=1500,
        )

        data = entry.to_dict()
        assert data["key"] == "abc123"
        assert data["result"] == {"param": "value"}
        assert data["provider_id"] == "ollama"
        assert data["execution_time_ms"] == 1500

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "key": "abc123",
            "result": {"param": "value"},
            "provider_id": "gemini",
            "model": "gemini-3-pro-preview",
            "created_at": time.time(),
            "execution_time_ms": 2000,
        }

        entry = CacheEntry.from_dict(data)
        assert entry.key == "abc123"
        assert entry.provider_id == "gemini"

    def test_age_seconds(self):
        """Test age calculation in seconds."""
        entry = CacheEntry(
            key="test",
            result={},
            provider_id="test",
            model="test",
            created_at=time.time() - 3600,  # 1 hour ago
            execution_time_ms=0,
        )

        age = entry.age_seconds()
        assert 3599 <= age <= 3601  # Allow for small timing differences

    def test_age_days(self):
        """Test age calculation in days."""
        entry = CacheEntry(
            key="test",
            result={},
            provider_id="test",
            model="test",
            created_at=time.time() - 86400,  # 1 day ago
            execution_time_ms=0,
        )

        age = entry.age_days()
        assert 0.99 <= age <= 1.01


class TestAICache:
    """Tests for AICache class."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temp directory."""
        return AICache(cache_dir=temp_cache_dir, ttl_days=30)

    def test_cache_key_deterministic(self, cache):
        """Test cache key is deterministic."""
        content = "test content for caching"
        key1 = cache.get_cache_key(content)
        key2 = cache.get_cache_key(content)

        assert key1 == key2
        assert len(key1) == 16  # 16 hex chars

    def test_cache_key_different_content(self, cache):
        """Test different content produces different keys."""
        key1 = cache.get_cache_key("content 1")
        key2 = cache.get_cache_key("content 2")

        assert key1 != key2

    def test_set_and_get(self, cache):
        """Test storing and retrieving cache entry."""
        content = "test description"
        result = {"cfg_scale": 7, "steps": 25}

        entry = cache.set(
            content=content,
            result=result,
            provider_id="ollama",
            model="qwen2.5:14b",
            execution_time_ms=1500,
        )

        assert entry.key == cache.get_cache_key(content)
        assert entry.result == result

        # Retrieve
        retrieved = cache.get(content)
        assert retrieved is not None
        assert retrieved.result == result
        assert retrieved.provider_id == "ollama"

    def test_get_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("non-existent content")
        assert result is None

    def test_invalidate(self, cache):
        """Test invalidating a cache entry."""
        content = "test content"
        cache.set(content, {"key": "value"}, "test", "test")

        # Entry exists
        assert cache.get(content) is not None

        # Invalidate
        result = cache.invalidate(content)
        assert result is True

        # Entry no longer exists
        assert cache.get(content) is None

    def test_invalidate_nonexistent(self, cache):
        """Test invalidating non-existent entry."""
        result = cache.invalidate("non-existent")
        assert result is False

    def test_clear(self, cache):
        """Test clearing all entries."""
        # Add some entries
        cache.set("content1", {"k": 1}, "p1", "m1")
        cache.set("content2", {"k": 2}, "p2", "m2")
        cache.set("content3", {"k": 3}, "p3", "m3")

        # Clear
        count = cache.clear()
        assert count == 3

        # All entries gone
        assert cache.get("content1") is None
        assert cache.get("content2") is None
        assert cache.get("content3") is None

    def test_stats(self, cache):
        """Test cache statistics."""
        cache.set("content1", {"k": 1}, "p1", "m1")
        cache.set("content2", {"k": 2}, "p2", "m2")

        stats = cache.stats()

        assert stats["entry_count"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["ttl_days"] == 30

    def test_ttl_expiry(self, temp_cache_dir):
        """Test TTL-based expiry."""
        cache = AICache(cache_dir=temp_cache_dir, ttl_days=1)

        # Add entry with old timestamp
        content = "old content"
        key = cache.get_cache_key(content)
        cache_file = cache.cache_dir / f"{key}.json"

        old_entry = {
            "key": key,
            "result": {"k": "v"},
            "provider_id": "test",
            "model": "test",
            "created_at": time.time() - (2 * 86400),  # 2 days ago
            "execution_time_ms": 0,
        }

        with open(cache_file, "w") as f:
            json.dump(old_entry, f)

        # Entry should be expired
        result = cache.get(content)
        assert result is None

        # File should be removed
        assert not cache_file.exists()

    def test_cleanup_expired(self, temp_cache_dir):
        """Test cleanup of expired entries."""
        cache = AICache(cache_dir=temp_cache_dir, ttl_days=1)

        # Add fresh entry
        cache.set("fresh", {"k": 1}, "p", "m")

        # Add old entry manually
        old_key = "old_entry_key"
        old_file = cache.cache_dir / f"{old_key}.json"
        old_entry = {
            "key": old_key,
            "result": {},
            "provider_id": "test",
            "model": "test",
            "created_at": time.time() - (5 * 86400),  # 5 days ago
            "execution_time_ms": 0,
        }
        with open(old_file, "w") as f:
            json.dump(old_entry, f)

        # Cleanup
        count = cache.cleanup_expired()
        assert count == 1

        # Fresh entry still exists
        assert cache.get("fresh") is not None

        # Old entry removed
        assert not old_file.exists()
