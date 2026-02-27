"""
Adversarial workflow tests for AvatarTaskService.

Written from BLACK-BOX perspective based on public contract only.
Scenarios designed by Gemini and Codex QA review — intended to BREAK things.

Each test assumes the implementation has bugs and tries to find them.
"""

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.avatar.cache import AICache
from src.avatar.config import AvatarConfig, AvatarProviderConfig, ExtractionConfig
from src.avatar.task_service import AvatarTaskService
from src.avatar.tasks.base import TaskResult
from src.avatar.tasks.model_tagging import ModelTaggingTask
from src.avatar.tasks.parameter_extraction import ParameterExtractionTask
from src.avatar.tasks.registry import TaskRegistry


# =============================================================================
# Fake engine
# =============================================================================


@dataclass
class FakeResponse:
    content: str
    success: bool = True
    error: Optional[str] = None
    duration_ms: int = 42

    def __bool__(self) -> bool:
        return self.success


# =============================================================================
# Helpers
# =============================================================================


def _registry() -> TaskRegistry:
    reg = TaskRegistry()
    reg.register(ParameterExtractionTask())
    reg.register(ModelTaggingTask())
    return reg


def _service(tmp_path: Path, **kw) -> AvatarTaskService:
    ext = ExtractionConfig(
        cache_enabled=kw.pop("cache_enabled", True),
        cache_ttl_days=kw.pop("cache_ttl_days", 30),
        cache_directory=str(tmp_path / "cache"),
    )
    config = AvatarConfig(
        provider=kw.pop("provider", "gemini"),
        extraction=ext,
        providers={
            "gemini": AvatarProviderConfig(model="gemini-2.0-flash", enabled=True),
            "claude": AvatarProviderConfig(model="claude-sonnet", enabled=True),
        },
        **kw,
    )
    return AvatarTaskService(config=config, registry=_registry())


def _arm(svc, task_type, content):
    """Arm service with a mock engine returning given content."""
    engine = MagicMock()
    engine.chat_sync.return_value = FakeResponse(content=content)
    svc._engine = engine
    svc._current_task_type = task_type
    return engine


# =============================================================================
# Codex #2: Wrapper vs direct API cache equivalence
# =============================================================================


class TestWrapperVsDirectCache:
    """extract_parameters() and execute_task('parameter_extraction', ...)
    must share the SAME cache. They are the same operation."""

    @pytest.mark.slow
    def test_wrapper_caches_then_direct_hits(self, tmp_path):
        """extract_parameters() populates cache, execute_task() hits it."""
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        r1 = svc.extract_parameters("wrapper test")
        assert r1.cached is False

        r2 = svc.execute_task("parameter_extraction", "wrapper test")
        assert r2.cached is True
        assert r2.output["steps"] == 20

    @pytest.mark.slow
    def test_direct_caches_then_wrapper_hits(self, tmp_path):
        """execute_task() populates cache, extract_parameters() hits it."""
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 30}')

        r1 = svc.execute_task("parameter_extraction", "direct test")
        assert r1.cached is False

        r2 = svc.extract_parameters("direct test")
        assert r2.cached is True
        assert r2.output["steps"] == 30

    @pytest.mark.slow
    def test_wrapper_and_direct_produce_single_cache_entry(self, tmp_path):
        """Calling both should still produce only 1 cache file."""
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 25}')

        svc.extract_parameters("single entry test")
        svc.execute_task("parameter_extraction", "single entry test")

        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 1


# =============================================================================
# Gemini #11 / Codex: use_cache=False behavior
# =============================================================================


