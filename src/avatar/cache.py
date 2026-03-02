"""
AI Cache

Caches AI extraction results to avoid redundant API calls.
Uses SHA-256 hash of description as cache key.
Thread-safe: all file operations are guarded by a lock.
"""

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached AI result."""

    key: str
    result: Dict[str, Any]
    provider_id: str
    model: str
    created_at: float  # Unix timestamp
    execution_time_ms: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": self.key,
            "result": self.result,
            "provider_id": self.provider_id,
            "model": self.model,
            "created_at": self.created_at,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            result=data["result"],
            provider_id=data["provider_id"],
            model=data["model"],
            created_at=data["created_at"],
            execution_time_ms=data.get("execution_time_ms", 0),
        )

    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at

    def age_days(self) -> float:
        """Get age of cache entry in days."""
        return self.age_seconds() / 86400


class AICache:
    """
    Cache for AI extraction results.

    Stores results as JSON files using content hash as filename.
    """

    def __init__(
        self,
        cache_dir: str = "~/.synapse/store/data/cache/ai",
        ttl_days: int = 30,
    ):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_days: Time-to-live in days (0 = no expiry)
        """
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        self.ttl_days = ttl_days
        self._lock = threading.Lock()

        # Ensure cache directory exists
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("[ai-cache] Failed to create cache directory %s: %s", cache_dir, e)

    def get_cache_key(self, content: str) -> str:
        """
        Generate deterministic cache key for content.

        Uses SHA-256 hash, truncated to 16 characters.

        Args:
            content: Content to hash (e.g., description)

        Returns:
            16-character hex hash
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, content: str) -> Optional[CacheEntry]:
        """
        Get cached result for content.

        Args:
            content: Content to look up

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        key = self.get_cache_key(content)
        cache_file = self.cache_dir / f"{key}.json"

        with self._lock:
            if not cache_file.exists():
                logger.debug(f"[ai-cache] Cache miss for key: {key}")
                return None

            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)

                entry = CacheEntry.from_dict(data)

                # Check TTL
                if self.ttl_days > 0 and entry.age_days() > self.ttl_days:
                    logger.debug(
                        f"[ai-cache] Cache expired for key: {key} "
                        f"(age: {entry.age_days():.1f}d > {self.ttl_days}d)"
                    )
                    cache_file.unlink(missing_ok=True)
                    return None

                logger.debug(
                    f"[ai-cache] Cache hit for key: {key} (age: {entry.age_days():.1f}d)"
                )
                return entry

            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"[ai-cache] Invalid cache entry {key}: {e}")
                cache_file.unlink(missing_ok=True)
                return None

    def set(
        self,
        content: str,
        result: Dict[str, Any],
        provider_id: str,
        model: str,
        execution_time_ms: int = 0,
    ) -> CacheEntry:
        """
        Store result in cache.

        Args:
            content: Original content (for key generation)
            result: Extraction result to cache
            provider_id: Provider that generated the result
            model: Model used
            execution_time_ms: Execution time

        Returns:
            Created CacheEntry
        """
        key = self.get_cache_key(content)

        entry = CacheEntry(
            key=key,
            result=result,
            provider_id=provider_id,
            model=model,
            created_at=time.time(),
            execution_time_ms=execution_time_ms,
        )

        cache_file = self.cache_dir / f"{key}.json"
        with self._lock:
            try:
                with open(cache_file, "w") as f:
                    json.dump(entry.to_dict(), f, indent=2)
            except OSError as e:
                logger.warning("[ai-cache] Failed to write cache file %s: %s", key, e)
                return entry

        logger.debug(f"[ai-cache] Result cached with key: {key}")
        return entry

    def invalidate(self, content: str) -> bool:
        """
        Remove cached result for content.

        Args:
            content: Content to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        key = self.get_cache_key(content)
        cache_file = self.cache_dir / f"{key}.json"

        with self._lock:
            if cache_file.exists():
                cache_file.unlink(missing_ok=True)
                logger.debug(f"[ai-cache] Cache invalidated for key: {key}")
                return True

        return False

    def clear(self) -> int:
        """
        Clear all cached entries.

        Returns:
            Number of entries removed
        """
        count = 0
        with self._lock:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink(missing_ok=True)
                    count += 1
                except OSError as e:
                    logger.warning("[ai-cache] Failed to remove %s: %s", cache_file.name, e)

        logger.info(f"[ai-cache] Cache cleared: {count} entries removed")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        if self.ttl_days <= 0:
            return 0

        count = 0
        with self._lock:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r") as f:
                        data = json.load(f)

                    entry = CacheEntry.from_dict(data)
                    if entry.age_days() > self.ttl_days:
                        cache_file.unlink(missing_ok=True)
                        count += 1

                except (json.JSONDecodeError, KeyError, OSError) as e:
                    logger.warning("[ai-cache] Removing invalid entry %s: %s", cache_file.name, e)
                    try:
                        cache_file.unlink(missing_ok=True)
                    except OSError:
                        pass
                    count += 1

        if count > 0:
            logger.info(f"[ai-cache] Cache cleanup: {count} expired entries removed")

        return count

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        entries = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in entries)

        return {
            "cache_dir": str(self.cache_dir),
            "entry_count": len(entries),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "ttl_days": self.ttl_days,
        }
