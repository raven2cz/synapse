"""
Unit tests for AvatarTaskService.

Tests the multi-task service with fully mocked engine.
No real CLI calls are made.
"""

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.avatar.config import AvatarConfig, AvatarProviderConfig, ExtractionConfig
from src.avatar.task_service import AvatarTaskService, _extract_json
from src.avatar.tasks.base import AITask, TaskResult
from src.avatar.tasks.registry import TaskRegistry


# =============================================================================
# Fake BridgeResponse (mirrors avatar_engine.types.BridgeResponse)
# =============================================================================


@dataclass
class FakeBridgeResponse:
    """Fake BridgeResponse for testing."""

    content: str
    success: bool = True
    error: Optional[str] = None
    duration_ms: int = 0
    cost_usd: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.success


# =============================================================================
# Fake tasks for testing
# =============================================================================


class FakeExtractionTask(AITask):
    task_type = "fake_extraction"
    SKILL_NAMES = ("test-skill",)

    def build_system_prompt(self, skills_content: str) -> str:
        return f"Extract params. {skills_content}"

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw_output, dict):
            return {}
        return {k: v for k, v in raw_output.items() if not k.startswith("_")}

    def validate_output(self, output: Any) -> bool:
        return isinstance(output, dict) and len(output) > 0


class FakeTaskWithFallback(AITask):
    task_type = "with_fallback"
    SKILL_NAMES = ()

    def build_system_prompt(self, skills_content: str) -> str:
        return "Fallback task."

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw_output, dict):
            return {}
        return raw_output

    def validate_output(self, output: Any) -> bool:
        return isinstance(output, dict) and len(output) > 0

    def get_fallback(self) -> Optional[Callable[[str], TaskResult]]:
        def _fallback(input_data: str) -> TaskResult:
            return TaskResult(
                success=True,
                output={"fallback": True, "input": input_data[:20]},
                provider_id="rule_based",
                model="test_fallback",
            )
        return _fallback


class FakeTaskNoFallback(AITask):
    task_type = "no_fallback"
    SKILL_NAMES = ()

    def build_system_prompt(self, skills_content: str) -> str:
        return "No fallback."

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw_output, dict):
            return {}
        return raw_output

    def validate_output(self, output: Any) -> bool:
        return isinstance(output, dict) and len(output) > 0


# =============================================================================
# Helpers
# =============================================================================


def _make_config(tmp_path: Optional[Path] = None, **overrides) -> AvatarConfig:
    """Create test AvatarConfig with sensible defaults."""
    ext_overrides = {}
    config_overrides = {}
    for k, v in overrides.items():
        if k in ("cache_enabled", "cache_ttl_days", "cache_directory",
                  "always_fallback_to_rule_based"):
            ext_overrides[k] = v
        else:
            config_overrides[k] = v

    if tmp_path and "cache_directory" not in ext_overrides:
        ext_overrides["cache_directory"] = str(tmp_path / "cache")

    extraction = ExtractionConfig(**ext_overrides)

    provider = config_overrides.pop("provider", "gemini")
    providers = config_overrides.pop("providers", {
        "gemini": AvatarProviderConfig(model="gemini-test", enabled=True),
        "claude": AvatarProviderConfig(model="claude-test", enabled=True),
        "codex": AvatarProviderConfig(model="", enabled=True),
    })

    return AvatarConfig(
        provider=provider,
        extraction=extraction,
        providers=providers,
        **config_overrides,
    )


def _make_registry(*tasks: AITask) -> TaskRegistry:
    """Create a registry with given tasks."""
    reg = TaskRegistry()
    for t in tasks:
        reg.register(t)
    return reg


def _make_service(
    tmp_path: Optional[Path] = None,
    registry: Optional[TaskRegistry] = None,
    **overrides,
) -> AvatarTaskService:
    """Create AvatarTaskService with test config and registry."""
    config = _make_config(tmp_path, **overrides)
    return AvatarTaskService(config=config, registry=registry)


# =============================================================================
# TestAvatarTaskServiceInit
# =============================================================================