class TestCacheBypass:
    """use_cache=False should skip reading cache AND skip writing cache."""

    @pytest.mark.slow
    def test_cache_false_doesnt_read_cache(self, tmp_path):
        """Existing cache entry is ignored when use_cache=False."""
        svc = _service(tmp_path)
        engine = _arm(svc, "parameter_extraction", '{"steps": 20}')

        # Populate cache
        svc.extract_parameters("bypass test")
        assert engine.chat_sync.call_count == 1

        # With use_cache=False, engine must be called again
        r = svc.extract_parameters("bypass test", use_cache=False)
        assert r.cached is False
        assert engine.chat_sync.call_count == 2

    @pytest.mark.slow
    def test_cache_false_doesnt_write_cache(self, tmp_path):
        """use_cache=False should not create/update cache entries."""
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        # Call with cache disabled
        svc.extract_parameters("no write test", use_cache=False)

        # Cache should still be empty
        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 0

    @pytest.mark.slow
    def test_cache_false_doesnt_overwrite_existing(self, tmp_path):
        """use_cache=False should not overwrite a valid cached entry."""
        svc = _service(tmp_path)
        engine = _arm(svc, "parameter_extraction", '{"steps": 20}')

        # Cache with steps=20
        svc.extract_parameters("overwrite test")

        # Change engine response
        engine.chat_sync.return_value = FakeResponse(content='{"steps": 99}')

        # Call with cache bypass
        r = svc.extract_parameters("overwrite test", use_cache=False)
        assert r.output["steps"] == 99
        assert r.cached is False

        # Original cache should still have steps=20
        r_cached = svc.extract_parameters("overwrite test")
        assert r_cached.cached is True
        assert r_cached.output["steps"] == 20


# =============================================================================
# Codex #7: Failed executions must NOT be cached
# =============================================================================


class TestFailedExecutionNotCached:
    """Failures should never poison the cache."""

    @pytest.mark.slow
    def test_ai_failure_not_cached(self, tmp_path):
        """AI engine failure → fallback success → result NOT cached."""
        svc = _service(tmp_path)
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("AI down")
        svc._engine = engine
        svc._current_task_type = "model_tagging"

        # This should succeed via fallback but NOT cache
        r1 = svc.execute_task("model_tagging", "Anime character model")
        assert r1.success is True
        assert r1.provider_id == "rule_based"

        # Cache should be empty — fallback results are not cached
        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 0

    @pytest.mark.slow
    def test_total_failure_not_cached(self, tmp_path):
        """Both AI and fallback fail → nothing cached."""
        svc = _service(tmp_path)
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("AI down")
        svc._engine = engine
        svc._current_task_type = "model_tagging"

        r = svc.execute_task("model_tagging", "xyz no keywords 123")
        assert r.success is False

        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 0

    @pytest.mark.slow
    def test_failed_then_success_caches_correctly(self, tmp_path):
        """After a failure, a subsequent success should cache normally."""
        svc = _service(tmp_path)

        # First: AI fails
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("temporary failure")
        svc._engine = engine
        svc._current_task_type = "parameter_extraction"

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(success=False, error="No match")
            r1 = svc.extract_parameters("recovery test")
        assert r1.success is False

        # Second: AI works
        engine.chat_sync.side_effect = None
        engine.chat_sync.return_value = FakeResponse(content='{"steps": 25}')
        r2 = svc.extract_parameters("recovery test")
        assert r2.success is True
        assert r2.cached is False
        assert r2.output["steps"] == 25

        # Third: cache hit
        r3 = svc.extract_parameters("recovery test")
        assert r3.cached is True
        assert r3.output["steps"] == 25


# =============================================================================
# Codex #11: Input canonicalization / whitespace variants
# =============================================================================


class TestInputCanonicalization:
    """Different whitespace = different cache keys (no hidden normalization)."""

    @pytest.mark.slow
    def test_trailing_space_is_different_key(self, tmp_path):
        """'test' and 'test ' are different cache entries."""
        svc = _service(tmp_path)
        engine = _arm(svc, "parameter_extraction", '{"steps": 20}')

        svc.extract_parameters("test")
        engine.chat_sync.return_value = FakeResponse(content='{"steps": 30}')
        svc.extract_parameters("test ")

        # Both should be in cache separately
        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 2

    @pytest.mark.slow
    def test_newline_variants_are_different(self, tmp_path):
        """Inputs with different whitespace are not collapsed."""
        svc = _service(tmp_path)
        engine = _arm(svc, "parameter_extraction", '{"steps": 10}')

        svc.extract_parameters("line1\nline2")
        engine.chat_sync.return_value = FakeResponse(content='{"steps": 20}')
        svc.extract_parameters("line1 line2")

        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 2


