"""
Workflow tests for AvatarTaskService.

These tests exercise REAL multi-task scenarios to find bugs —
not to cover code paths, but to verify end-to-end behavior
matches expectations.

Uses two real tasks (parameter_extraction, model_tagging)
with real cache, real registry, real config serialization.
Only HTTP/subprocess is mocked.
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
from src.avatar.task_service import AvatarTaskService, _extract_json
from src.avatar.tasks.base import TaskResult
from src.avatar.tasks.model_tagging import ModelTaggingTask
from src.avatar.tasks.parameter_extraction import ParameterExtractionTask
from src.avatar.tasks.registry import TaskRegistry


# =============================================================================
# Fake engine response
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


def _make_registry() -> TaskRegistry:
    """Create registry with both real tasks."""
    reg = TaskRegistry()
    reg.register(ParameterExtractionTask())
    reg.register(ModelTaggingTask())
    return reg


def _make_service(tmp_path: Path, **overrides) -> AvatarTaskService:
    """Create service with real cache, real registry, two tasks."""
    cache_dir = str(tmp_path / "cache")
    ext = ExtractionConfig(
        cache_enabled=overrides.pop("cache_enabled", True),
        cache_ttl_days=overrides.pop("cache_ttl_days", 30),
        cache_directory=cache_dir,
    )
    config = AvatarConfig(
        provider=overrides.pop("provider", "gemini"),
        extraction=ext,
        providers={
            "gemini": AvatarProviderConfig(model="gemini-2.0-flash", enabled=True),
            "claude": AvatarProviderConfig(model="claude-sonnet", enabled=True),
        },
        **overrides,
    )
    return AvatarTaskService(config=config, registry=_make_registry())


def _mock_engine_for(service, task_type, response_content):
    """Pre-configure service with a mock engine ready for given task type."""
    engine = MagicMock()
    engine.chat_sync.return_value = FakeResponse(content=response_content)
    service._engine = engine
    service._current_task_type = task_type
    return engine


# =============================================================================
# Workflow 1: Multi-task round-trip with real cache
#
# scenario: extract params → tag model → re-extract (cache) → re-tag (cache)
# verify: correct isolation, no cross-contamination
# =============================================================================


class TestMultiTaskRoundTrip:
    """Full lifecycle: two different tasks, cache, re-execution."""

    @pytest.mark.slow
    def test_extract_then_tag_same_description(self, tmp_path):
        """Same input text, different tasks → different results, separate cache."""
        service = _make_service(tmp_path)
        description = "Anime SDXL LoRA. Steps 20-30, CFG 7. Trigger: anime girl"

        # 1. Parameter extraction
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": {"min": 20, "max": 30}, "cfg_scale": 7}')

        r1 = service.execute_task("parameter_extraction", description)
        assert r1.success is True
        assert r1.output["steps"] == {"min": 20, "max": 30}
        assert r1.output["cfg_scale"] == 7
        assert r1.cached is False
        assert r1.output["_extracted_by"] == "avatar:gemini"

        # 2. Model tagging (same text!)
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeResponse(
            content='{"category": "anime", "tags": ["lora", "sdxl"], '
                    '"trigger_words": ["anime girl"]}')

        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            r2 = service.execute_task("model_tagging", description)

        assert r2.success is True
        assert r2.output["category"] == "anime"
        assert "lora" in r2.output["tags"]
        assert r2.cached is False

        # 3. Re-extract params (should hit cache, NOT call engine)
        r3 = service.execute_task("parameter_extraction", description)
        assert r3.success is True
        assert r3.cached is True
        assert r3.output["steps"] == {"min": 20, "max": 30}
        assert r3.output["_extracted_by"] == "avatar:gemini"

        # 4. Re-tag model (should hit cache, NOT call engine)
        r4 = service.execute_task("model_tagging", description)
        assert r4.success is True
        assert r4.cached is True
        assert r4.output["category"] == "anime"

        # 5. Verify separate cache files
        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 2

    @pytest.mark.slow
    def test_cache_not_cross_contaminated(self, tmp_path):
        """Parameter extraction cache cannot be returned for model tagging."""
        service = _make_service(tmp_path)
        text = "SDXL anime checkpoint"

        # Cache a parameter extraction result
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 25}')
        service.execute_task("parameter_extraction", text)

        # Model tagging with same text should NOT get param cache
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeResponse(
            content='{"category": "anime", "tags": ["sdxl"]}')
        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            r2 = service.execute_task("model_tagging", text)

        assert r2.cached is False  # Must be fresh, not cross-contaminated
        assert "steps" not in r2.output  # Must NOT have param data
        assert r2.output["category"] == "anime"


# =============================================================================
# Workflow 2: Metadata consistency
#
# verify: _extracted_by and _ai_fields are present and correct
#         in ALL paths (AI, cache, fallback)
# =============================================================================


class TestMetadataConsistency:
    """Verify _extracted_by and _ai_fields are correct in all paths."""

    @pytest.mark.slow
    def test_ai_path_has_metadata(self, tmp_path):
        """Fresh AI result has correct metadata."""
        service = _make_service(tmp_path, cache_enabled=False)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20, "sampler": "Euler"}')

        result = service.extract_parameters("test")
        assert result.output["_extracted_by"] == "avatar:gemini"
        assert set(result.output["_ai_fields"]) == {"steps", "sampler"}

    @pytest.mark.slow
    def test_cache_path_has_metadata(self, tmp_path):
        """Cached result has correct metadata (same as original)."""
        service = _make_service(tmp_path, cache_enabled=True)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20, "sampler": "Euler"}')

        # Fresh call
        r1 = service.extract_parameters("test")
        # Cache hit
        r2 = service.extract_parameters("test")

        assert r2.cached is True
        assert r2.output["_extracted_by"] == "avatar:gemini"
        assert set(r2.output["_ai_fields"]) == {"steps", "sampler"}

    @pytest.mark.slow
    def test_cache_does_not_store_metadata_keys(self, tmp_path):
        """Cache file on disk must NOT contain _extracted_by or _ai_fields."""
        service = _make_service(tmp_path, cache_enabled=True)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20, "sampler": "Euler"}')

        service.extract_parameters("test for disk check")

        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 1

        with open(cache_files[0]) as f:
            cached_data = json.load(f)

        stored_result = cached_data["result"]
        assert "_extracted_by" not in stored_result
        assert "_ai_fields" not in stored_result
        assert stored_result == {"steps": 20, "sampler": "Euler"}

    @pytest.mark.slow
    def test_fallback_path_has_metadata(self, tmp_path):
        """Fallback result also has _extracted_by metadata."""
        service = _make_service(tmp_path, cache_enabled=False)

        # Engine fails → fallback
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("Provider down")
        service._engine = engine
        service._current_task_type = "parameter_extraction"

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=True,
                output={"steps": 20, "cfg_scale": 7},
            )
            result = service.extract_parameters("Steps: 20, CFG: 7")

        assert result.success is True
        assert result.provider_id == "rule_based"
        # This is the bug fix #2 - verify it works
        assert "_extracted_by" in result.output
        assert result.output["_extracted_by"] == "rule_based"
        assert set(result.output["_ai_fields"]) == {"steps", "cfg_scale"}

    @pytest.mark.slow
    def test_tagging_fallback_has_metadata(self, tmp_path):
        """Model tagging fallback also gets metadata enrichment."""
        service = _make_service(tmp_path, cache_enabled=False)

        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("down")
        service._engine = engine
        service._current_task_type = "model_tagging"

        result = service.execute_task(
            "model_tagging",
            "Anime style SDXL LoRA for character illustrations. Trigger: anime girl",
        )

        assert result.success is True
        assert result.provider_id == "rule_based"
        assert "_extracted_by" in result.output
        assert result.output["_extracted_by"] == "rule_based"
        assert "category" in result.output["_ai_fields"]


# =============================================================================
# Workflow 3: Cache data integrity
#
# verify: cache stores clean data, mutations don't affect cached data,
#         provider switch invalidates correctly
# =============================================================================


class TestCacheDataIntegrity:
    """Verify cache stores clean data and mutations don't leak."""

    @pytest.mark.slow
    def test_output_mutation_doesnt_corrupt_cache(self, tmp_path):
        """Mutating returned output dict must not affect next cache hit."""
        service = _make_service(tmp_path)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20, "sampler": "Euler"}')

        # Get result and mutate it
        r1 = service.extract_parameters("mutation test")
        r1.output["steps"] = 999
        r1.output["injected"] = "hacked"
        del r1.output["sampler"]

        # Cache hit should return original data
        r2 = service.extract_parameters("mutation test")
        assert r2.cached is True
        assert r2.output["steps"] == 20
        assert r2.output["sampler"] == "Euler"
        assert "injected" not in r2.output

    @pytest.mark.slow
    def test_different_providers_get_separate_cache(self, tmp_path):
        """Switching provider means different cache keys."""
        text = "test caching with providers"

        # Service with gemini
        service1 = _make_service(tmp_path, provider="gemini")
        engine1 = _mock_engine_for(service1, "parameter_extraction",
            '{"steps": 20}')
        r1 = service1.extract_parameters(text)
        assert r1.output["steps"] == 20

        # Service with claude (same cache dir!)
        service2 = _make_service(tmp_path, provider="claude")
        engine2 = _mock_engine_for(service2, "parameter_extraction",
            '{"steps": 30}')
        r2 = service2.extract_parameters(text)
        # Must NOT return gemini's cached result
        assert r2.cached is False
        assert r2.output["steps"] == 30

        # Verify 2 separate cache files
        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 2

    @pytest.mark.slow
    def test_corrupted_cache_file_handled_gracefully(self, tmp_path):
        """Corrupted JSON in cache file doesn't crash, triggers re-execution."""
        service = _make_service(tmp_path)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20}')

        # Execute to create cache
        r1 = service.extract_parameters("corruption test")
        assert r1.cached is False

        # Corrupt the cache file
        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 1
        with open(cache_files[0], "w") as f:
            f.write("{invalid json garbage")

        # Next call should handle gracefully (cache.get returns None for invalid JSON)
        r2 = service.extract_parameters("corruption test")
        # AICache.get() catches JSONDecodeError and returns None → fresh execution
        assert r2.success is True
        assert r2.output["steps"] == 20

    @pytest.mark.slow
    def test_cache_entry_with_extra_fields_still_works(self, tmp_path):
        """Cache file with extra fields (forward compat) doesn't crash."""
        service = _make_service(tmp_path)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20}')

        # Create cache normally
        service.extract_parameters("forward compat test")

        # Inject extra fields into cache file
        cache_files = list((tmp_path / "cache").glob("*.json"))
        with open(cache_files[0]) as f:
            data = json.load(f)
        data["future_field"] = "from v2.0"
        data["result"]["extra_param"] = 42
        with open(cache_files[0], "w") as f:
            json.dump(data, f)

        # Should still work (extra fields ignored)
        r2 = service.extract_parameters("forward compat test")
        assert r2.cached is True
        assert r2.output["steps"] == 20
        # Extra field from cache is preserved (no parse_result to strip it)
        assert r2.output["extra_param"] == 42


