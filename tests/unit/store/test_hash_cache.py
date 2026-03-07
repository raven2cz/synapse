"""
Tests for hash_cache.py — persistent hash cache for local model files.
"""

import json
import time
from pathlib import Path

import pytest

from src.store.hash_cache import HashCache, HashEntry, compute_sha256


class TestComputeSha256:
    def test_computes_hash(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        h = compute_sha256(f)
        assert len(h) == 64
        assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        h = compute_sha256(f)
        assert len(h) == 64

    def test_large_file(self, tmp_path):
        f = tmp_path / "large.bin"
        f.write_bytes(b"x" * (1024 * 1024 * 10))  # 10MB
        h = compute_sha256(f)
        assert len(h) == 64


class TestHashCache:
    def test_empty_cache(self, tmp_path):
        cache = HashCache(tmp_path)
        assert cache.size == 0

    def test_compute_and_cache(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"model data")

        cache = HashCache(registry)
        h = cache.compute_and_cache(model_file)
        assert len(h) == 64
        assert cache.size == 1

    def test_get_cached(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"model data")

        cache = HashCache(registry)
        h1 = cache.compute_and_cache(model_file)
        h2 = cache.get(model_file)
        assert h1 == h2

    def test_get_uncached_returns_none(self, tmp_path):
        cache = HashCache(tmp_path)
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"data")
        assert cache.get(model_file) is None

    def test_get_or_compute(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"data")

        cache = HashCache(registry)
        h1 = cache.get_or_compute(model_file)
        h2 = cache.get_or_compute(model_file)  # Should use cache
        assert h1 == h2

    def test_invalidate_on_mtime_change(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"data v1")

        cache = HashCache(registry)
        h1 = cache.compute_and_cache(model_file)

        # Modify file
        time.sleep(0.01)
        model_file.write_bytes(b"data v2")

        assert cache.get(model_file) is None  # Stale
        h2 = cache.compute_and_cache(model_file)
        assert h1 != h2

    def test_invalidate_explicit(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"data")

        cache = HashCache(registry)
        cache.compute_and_cache(model_file)
        assert cache.size == 1
        cache.invalidate(model_file)
        assert cache.size == 0
        assert cache.get(model_file) is None

    def test_clear(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()

        cache = HashCache(registry)
        for i in range(5):
            f = tmp_path / f"model_{i}.safetensors"
            f.write_bytes(f"data {i}".encode())
            cache.compute_and_cache(f)

        assert cache.size == 5
        cache.clear()
        assert cache.size == 0

    def test_persistence(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"persistent data")

        cache1 = HashCache(registry)
        h1 = cache1.compute_and_cache(model_file)
        cache1.save()

        # Load fresh cache from disk
        cache2 = HashCache(registry)
        h2 = cache2.get(model_file)
        assert h1 == h2

    def test_save_only_when_dirty(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()

        cache = HashCache(registry)
        cache.save()  # Not dirty, should not create file
        assert not (registry / "local_model_hashes.json").exists()

        f = tmp_path / "model.safetensors"
        f.write_bytes(b"data")
        cache.compute_and_cache(f)
        cache.save()  # Dirty now
        assert (registry / "local_model_hashes.json").exists()

    def test_corrupt_cache_file(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        (registry / "local_model_hashes.json").write_text("not json")

        cache = HashCache(registry)
        assert cache.size == 0  # Should recover gracefully

    def test_nonexistent_file_get(self, tmp_path):
        cache = HashCache(tmp_path)
        assert cache.get(tmp_path / "nonexistent.safetensors") is None