# =============================================================================
# Codex #12: Unexpected input types
# =============================================================================


class TestUnexpectedInputTypes:
    """Service must handle weird inputs gracefully."""

    @pytest.mark.slow
    def test_empty_string_returns_error(self, tmp_path):
        svc = _service(tmp_path)
        r = svc.execute_task("parameter_extraction", "")
        assert r.success is False
        assert r.error is not None

    @pytest.mark.slow
    def test_whitespace_only_returns_error(self, tmp_path):
        svc = _service(tmp_path)
        for text in ["   ", "\t\n", "\n\n\n"]:
            r = svc.execute_task("parameter_extraction", text)
            assert r.success is False

    @pytest.mark.slow
    def test_very_long_input_works(self, tmp_path):
        """50KB input should not crash the service."""
        svc = _service(tmp_path, cache_enabled=False)
        long_text = "Steps 20, CFG 7. " * 3000  # ~51KB
        _arm(svc, "parameter_extraction", '{"steps": 20, "cfg_scale": 7}')

        r = svc.execute_task("parameter_extraction", long_text)
        assert r.success is True
        assert r.output["steps"] == 20

    @pytest.mark.slow
    def test_unicode_input_works(self, tmp_path):
        """Unicode (CJK, emoji) input should not crash."""
        svc = _service(tmp_path, cache_enabled=False)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        for text in [
            "动漫风格模型 CFG 7",
            "🎨 Art style model steps 20",
            "café résumé naïve",
        ]:
            r = svc.execute_task("parameter_extraction", text)
            assert r.success is True


# =============================================================================
# Codex #8: Thundering herd — concurrent same-key
# =============================================================================


class TestThunderingHerd:
    """Many threads, same input, same task — only 1 AI call expected."""

    @pytest.mark.slow
    def test_concurrent_same_input_all_succeed(self, tmp_path):
        """10 threads with identical input all get correct results."""
        svc = _service(tmp_path, cache_enabled=True)
        engine = _arm(svc, "parameter_extraction", '{"steps": 42}')

        results = []
        errors = []

        def worker():
            try:
                r = svc.extract_parameters("thundering herd test")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 10
        assert all(r.success for r in results)
        assert all(r.output["steps"] == 42 for r in results)

        # Engine should be called at most a few times (not 10)
        # Because lock serializes, first call caches, rest should hit cache
        assert engine.chat_sync.call_count <= 2  # 1 ideal, maybe 2 with race


# =============================================================================
# Codex #15: Error → task switch → recovery
# =============================================================================


class TestErrorRecoveryAcrossTaskSwitch:
    """Failure in one task should not affect subsequent different task."""

    @pytest.mark.slow
    def test_failure_doesnt_poison_next_task(self, tmp_path):
        """model_tagging fails → parameter_extraction should work fine."""
        svc = _service(tmp_path, cache_enabled=False)

        # Tagging fails (engine error + no keywords = total fail)
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("engine crashed")
        svc._engine = engine
        svc._current_task_type = "model_tagging"

        r1 = svc.execute_task("model_tagging", "xyz no match 123")
        assert r1.success is False

        # Now extraction should work (new engine)
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeResponse(content='{"steps": 20}')
        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            r2 = svc.execute_task("parameter_extraction", "Steps 20")

        assert r2.success is True
        assert r2.output["steps"] == 20

    @pytest.mark.slow
    def test_failure_recovery_same_task_type(self, tmp_path):
        """Same task: fail → succeed → correct state."""
        svc = _service(tmp_path, cache_enabled=False)

        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("temporary")
        svc._engine = engine
        svc._current_task_type = "parameter_extraction"

        # Fails (fallback also fails for this input)
        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(success=False, error="No match")
            r1 = svc.extract_parameters("recovery same task")
        assert r1.success is False

        # Fix engine
        engine.chat_sync.side_effect = None
        engine.chat_sync.return_value = FakeResponse(content='{"steps": 15}')

        r2 = svc.extract_parameters("recovery same task")
        assert r2.success is True
        assert r2.output["steps"] == 15