# =============================================================================
# Workflow 4: Engine lifecycle under multi-task switching
#
# verify: engine restarts correctly, state is clean between switches,
#         shutdown mid-workflow doesn't corrupt state
# =============================================================================


class TestEngineLifecycleWorkflows:
    """Real multi-task engine switching scenarios."""

    @pytest.mark.slow
    def test_rapid_task_switching(self, tmp_path):
        """Switch between tasks rapidly — engine restarts each time."""
        service = _make_service(tmp_path, cache_enabled=False)
        stop_count = 0
        start_count = 0

        def make_engine(content):
            nonlocal start_count
            e = MagicMock()
            e.chat_sync.return_value = FakeResponse(content=content)
            start_count += 1
            return e

        def track_stop():
            nonlocal stop_count
            stop_count += 1

        # Start with param extraction
        engine1 = make_engine('{"steps": 20}')
        engine1.stop_sync.side_effect = track_stop
        service._engine = engine1
        service._current_task_type = "parameter_extraction"

        r1 = service.execute_task("parameter_extraction", "test A")
        assert r1.success is True
        assert stop_count == 0  # No switch needed

        # Switch to tagging
        engine2 = make_engine('{"category": "anime", "tags": ["test"]}')
        engine2.stop_sync.side_effect = track_stop
        with patch("avatar_engine.AvatarEngine", return_value=engine2, create=True):
            r2 = service.execute_task("model_tagging", "test B")
        assert r2.success is True
        assert stop_count == 1  # Old engine stopped

        # Switch back to extraction
        engine3 = make_engine('{"steps": 30}')
        engine3.stop_sync.side_effect = track_stop
        with patch("avatar_engine.AvatarEngine", return_value=engine3, create=True):
            r3 = service.execute_task("parameter_extraction", "test C")
        assert r3.success is True
        assert stop_count == 2  # Tagging engine stopped

        # Same task again — no switch
        r4 = service.execute_task("parameter_extraction", "test D")
        assert r4.success is True
        assert stop_count == 2  # Still 2, no additional stop

    @pytest.mark.slow
    def test_shutdown_then_resume_different_task(self, tmp_path):
        """Shutdown, then execute different task type — clean restart."""
        service = _make_service(tmp_path, cache_enabled=False)

        engine1 = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20}')
        service.execute_task("parameter_extraction", "before shutdown")

        # Shutdown
        service.shutdown()
        assert service._engine is None
        assert service._current_task_type is None

        # Resume with different task
        engine2 = MagicMock()
        engine2.chat_sync.return_value = FakeResponse(
            content='{"category": "anime", "tags": ["test"]}')
        with patch("avatar_engine.AvatarEngine", return_value=engine2, create=True):
            r = service.execute_task("model_tagging", "after shutdown")

        assert r.success is True
        assert r.output["category"] == "anime"
        assert service._current_task_type == "model_tagging"


