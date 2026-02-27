"""
Smoke tests for AvatarTaskService (via AvatarAIService backward compat).

Tests full lifecycle with minimal mocking — only HTTP/subprocess is mocked.
Uses real Store, real cache, real config serialization.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.avatar.ai_service import AvatarAIService
from src.avatar.config import AvatarConfig, AvatarProviderConfig, ExtractionConfig
from src.avatar.task_service import AvatarTaskService
from src.avatar.tasks.base import AITask, TaskResult
from src.avatar.tasks.registry import TaskRegistry


# =============================================================================
# Fake BridgeResponse
# =============================================================================


@dataclass
class FakeBridgeResponse:
    """Fake BridgeResponse for smoke tests."""

    content: str
    success: bool = True
    error: Optional[str] = None
    duration_ms: int = 0
    cost_usd: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.success


# =============================================================================
# Helpers
# =============================================================================


def _make_config(tmp_path: Path, **overrides) -> AvatarConfig:
    """Create config for smoke tests."""
    ext_overrides = {}
    config_overrides = {}
    for k, v in overrides.items():
        if k in ("cache_enabled", "cache_ttl_days", "cache_directory",
                  "always_fallback_to_rule_based"):
            ext_overrides[k] = v
        else:
            config_overrides[k] = v

    ext_overrides.setdefault("cache_directory", str(tmp_path / "cache"))
    ext_overrides.setdefault("cache_enabled", True)
    ext_overrides.setdefault("always_fallback_to_rule_based", True)
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


# =============================================================================
# TestAvatarImportSmoke
# =============================================================================


class TestAvatarImportSmoke:
    """Smoke tests simulating parameter extraction during import."""

    @pytest.mark.slow
    def test_extract_realistic_parameters(self, tmp_path):
        """Extract parameters from a realistic Civitai model description."""
        config = _make_config(tmp_path)
        service = AvatarAIService(config)

        # Realistic Civitai model description
        description = """
        <p>This is a SDXL LoRA trained on anime style artwork.</p>
        <p><strong>Recommended settings:</strong></p>
        <ul>
            <li>Sampler: DPM++ 2M Karras or Euler a</li>
            <li>Steps: 20-30</li>
            <li>CFG Scale: 7-9</li>
            <li>Clip Skip: 2</li>
            <li>LoRA Weight: 0.6-0.8</li>
        </ul>
        <p>Trigger words: anime style, detailed eyes</p>
        <p>Works best with animagine-xl-3.1 as base model.</p>
        """

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content=json.dumps({
                "base_model": "SDXL",
                "sampler": ["DPM++ 2M Karras", "Euler a"],
                "steps": {"min": 20, "max": 30},
                "cfg_scale": {"min": 7, "max": 9},
                "clip_skip": 2,
                "lora_weight": {"min": 0.6, "max": 0.8},
                "trigger_words": ["anime style", "detailed eyes"],
                "recommended_base": "animagine-xl-3.1",
            }),
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters(description)

        assert result.success is True
        assert result.provider_id == "avatar:gemini"
        assert "sampler" in result.output
        assert "steps" in result.output
        assert "trigger_words" in result.output
        assert result.output["clip_skip"] == 2
        # Verify _extracted_by tracking
        assert result.output["_extracted_by"] == "avatar:gemini"

    @pytest.mark.slow
    def test_extract_then_verify_cache(self, tmp_path):
        """Full flow: extract, verify cache on disk, re-extract from cache."""
        config = _make_config(tmp_path)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25, "sampler": "DPM++ SDE"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        # Extract
        r1 = service.extract_parameters("Use 25 steps with DPM++ SDE")
        assert r1.success is True
        assert r1.cached is False

        # Verify cache file on disk
        cache_dir = tmp_path / "cache"
        assert cache_dir.exists()
        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Re-extract (should use cache)
        r2 = service.extract_parameters("Use 25 steps with DPM++ SDE")
        assert r2.success is True
        assert r2.cached is True
        assert r2.output["steps"] == 25
        assert r2.output["sampler"] == "DPM++ SDE"

        # Verify engine was only called once
        assert mock_engine.chat_sync.call_count == 1


# =============================================================================
# TestAvatarAPISmoke
# =============================================================================


class TestAvatarAPISmoke:
    """Smoke tests for API-level integration."""

    @pytest.mark.slow
    def test_config_provider_reflected_in_extraction(self, tmp_path):
        """Provider from AvatarConfig is used in extraction results."""
        config = _make_config(tmp_path, provider="claude")
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("Test")
        assert result.provider_id == "avatar:claude"
        assert result.model == "claude-test"

    @pytest.mark.slow
    def test_cache_stats_after_extraction(self, tmp_path):
        """Cache stats reflect actual cached entries."""
        config = _make_config(tmp_path)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        # Stats before
        stats_before = service.get_cache_stats()
        assert stats_before["entry_count"] == 0

        # Extract
        service.extract_parameters("Test description for stats")

        # Stats after
        stats_after = service.get_cache_stats()
        assert stats_after["entry_count"] == 1
        assert stats_after["total_size_bytes"] > 0

        # Clear cache
        cleared = service.clear_cache()
        assert cleared == 1

        stats_final = service.get_cache_stats()
        assert stats_final["entry_count"] == 0


# =============================================================================
# Fake task for multi-task smoke tests
# =============================================================================


class FakeSummaryTask(AITask):
    """Fake task type to test multi-task switching."""
    task_type = "summary"
    SKILL_NAMES = ()

    def build_system_prompt(self, skills_content: str) -> str:
        return "Summarize the input."

    def parse_result(self, raw_output):
        if not isinstance(raw_output, dict):
            return {}
        return raw_output

    def validate_output(self, output):
        return isinstance(output, dict) and len(output) > 0

    def get_fallback(self) -> Optional[Callable[[str], TaskResult]]:
        def _fb(input_data: str) -> TaskResult:
            return TaskResult(
                success=True,
                output={"summary": input_data[:50]},
                provider_id="rule_based",
                model="truncate",
            )
        return _fb


# =============================================================================
# TestMultiTaskSmoke
# =============================================================================


class TestMultiTaskSmoke:
    """Smoke tests for multi-task execute_task() flow."""

    @pytest.mark.slow
    def test_execute_task_happy_path(self, tmp_path):
        """execute_task() with registered task returns TaskResult."""
        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarTaskService(config=config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25, "sampler": "DPM++ 2M"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.execute_task("parameter_extraction", "Steps 25, DPM++ 2M")
        assert result.success is True
        assert result.output["steps"] == 25
        assert result.output["sampler"] == "DPM++ 2M"

    @pytest.mark.slow
    def test_task_type_switch_restarts_engine(self, tmp_path):
        """Switching task type stops old engine and starts new one."""
        reg = TaskRegistry()
        from src.avatar.tasks.parameter_extraction import ParameterExtractionTask
        reg.register(ParameterExtractionTask())
        reg.register(FakeSummaryTask())

        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarTaskService(config=config, registry=reg)

        # Pre-set engine for parameter_extraction
        old_engine = MagicMock()
        old_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = old_engine
        service._current_task_type = "parameter_extraction"

        # Execute parameter_extraction (reuses engine)
        r1 = service.execute_task("parameter_extraction", "Steps 20")
        assert r1.success is True
        old_engine.stop_sync.assert_not_called()

        # Switch to summary task — need to mock AvatarEngine constructor
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"summary": "test"}',
            success=True,
        )

        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            r2 = service.execute_task("summary", "Some long text to summarize")

        # Old engine should have been stopped
        old_engine.stop_sync.assert_called_once()
        # New engine started
        new_engine.start_sync.assert_called_once()
        assert r2.success is True
        assert service._current_task_type == "summary"

    @pytest.mark.slow
    def test_cache_isolation_between_task_types(self, tmp_path):
        """Same input for different task types gets separate cache entries."""
        reg = TaskRegistry()
        from src.avatar.tasks.parameter_extraction import ParameterExtractionTask
        reg.register(ParameterExtractionTask())
        reg.register(FakeSummaryTask())

        config = _make_config(tmp_path, cache_enabled=True)
        service = AvatarTaskService(config=config, registry=reg)

        mock_engine = MagicMock()
        call_count = 0

        def side_effect(msg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeBridgeResponse(content='{"steps": 20}', success=True)
            return FakeBridgeResponse(content='{"summary": "hi"}', success=True)

        mock_engine.chat_sync.side_effect = side_effect
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        # Same input, different task types
        r1 = service.execute_task("parameter_extraction", "test input")
        assert r1.success is True
        assert r1.output.get("steps") == 20

        # Switch to summary task (mock engine restart)
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"summary": "hi"}', success=True,
        )
        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            r2 = service.execute_task("summary", "test input")
        assert r2.success is True
        assert r2.output.get("summary") == "hi"

        # Both should be cached independently
        cache_dir = tmp_path / "cache"
        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 2

    @pytest.mark.slow
    def test_fallback_chain_full_lifecycle(self, tmp_path):
        """AI fails → fallback succeeds → correct result."""
        reg = TaskRegistry()
        reg.register(FakeSummaryTask())

        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarTaskService(config=config, registry=reg)

        # Engine fails
        mock_engine = MagicMock()
        mock_engine.chat_sync.side_effect = RuntimeError("Provider down")
        service._engine = mock_engine
        service._current_task_type = "summary"

        result = service.execute_task("summary", "Some text to summarize")

        assert result.success is True
        assert result.provider_id == "rule_based"
        assert result.model == "truncate"
        assert "Some text" in result.output["summary"]

    @pytest.mark.slow
    def test_unknown_task_type_returns_error(self, tmp_path):
        """Unknown task type returns error without engine interaction."""
        config = _make_config(tmp_path)
        service = AvatarTaskService(config=config)

        mock_engine = MagicMock()
        service._engine = mock_engine

        result = service.execute_task("nonexistent_task", "test")
        assert result.success is False
        assert "Unknown task type" in result.error
        mock_engine.chat_sync.assert_not_called()

    @pytest.mark.slow
    def test_shutdown_and_reinit_lifecycle(self, tmp_path):
        """Shutdown + re-execute works correctly."""
        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarTaskService(config=config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 10}', success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        # Execute
        r1 = service.execute_task("parameter_extraction", "Steps 10")
        assert r1.success is True

        # Shutdown
        service.shutdown()
        assert service._engine is None
        assert service._current_task_type is None

        # Re-execute (needs new engine)
        new_engine = MagicMock()
        new_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}', success=True,
        )
        with patch("avatar_engine.AvatarEngine", return_value=new_engine, create=True):
            r2 = service.execute_task("parameter_extraction", "Steps 20")
        assert r2.success is True
        assert r2.output["steps"] == 20