class TestAvatarTaskServiceInit:
    """Test initialization of AvatarTaskService."""

    def test_init_with_config_and_registry(self, tmp_path):
        """Service initializes with given config and registry."""
        reg = _make_registry(FakeExtractionTask())
        config = _make_config(tmp_path)
        service = AvatarTaskService(config=config, registry=reg)
        assert service.config is config
        assert service.registry is reg
        assert service._engine is None
        assert service.cache is not None

    def test_init_with_defaults(self, tmp_path):
        """Service uses default registry when none provided."""
        config = _make_config(tmp_path)
        service = AvatarTaskService(config=config)
        assert "parameter_extraction" in service.registry.list_tasks()

    def test_engine_is_lazy(self, tmp_path):
        """Engine is not created during init."""
        service = _make_service(tmp_path)
        assert service._engine is None
        assert service._current_task_type is None


# =============================================================================
# TestExecuteTask
# =============================================================================


class TestExecuteTask:
    """Test execute_task method."""

    def test_happy_path(self, tmp_path):
        """Successful execution returns TaskResult with output."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "DPM++ 2M", "steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        result = service.execute_task("fake_extraction", "Use DPM++ 2M with 20 steps")

        assert result.success is True
        assert result.output["sampler"] == "DPM++ 2M"
        assert result.output["steps"] == 20
        assert result.provider_id == "avatar:gemini"
        assert result.cached is False
        mock_engine.chat_sync.assert_called_once()

    def test_cache_hit_no_engine_call(self, tmp_path):
        """Cache hit returns cached result without calling engine."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=True)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "Euler"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        # First call
        r1 = service.execute_task("fake_extraction", "Test description")
        assert r1.success is True
        assert r1.cached is False
        assert mock_engine.chat_sync.call_count == 1

        # Second call - cache hit
        r2 = service.execute_task("fake_extraction", "Test description")
        assert r2.success is True
        assert r2.cached is True
        assert mock_engine.chat_sync.call_count == 1

    def test_unknown_task_type(self, tmp_path):
        """Unknown task type returns error result."""
        reg = TaskRegistry()
        service = _make_service(tmp_path, registry=reg)

        result = service.execute_task("nonexistent", "test")
        assert result.success is False
        assert "Unknown task type" in result.error

    def test_empty_input(self, tmp_path):
        """Empty input returns error result."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg)

        result = service.execute_task("fake_extraction", "")
        assert result.success is False
        assert "Empty" in result.error

        result2 = service.execute_task("fake_extraction", "   ")
        assert result2.success is False

    def test_engine_failure_with_fallback(self, tmp_path):
        """Engine failure triggers fallback when available."""
        reg = _make_registry(FakeTaskWithFallback())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="",
            success=False,
            error="Timeout",
        )
        service._engine = mock_engine
        service._current_task_type = "with_fallback"

        result = service.execute_task("with_fallback", "test input")
        assert result.success is True
        assert result.output["fallback"] is True
        assert result.provider_id == "rule_based"

    def test_engine_failure_no_fallback(self, tmp_path):
        """Engine failure without fallback returns error."""
        reg = _make_registry(FakeTaskNoFallback())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="",
            success=False,
            error="Connection timeout",
        )
        service._engine = mock_engine
        service._current_task_type = "no_fallback"

        result = service.execute_task("no_fallback", "test input")
        assert result.success is False
        assert "Connection timeout" in result.error

    def test_json_parse_error_triggers_fallback(self, tmp_path):
        """Invalid JSON triggers fallback."""
        reg = _make_registry(FakeTaskWithFallback())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="This is not JSON at all",
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "with_fallback"

        result = service.execute_task("with_fallback", "test")
        assert result.success is True
        assert result.provider_id == "rule_based"

    def test_validation_failure_triggers_fallback(self, tmp_path):
        """Output validation failure triggers fallback."""
        reg = _make_registry(FakeTaskWithFallback())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        # Empty dict fails validate_output (requires non-empty)
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "with_fallback"

        result = service.execute_task("with_fallback", "test")
        assert result.success is True
        assert result.provider_id == "rule_based"


# =============================================================================
# TestEngineLifecycle
# =============================================================================


class TestEngineLifecycle:
    """Test engine restart / reuse behavior."""

    def test_reuse_on_same_task_type(self, tmp_path):
        """Engine is reused when task type hasn't changed."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        service.execute_task("fake_extraction", "call 1")
        service.execute_task("fake_extraction", "call 2")

        # Engine should not have been stopped/restarted
        mock_engine.stop_sync.assert_not_called()
        assert mock_engine.chat_sync.call_count == 2

    def test_restart_on_task_type_switch(self, tmp_path):
        """Engine is restarted when task type changes."""
        task_a = FakeExtractionTask()
        task_b = FakeTaskNoFallback()
        reg = _make_registry(task_a, task_b)
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"result": 1}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        # Patch AvatarEngine constructor so restart creates a new mock
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"result": 2}',
            success=True,
        )

        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            result = service.execute_task("no_fallback", "switch task")

        # Old engine should have been stopped
        mock_engine.stop_sync.assert_called_once()
        # New engine should have been started
        new_engine.start_sync.assert_called_once()
        assert service._current_task_type == "no_fallback"

    def test_engine_start_failure_cleans_state(self, tmp_path):
        """If engine start fails, state is clean (no partial engine)."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine_instance = MagicMock()
        mock_engine_instance.start_sync.side_effect = RuntimeError("Start failed")

        with patch("avatar_engine.AvatarEngine", return_value=mock_engine_instance, create=True):
            result = service.execute_task("fake_extraction", "test")

        assert result.success is False
        assert service._engine is None
        assert service._current_task_type is None

    def test_shutdown_stops_engine(self, tmp_path):
        """shutdown() stops and clears engine."""
        service = _make_service(tmp_path)
        mock_engine = MagicMock()
        service._engine = mock_engine
        service._current_task_type = "something"

        service.shutdown()

        mock_engine.stop_sync.assert_called_once()
        assert service._engine is None
        assert service._current_task_type is None

    def test_shutdown_no_engine_no_error(self, tmp_path):
        """shutdown() with no engine doesn't raise."""
        service = _make_service(tmp_path)
        service.shutdown()  # Should not raise