# =============================================================================
# Workflow 5: Fallback chain completeness
#
# verify: all 3 levels work (AI → fallback → error),
#         each level produces consistent output structure
# =============================================================================


class TestFallbackChainWorkflows:
    """Complete fallback chain testing with both task types."""

    @pytest.mark.slow
    def test_parameter_extraction_all_three_levels(self, tmp_path):
        """Level 1: AI, Level 2: rule-based, Level 3: error."""
        service = _make_service(tmp_path, cache_enabled=False)

        # Level 1: AI success
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20, "sampler": "Euler"}')
        r1 = service.extract_parameters("Steps 20, Euler sampler")
        assert r1.success is True
        assert r1.provider_id == "avatar:gemini"
        assert "_extracted_by" in r1.output

        # Level 2: AI fails, rule-based succeeds
        engine.chat_sync.side_effect = RuntimeError("AI down")
        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=True,
                output={"steps": 20},
            )
            r2 = service.extract_parameters("Steps: 20")
        assert r2.success is True
        assert r2.provider_id == "rule_based"
        assert "_extracted_by" in r2.output

        # Level 3: AI fails, rule-based also fails
        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            mock_rb.return_value = RuleBasedResult(
                success=False,
                error="No patterns matched",
            )
            r3 = service.extract_parameters("completely unparseable gibberish xyz")
        assert r3.success is False
        assert r3.error is not None

    @pytest.mark.slow
    def test_tagging_ai_fail_fallback_extracts_keywords(self, tmp_path):
        """Model tagging: AI fails, keyword fallback finds tags."""
        service = _make_service(tmp_path, cache_enabled=False)
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("timeout")
        service._engine = engine
        service._current_task_type = "model_tagging"

        result = service.execute_task(
            "model_tagging",
            "Photorealistic SDXL model for portrait photography. "
            "Trigger words: realistic photo, 4k detail",
        )

        assert result.success is True
        assert result.provider_id == "rule_based"
        assert result.output["category"] == "photorealistic"
        assert "portrait" in result.output["content_types"]
        assert "realistic photo" in result.output["trigger_words"]
        assert "_extracted_by" in result.output

    @pytest.mark.slow
    def test_tagging_fallback_no_keywords_returns_failure(self, tmp_path):
        """Model tagging: AI fails, fallback finds nothing."""
        service = _make_service(tmp_path, cache_enabled=False)
        engine = MagicMock()
        engine.chat_sync.side_effect = RuntimeError("timeout")
        service._engine = engine
        service._current_task_type = "model_tagging"

        result = service.execute_task("model_tagging", "xyz 123 no keywords here")
        assert result.success is False