# =============================================================================
# Codex #4: Cache stats integrity under churn
# =============================================================================


class TestCacheStatsIntegrity:
    """Cache stats must accurately reflect actual state after operations."""

    @pytest.mark.slow
    def test_stats_track_insertions(self, tmp_path):
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 1}')

        assert svc.get_cache_stats()["entry_count"] == 0

        for i in range(5):
            svc.extract_parameters(f"unique input {i}")

        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 5
        assert stats["total_size_bytes"] > 0

    @pytest.mark.slow
    def test_clear_returns_correct_count_and_zeros_stats(self, tmp_path):
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 1}')

        for i in range(3):
            svc.extract_parameters(f"clear test {i}")

        cleared = svc.clear_cache()
        assert cleared == 3

        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 0
        assert stats["total_size_bytes"] == 0

    @pytest.mark.slow
    def test_mixed_task_types_correct_total(self, tmp_path):
        """Multiple task types → combined stats."""
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        svc.execute_task("parameter_extraction", "input A")

        # Switch to tagging
        tag_engine = MagicMock()
        tag_engine.chat_sync.return_value = FakeResponse(
            content='{"category": "anime", "tags": ["test"]}')
        with patch("avatar_engine.AvatarEngine", return_value=tag_engine, create=True):
            svc.execute_task("model_tagging", "input A")  # Same text, different task

        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 2  # 1 per task type

        cleared = svc.clear_cache()
        assert cleared == 2


# =============================================================================
# Gemini #9: Cache expiration + cleanup
# =============================================================================


class TestCacheExpiration:
    """TTL expiration must work correctly."""

    @pytest.mark.slow
    def test_expired_entry_not_returned(self, tmp_path):
        """Cache entry older than TTL should be treated as miss."""
        svc = _service(tmp_path, cache_ttl_days=1)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        svc.extract_parameters("expiry test")

        # Manually age the cache file
        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 1
        with open(cache_files[0]) as f:
            data = json.load(f)
        data["created_at"] = time.time() - (2 * 86400)  # 2 days ago
        with open(cache_files[0], "w") as f:
            json.dump(data, f)

        # Should be cache miss (expired), engine called again
        r = svc.extract_parameters("expiry test")
        assert r.cached is False

    @pytest.mark.slow
    def test_cleanup_removes_expired_entries(self, tmp_path):
        """cleanup_cache() removes only expired entries."""
        svc = _service(tmp_path, cache_ttl_days=1)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        # Create 3 entries
        for i in range(3):
            svc.extract_parameters(f"cleanup test {i}")

        assert svc.get_cache_stats()["entry_count"] == 3

        # Age 2 of the 3 entries
        cache_files = sorted((tmp_path / "cache").glob("*.json"))
        for f in cache_files[:2]:
            with open(f) as fp:
                data = json.load(fp)
            data["created_at"] = time.time() - (5 * 86400)
            with open(f, "w") as fp:
                json.dump(data, fp)

        removed = svc.cleanup_cache()
        assert removed == 2

        stats = svc.get_cache_stats()
        assert stats["entry_count"] == 1


# =============================================================================
# Codex #6: Contradictory TaskResult fields
# =============================================================================