# =============================================================================
# TestConvenienceWrappers
# =============================================================================


class TestConvenienceWrappers:
    """Test convenience wrapper methods."""

    def test_extract_parameters_delegates(self, tmp_path):
        """extract_parameters() delegates to execute_task."""
        service = _make_service(tmp_path)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("CFG 7, Steps 20")
        assert result.success is True


# =============================================================================
# TestLoadSkills
# =============================================================================


class TestLoadSkills:
    """Test _load_skills method."""

    def test_load_existing_skill(self, tmp_path):
        """Loads skill content from existing file."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "test-skill.md").write_text("# Test Skill\nContent here.")

        config = _make_config(tmp_path, skills_dir=skills_dir)
        service = AvatarTaskService(config=config)

        content = service._load_skills(("test-skill",))
        assert "Test Skill" in content
        assert "Content here." in content

    def test_load_missing_skill_returns_empty(self, tmp_path):
        """Missing skill file returns empty string with warning."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        config = _make_config(tmp_path, skills_dir=skills_dir)
        service = AvatarTaskService(config=config)

        content = service._load_skills(("nonexistent",))
        assert content == ""

    def test_load_skills_no_dir(self, tmp_path):
        """No skills_dir returns empty string."""
        config = _make_config(tmp_path, skills_dir=None)
        service = AvatarTaskService(config=config)

        content = service._load_skills(("anything",))
        assert content == ""

    def test_load_multiple_skills(self, tmp_path):
        """Multiple skills are joined with separator."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill-a.md").write_text("Skill A content")
        (skills_dir / "skill-b.md").write_text("Skill B content")

        config = _make_config(tmp_path, skills_dir=skills_dir)
        service = AvatarTaskService(config=config)

        content = service._load_skills(("skill-a", "skill-b"))
        assert "Skill A content" in content
        assert "Skill B content" in content
        assert "---" in content  # Separator


# =============================================================================
# TestCacheKeyPrefix
# =============================================================================


class TestCacheKeyPrefix:
    """Test that cache keys include task type prefix."""

    def test_cache_key_includes_task_prefix(self, tmp_path):
        """Cache file key includes task_type prefix."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=True)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        service.execute_task("fake_extraction", "test desc")

        cache_files = list(Path(str(tmp_path / "cache")).glob("*.json"))
        assert len(cache_files) == 1

        # Cache key includes task_type:provider:model:input
        expected_key = hashlib.sha256(
            "fake_extraction:gemini:gemini-test:test desc".encode()
        ).hexdigest()[:16]
        assert cache_files[0].stem == expected_key