# =============================================================================
# Workflow 6: parse_result contract verification
#
# verify: parse_result is called exactly ONCE on fresh AI output,
#         NEVER on cached output, and handles edge cases correctly
# =============================================================================


class TestParseResultContract:
    """Verify parse_result is called correctly in all paths."""

    @pytest.mark.slow
    def test_parse_result_called_once_on_fresh(self, tmp_path):
        """parse_result is called exactly once on fresh AI output."""
        service = _make_service(tmp_path, cache_enabled=False)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20, "_private": "strip"}')

        result = service.extract_parameters("test")
        # _private was stripped by parse_result
        assert "_private" not in result.output
        # But metadata was added
        assert "_extracted_by" in result.output

    @pytest.mark.slow
    def test_parse_result_not_called_on_cache_hit(self, tmp_path):
        """parse_result is NOT called on cache hit (bug #1 fix)."""
        service = _make_service(tmp_path, cache_enabled=True)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 20}')

        # Populate cache
        service.extract_parameters("test")

        # Monkey-patch parse_result to detect calls
        original = service.registry.get("parameter_extraction").parse_result
        call_count = [0]

        def counting_parse(raw):
            call_count[0] += 1
            return original(raw)

        service.registry.get("parameter_extraction").parse_result = counting_parse

        # Cache hit — parse_result should NOT be called
        r2 = service.extract_parameters("test")
        assert r2.cached is True
        assert call_count[0] == 0  # Not called!

        # Restore
        service.registry.get("parameter_extraction").parse_result = original

    @pytest.mark.slow
    def test_non_idempotent_parse_works_with_cache(self, tmp_path):
        """A task with non-idempotent parse_result works because cache
        skips parse_result (bug #1 fix verification)."""
        from src.avatar.tasks.base import AITask

        class CountingTask(AITask):
            """Task where parse_result adds a counter field."""
            task_type = "counting_test"
            SKILL_NAMES = ()
            _counter = 0

            def build_system_prompt(self, skills_content):
                return "test"

            def parse_result(self, raw_output):
                if not isinstance(raw_output, dict):
                    return {}
                CountingTask._counter += 1
                result = dict(raw_output)
                result["parse_count"] = CountingTask._counter
                return result

            def validate_output(self, output):
                return isinstance(output, dict) and len(output) > 0

        reg = _make_registry()
        reg.register(CountingTask())

        service = _make_service(tmp_path, cache_enabled=True)
        service.registry = reg

        engine = _mock_engine_for(service, "counting_test",
            '{"data": "hello"}')

        # Fresh call — parse_result called, counter=1
        r1 = service.execute_task("counting_test", "test input")
        assert r1.output["parse_count"] == 1

        # Cache hit — parse_result NOT called, counter stays 1
        r2 = service.execute_task("counting_test", "test input")
        assert r2.cached is True
        assert r2.output["data"] == "hello"
        # parse_count is in cache because it was in parsed output
        assert r2.output["parse_count"] == 1
        # Counter didn't increment (parse_result not called)
        assert CountingTask._counter == 1


