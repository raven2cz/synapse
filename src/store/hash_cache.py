"""
Hash cache — persistent cache for local model file hashes.

Based on PLAN-Resolve-Model.md v0.7.1 section G1, Phase 0 item 11.

Cache structure: { path: { sha256, mtime, size, computed_at } }
Persistence: data/registry/local_model_hashes.json
Invalidation: mtime+size change → rehash
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

HASH_CACHE_FILENAME = "local_model_hashes.json"
CHUNK_SIZE = 1024 * 1024 * 8  # 8MB chunks for SHA256


@dataclass
class HashEntry:
    """Cached hash entry for a local file."""
    sha256: str
    mtime: float
    size: int
    computed_at: float  # Unix timestamp


class HashCache:
    """Persistent hash cache for local model files.

    Stores SHA256 hashes keyed by file path. Invalidates when
    mtime or size changes. Full background scan is Phase 3;
    this module provides the cache + sync hash computation.
    """

    def __init__(self, registry_path: Path):
        """Initialize with path to the registry directory.

        Cache file will be stored at registry_path / local_model_hashes.json.
        """
        self._cache_file = registry_path / HASH_CACHE_FILENAME
        self._entries: Dict[str, HashEntry] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if not self._cache_file.exists():
            return

        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            for path_str, entry_data in data.items():
                self._entries[path_str] = HashEntry(**entry_data)
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Failed to load hash cache from %s: %s", self._cache_file, e)
            self._entries = {}

    def save(self) -> None:
        """Persist cache to disk (only if dirty). Uses atomic write (temp + rename)."""
        if not self._dirty:
            return

        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {path: asdict(entry) for path, entry in self._entries.items()}
            content = json.dumps(data, indent=2)
            # Atomic write: write to temp file, then rename
            tmp_file = self._cache_file.with_suffix(".tmp")
            tmp_file.write_text(content, encoding="utf-8")
            tmp_file.replace(self._cache_file)
            self._dirty = False
        except OSError as e:
            logger.warning("Failed to save hash cache to %s: %s", self._cache_file, e)

    def get(self, file_path: Path) -> Optional[str]:
        """Get cached SHA256 for a file, or None if stale/missing.

        Returns the hash only if the file's mtime and size match the cache.
        """
        key = str(file_path)
        entry = self._entries.get(key)
        if entry is None:
            return None

        try:
            stat = file_path.stat()
        except OSError:
            return None

        if stat.st_mtime != entry.mtime or stat.st_size != entry.size:
            return None

        return entry.sha256

    def compute_and_cache(self, file_path: Path) -> str:
        """Compute SHA256 for a file and store in cache.

        This is a synchronous operation. For async, use compute_hash_async().
        """
        sha256 = compute_sha256(file_path)
        stat = file_path.stat()

        self._entries[str(file_path)] = HashEntry(
            sha256=sha256,
            mtime=stat.st_mtime,
            size=stat.st_size,
            computed_at=time.time(),
        )
        self._dirty = True

        return sha256

    def get_or_compute(self, file_path: Path) -> str:
        """Get cached hash or compute and cache it."""
        cached = self.get(file_path)
        if cached is not None:
            return cached
        return self.compute_and_cache(file_path)

    def invalidate(self, file_path: Path) -> None:
        """Remove a file from the cache."""
        key = str(file_path)
        if key in self._entries:
            del self._entries[key]
            self._dirty = True

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self._dirty = True

    @property
    def size(self) -> int:
        """Number of cached entries."""
        return len(self._entries)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


async def compute_sha256_async(file_path: Path) -> str:
    """Compute SHA256 hash of a file without blocking the event loop.

    Offloads the I/O-heavy computation to a thread pool via asyncio.to_thread().
    Use this in FastAPI endpoints for large files (7GB+ checkpoints).
    """
    import asyncio
    return await asyncio.to_thread(compute_sha256, file_path)