# =============================================================================
# TestExtractedByTracking
# =============================================================================


class TestExtractedByTracking:
    """Test _extracted_by and _ai_fields metadata."""

    def test_extracted_by_provider(self, tmp_path):
        """Output includes _extracted_by = 'avatar:<provider>'."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, provider="gemini",
                                cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        result = service.execute_task("fake_extraction", "Test")
        assert result.output["_extracted_by"] == "avatar:gemini"

    def test_ai_fields_list(self, tmp_path):
        """Output includes _ai_fields listing non-private keys."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20, "sampler": "Euler"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        result = service.execute_task("fake_extraction", "Test")
        assert set(result.output["_ai_fields"]) == {"steps", "sampler"}


# =============================================================================
# TestJsonParsing
# =============================================================================


class TestJsonParsing:
    """Test _extract_json standalone function."""

    def test_plain_json(self):
        result = _extract_json('{"steps": 20, "sampler": "Euler"}')
        assert result == {"steps": 20, "sampler": "Euler"}

    def test_markdown_fences(self):
        text = '```json\n{"steps": 20}\n```'
        result = _extract_json(text)
        assert result == {"steps": 20}

    def test_text_around_json(self):
        text = 'Here are the params:\n{"steps": 20, "cfg": 7}\nDone!'
        result = _extract_json(text)
        assert result == {"steps": 20, "cfg": 7}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("This is not JSON at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("")

    def test_nested_json(self):
        text = '{"hires_fix": {"upscaler": "4x", "steps": 10}}'
        result = _extract_json(text)
        assert result["hires_fix"]["steps"] == 10


# =============================================================================
# TestThreadSafety
# =============================================================================


class TestThreadSafety:
    """Test thread safety of engine access."""

    def test_service_has_lock(self, tmp_path):
        """AvatarTaskService has an engine lock."""
        service = _make_service(tmp_path)
        assert hasattr(service, "_engine_lock")

    def test_concurrent_same_task_no_crash(self, tmp_path):
        """Concurrent same-task calls don't crash."""
        reg = _make_registry(FakeExtractionTask())
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        results = []
        errors = []

        def run():
            try:
                r = service.execute_task("fake_extraction", f"thread test")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        assert all(r.success for r in results)

    def test_concurrent_different_tasks_serialized(self, tmp_path):
        """Concurrent calls with different task types are serialized (no crash)."""
        task_a = FakeExtractionTask()
        task_b = FakeTaskNoFallback()
        reg = _make_registry(task_a, task_b)
        service = _make_service(tmp_path, registry=reg, cache_enabled=False)

        # Pre-set engine for task_a
        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"result": 1}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "fake_extraction"

        # Patch AvatarEngine for restarts
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"result": 2}',
            success=True,
        )

        results = []
        errors = []

        def run(task_type):
            try:
                r = service.execute_task(task_type, f"test {task_type}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            threads = [
                threading.Thread(target=run, args=("fake_extraction",)),
                threading.Thread(target=run, args=("no_fallback",)),
                threading.Thread(target=run, args=("fake_extraction",)),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(errors) == 0
        assert len(results) == 3


# =============================================================================
# TestBackwardCompat
# =============================================================================


class TestBackwardCompat:
    """Test backward compatibility aliases."""

    def test_avatar_ai_service_alias(self):
        """AvatarAIService is an alias for AvatarTaskService."""
        from src.avatar.ai_service import AvatarAIService
        assert AvatarAIService is AvatarTaskService

    def test_extract_json_importable_from_ai_service(self):
        """_extract_json is importable from ai_service."""
        from src.avatar.ai_service import _extract_json as fn
        assert fn is _extract_json

    def test_avatar_task_service_importable_from_ai_service(self):
        """AvatarTaskService is importable from ai_service."""
        from src.avatar.ai_service import AvatarTaskService as cls
        assert cls is AvatarTaskService