# =============================================================================
# Workflow 7: Edge cases and error recovery
# =============================================================================


class TestEdgeCasesAndRecovery:
    """Edge cases that could break the service."""

    @pytest.mark.slow
    def test_ai_returns_valid_json_but_empty_after_parse(self, tmp_path):
        """AI returns JSON that becomes empty after parse_result stripping."""
        service = _make_service(tmp_path, cache_enabled=False)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"_internal": "only private keys"}')

        # parse_result strips _ keys → empty dict → validate_output fails
        # → should trigger fallback
        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=True,
                output={"steps": 15},
            )
            result = service.extract_parameters("private keys only")

        assert result.success is True
        assert result.provider_id == "rule_based"

    @pytest.mark.slow
    def test_ai_returns_non_json_triggers_fallback(self, tmp_path):
        """AI returns text instead of JSON → fallback."""
        service = _make_service(tmp_path, cache_enabled=False)
        engine = _mock_engine_for(service, "parameter_extraction",
            "I'm sorry, I cannot extract parameters from this description.")

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=True,
                output={"steps": 20},
            )
            result = service.extract_parameters("test non-json")

        assert result.success is True
        assert result.provider_id == "rule_based"

    @pytest.mark.slow
    def test_whitespace_only_input_rejected(self, tmp_path):
        """Whitespace-only input returns error without engine call."""
        service = _make_service(tmp_path)
        engine = MagicMock()
        service._engine = engine

        for text in ["", "   ", "\n\t", "  \n  "]:
            result = service.execute_task("parameter_extraction", text)
            assert result.success is False
            assert "Empty" in result.error

        engine.chat_sync.assert_not_called()

    @pytest.mark.slow
    def test_unknown_task_doesnt_touch_engine(self, tmp_path):
        """Unknown task type returns error without any engine interaction."""
        service = _make_service(tmp_path)
        engine = MagicMock()
        service._engine = engine

        result = service.execute_task("nonexistent", "test")
        assert result.success is False
        assert "Unknown task type" in result.error
        engine.chat_sync.assert_not_called()
        engine.stop_sync.assert_not_called()

    @pytest.mark.slow
    def test_concurrent_different_tasks_produce_correct_results(self, tmp_path):
        """Two threads executing different tasks get correct results."""
        service = _make_service(tmp_path, cache_enabled=False)

        results = {}
        errors = []

        def run_extraction():
            try:
                engine = MagicMock()
                engine.chat_sync.return_value = FakeResponse(
                    content='{"steps": 42}')

                with patch("avatar_engine.AvatarEngine",
                           return_value=engine, create=True):
                    r = service.execute_task(
                        "parameter_extraction", "thread A input")
                results["extraction"] = r
            except Exception as e:
                errors.append(e)

        def run_tagging():
            try:
                engine = MagicMock()
                engine.chat_sync.return_value = FakeResponse(
                    content='{"category": "anime", "tags": ["thread"]}')

                with patch("avatar_engine.AvatarEngine",
                           return_value=engine, create=True):
                    r = service.execute_task(
                        "model_tagging", "thread B input")
                results["tagging"] = r
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=run_extraction)
        t2 = threading.Thread(target=run_tagging)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 2
        # Both should succeed (serialized by lock)
        assert results["extraction"].success is True
        assert results["tagging"].success is True

    @pytest.mark.slow
    def test_engine_start_failure_leaves_clean_state(self, tmp_path):
        """If engine.start_sync() fails, state is clean for next call."""
        service = _make_service(tmp_path, cache_enabled=False)

        # First attempt: engine start fails
        bad_engine = MagicMock()
        bad_engine.start_sync.side_effect = RuntimeError("Cannot start")
        with patch("avatar_engine.AvatarEngine",
                   return_value=bad_engine, create=True):
            r1 = service.execute_task("parameter_extraction", "attempt 1")

        assert r1.success is False
        assert service._engine is None  # Clean state

        # Second attempt: works fine
        good_engine = MagicMock()
        good_engine.chat_sync.return_value = FakeResponse(
            content='{"steps": 20}')
        with patch("avatar_engine.AvatarEngine",
                   return_value=good_engine, create=True):
            r2 = service.execute_task("parameter_extraction", "attempt 2")

        assert r2.success is True
        assert r2.output["steps"] == 20