class TestTaskResultConsistency:
    """TaskResult fields must never be contradictory."""

    @pytest.mark.slow
    def test_success_true_always_has_output(self, tmp_path):
        """success=True must have non-None output."""
        svc = _service(tmp_path, cache_enabled=False)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        r = svc.extract_parameters("consistency test")
        assert r.success is True
        assert r.output is not None
        assert isinstance(r.output, dict)

    @pytest.mark.slow
    def test_success_true_has_no_error(self, tmp_path):
        """success=True must have error=None."""
        svc = _service(tmp_path, cache_enabled=False)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        r = svc.extract_parameters("no error test")
        assert r.success is True
        assert r.error is None

    @pytest.mark.slow
    def test_success_false_has_error_message(self, tmp_path):
        """success=False must have non-empty error."""
        svc = _service(tmp_path)
        r = svc.execute_task("nonexistent_task", "test")
        assert r.success is False
        assert r.error is not None
        assert len(r.error) > 0

    @pytest.mark.slow
    def test_success_true_has_extracted_by(self, tmp_path):
        """Every success=True with dict output must have _extracted_by."""
        svc = _service(tmp_path, cache_enabled=False)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        # AI path
        r1 = svc.extract_parameters("meta test")
        assert r1.success is True
        assert "_extracted_by" in r1.output
        assert "_ai_fields" in r1.output

    @pytest.mark.slow
    def test_cached_result_has_extracted_by(self, tmp_path):
        """Cached result must also have _extracted_by."""
        svc = _service(tmp_path, cache_enabled=True)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        svc.extract_parameters("cached meta test")
        r2 = svc.extract_parameters("cached meta test")

        assert r2.cached is True
        assert r2.success is True
        assert "_extracted_by" in r2.output
        assert "_ai_fields" in r2.output

    @pytest.mark.slow
    def test_fallback_result_has_extracted_by(self, tmp_path):
        """Fallback result must also have _extracted_by."""
        svc = _service(tmp_path, cache_enabled=False)
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("down")
        svc._engine = engine
        svc._current_task_type = "model_tagging"

        r = svc.execute_task("model_tagging", "Anime style character portrait")
        assert r.success is True
        assert r.provider_id == "rule_based"
        assert "_extracted_by" in r.output
        assert "_ai_fields" in r.output

    @pytest.mark.slow
    def test_provider_id_consistent_with_extracted_by(self, tmp_path):
        """provider_id on TaskResult must match _extracted_by in output."""
        svc = _service(tmp_path, cache_enabled=False)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        r = svc.extract_parameters("provider match test")
        assert r.output["_extracted_by"] == r.provider_id

    @pytest.mark.slow
    def test_cached_provider_consistent(self, tmp_path):
        """Cache hit: provider_id and _extracted_by still match."""
        svc = _service(tmp_path)
        _arm(svc, "parameter_extraction", '{"steps": 20}')

        svc.extract_parameters("cached provider test")
        r2 = svc.extract_parameters("cached provider test")

        assert r2.cached is True
        assert r2.output["_extracted_by"] == r2.provider_id


# =============================================================================
# Gemini #14: Registry reset and integrity
# =============================================================================


class TestRegistryIntegrity:
    """Registry operations must not leak across service instances."""

    @pytest.mark.slow
    def test_reset_registry_makes_task_unavailable(self, tmp_path):
        """After registry.reset(), tasks are gone."""
        svc = _service(tmp_path)
        assert svc.registry.get("parameter_extraction") is not None

        svc.registry.reset()
        r = svc.execute_task("parameter_extraction", "test after reset")
        assert r.success is False
        assert "Unknown task type" in r.error

    @pytest.mark.slow
    def test_separate_services_have_isolated_registries(self, tmp_path):
        """Two services with separate registries don't interfere."""
        svc1 = _service(tmp_path)
        svc2 = _service(tmp_path)

        svc1.registry.reset()
        # svc1 has no tasks
        r1 = svc1.execute_task("parameter_extraction", "test")
        assert r1.success is False

        # svc2 still has tasks
        _arm(svc2, "parameter_extraction", '{"steps": 20}')
        r2 = svc2.extract_parameters("test")
        assert r2.success is True