# =============================================================================
# Workflow 8: Full pipeline → GenerationParameters → persist → reload
# =============================================================================


class TestExtractionToPackPersistence:
    """End-to-end: AvatarTaskService → result.output → GenerationParameters → pack.json.

    This is the MISSING test gap: individual pieces were tested, but never
    the full pipeline from AI response all the way through to pack.json
    serialization and reload.
    """

    @pytest.mark.slow
    def test_realistic_ai_response_to_generation_parameters(self, tmp_path):
        """Realistic AI response (lists, ranges, nested) survives the full pipeline."""
        from src.store.models import GenerationParameters

        service = _make_service(tmp_path)
        engine = _mock_engine_for(service, "parameter_extraction", json.dumps({
            "sampler": ["DPM++ 2M Karras", "Euler a"],
            "steps": {"min": 20, "max": 30, "recommended": 25},
            "cfg_scale": {"min": 7, "max": 9},
            "clip_skip": 2,
            "strength": {"min": 0.6, "max": 0.8},
            "trigger_words": ["anime style", "detailed eyes"],
            "hires_fix": True,
            "hires_scale": 2.0,
        }))

        result = service.extract_parameters(
            "SDXL anime LoRA. Sampler: DPM++ 2M Karras or Euler a, "
            "Steps 20-30 (25 recommended), CFG 7-9, Clip Skip 2, "
            "LoRA weight 0.6-0.8, HiRes Fix 2x"
        )
        assert result.success is True

        # Critical step: pass enriched output to GenerationParameters
        params = GenerationParameters(**result.output)

        # Verify normalization
        assert params.sampler == "DPM++ 2M Karras"  # list → first
        assert params.steps == 25  # range → recommended
        assert params.cfg_scale == 9.0  # range → max (no recommended)
        assert params.clip_skip == 2
        assert params.strength == 0.8  # range → max
        assert params.hires_fix is True
        assert params.hires_scale == 2.0

        # Verify metadata survived
        serialized = params.model_dump()
        assert serialized["_extracted_by"] == "avatar:gemini"
        assert "sampler" in serialized["_ai_fields"]

    @pytest.mark.slow
    def test_extraction_result_persists_in_pack_json(self, tmp_path):
        """Full flow: extract → GenerationParameters → save to disk → reload."""
        from src.store.models import GenerationParameters

        service = _make_service(tmp_path)
        engine = _mock_engine_for(service, "parameter_extraction", json.dumps({
            "steps": 25,
            "cfg_scale": 7.5,
            "sampler": "Euler a",
            "clip_skip": 2,
        }))

        result = service.extract_parameters("CFG 7.5, Steps 25, Euler a, Clip 2")
        assert result.success is True

        # Simulate pack_service.py:552-553
        params = GenerationParameters(**result.output)

        # Save to JSON file (simulate pack.json)
        pack_json = tmp_path / "pack.json"
        import json as json_mod
        pack_json.write_text(json_mod.dumps({
            "parameters": params.model_dump(),
            "parameters_source": result.provider_id,
        }))

        # Reload from disk
        loaded = json_mod.loads(pack_json.read_text())
        reloaded_params = GenerationParameters(**loaded["parameters"])

        assert reloaded_params.steps == 25
        assert reloaded_params.cfg_scale == 7.5
        assert reloaded_params.sampler == "Euler a"
        assert reloaded_params.clip_skip == 2
        assert loaded["parameters_source"] == "avatar:gemini"

    @pytest.mark.slow
    def test_fallback_result_also_works_with_generation_parameters(self, tmp_path):
        """Fallback (rule-based) result also creates valid GenerationParameters."""
        from src.store.models import GenerationParameters

        service = _make_service(tmp_path, cache_enabled=False)
        # No engine configured → will fail AI → trigger fallback
        service._engine = None
        service._current_task_type = None

        with patch("avatar_engine.AvatarEngine", create=True,
                   side_effect=RuntimeError("no engine")):
            result = service.extract_parameters(
                "Recommended: CFG 7, Steps 20, Clip Skip 2, Sampler: Euler"
            )

        # Should succeed via rule-based fallback
        assert result.success is True
        assert result.provider_id == "rule_based"

        params = GenerationParameters(**result.output)
        assert params.cfg_scale == 7.0
        assert params.steps == 20
        assert params.clip_skip == 2
        # Verify _extracted_by from fallback path
        serialized = params.model_dump()
        assert serialized.get("_extracted_by") == "rule_based"

    @pytest.mark.slow
    def test_cached_result_also_works_with_generation_parameters(self, tmp_path):
        """Cached result (second call) also creates valid GenerationParameters."""
        from src.store.models import GenerationParameters

        service = _make_service(tmp_path, cache_enabled=True)
        engine = _mock_engine_for(service, "parameter_extraction",
            '{"steps": 30, "cfg_scale": 8.0, "sampler": "DPM++ SDE"}')

        desc = "Steps 30, CFG 8, DPM++ SDE"

        # First call — AI path
        r1 = service.extract_parameters(desc)
        assert r1.cached is False
        p1 = GenerationParameters(**r1.output)
        assert p1.steps == 30

        # Second call — cache path
        r2 = service.extract_parameters(desc)
        assert r2.cached is True
        p2 = GenerationParameters(**r2.output)

        # Both paths produce identical parameters
        assert p2.steps == p1.steps
        assert p2.cfg_scale == p1.cfg_scale
        assert p2.sampler == p1.sampler
