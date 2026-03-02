"""
Unit tests for AvatarAIService (backward compat wrapper).

Tests that the backward-compatible import from ai_service.py works
and that the core extract_parameters flow functions correctly.
"""

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.avatar.ai_service import AvatarAIService, _extract_json
from src.avatar.config import AvatarConfig, AvatarProviderConfig, ExtractionConfig
from src.avatar.task_service import AvatarTaskService
from src.avatar.tasks.base import TaskResult


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


def _make_service(tmp_path: Optional[Path] = None, **overrides) -> AvatarAIService:
    """Create AvatarAIService with test config."""
    config = _make_config(tmp_path, **overrides)
    return AvatarAIService(config)


# =============================================================================
# TestBackwardCompatImport
# =============================================================================


class TestBackwardCompatImport:
    """Test that backward compat imports work."""

    def test_avatar_ai_service_is_task_service(self):
        """AvatarAIService is AvatarTaskService."""
        assert AvatarAIService is AvatarTaskService

    def test_extract_json_importable(self):
        """_extract_json is importable from ai_service."""
        assert callable(_extract_json)


# =============================================================================
# TestAvatarAIServiceInit
# =============================================================================


class TestAvatarAIServiceInit:
    """Test initialization of AvatarAIService."""

    def test_init_with_default_config(self, tmp_path):
        """Service initializes with given config."""
        config = _make_config(tmp_path)
        service = AvatarAIService(config)
        assert service.config is config
        assert service._engine is None
        assert service.cache is not None

    def test_init_with_custom_provider(self, tmp_path):
        """Service uses custom provider from config."""
        config = _make_config(tmp_path, provider="claude")
        service = AvatarAIService(config)
        assert service._provider == "claude"
        assert service._model == "claude-test"

    def test_engine_is_lazy(self, tmp_path):
        """Engine is not created during init."""
        service = _make_service(tmp_path)
        assert service._engine is None


# =============================================================================
# TestExtractParameters
# =============================================================================


class TestExtractParameters:
    """Test extract_parameters method."""

    def test_happy_path(self, tmp_path):
        """Successful extraction returns TaskResult with parameters."""
        service = _make_service(tmp_path, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "DPM++ 2M", "steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("Use DPM++ 2M sampler with 20 steps")

        assert result.success is True
        assert result.output["sampler"] == "DPM++ 2M"
        assert result.output["steps"] == 20
        assert result.provider_id == "avatar:gemini"
        assert result.cached is False
        mock_engine.chat_sync.assert_called_once()

    def test_cache_hit(self, tmp_path):
        """Second call with same description uses cache."""
        service = _make_service(tmp_path, cache_enabled=True)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "Euler"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        # First call - engine is called
        result1 = service.extract_parameters("Test description")
        assert result1.success is True
        assert result1.cached is False
        assert mock_engine.chat_sync.call_count == 1

        # Second call - cache hit
        result2 = service.extract_parameters("Test description")
        assert result2.success is True
        assert result2.cached is True
        assert mock_engine.chat_sync.call_count == 1  # Not called again

    def test_engine_error_falls_back(self, tmp_path):
        """Engine error triggers rule-based fallback via task.get_fallback()."""
        service = _make_service(tmp_path, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="",
            success=False,
            error="Connection timeout",
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        # The fallback is provided by ParameterExtractionTask.get_fallback()
        # Patch the rule-based provider to avoid importing real extractor
        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=True,
                output={"cfg_scale": 7},
            )
            result = service.extract_parameters("Test")

        assert result.success is True
        assert result.provider_id == "rule_based"

    def test_empty_description(self, tmp_path):
        """Empty description returns failure without calling engine."""
        service = _make_service(tmp_path)
        mock_engine = MagicMock()
        service._engine = mock_engine

        result = service.extract_parameters("")
        assert result.success is False
        assert "Empty" in result.error
        mock_engine.chat_sync.assert_not_called()

        result2 = service.extract_parameters("   ")
        assert result2.success is False
        mock_engine.chat_sync.assert_not_called()


# =============================================================================
# TestExtractedByTracking
# =============================================================================


class TestExtractedByTracking:
    """Test _extracted_by and _ai_fields metadata."""

    def test_extracted_by_avatar_provider(self, tmp_path):
        """Output includes _extracted_by = 'avatar:<provider>'."""
        service = _make_service(tmp_path, provider="gemini", cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("Test")
        assert result.output["_extracted_by"] == "avatar:gemini"

    def test_ai_fields_list(self, tmp_path):
        """Output includes _ai_fields listing non-private keys."""
        service = _make_service(tmp_path, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20, "sampler": "Euler"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("Test")
        assert set(result.output["_ai_fields"]) == {"steps", "sampler"}


# =============================================================================
# TestCacheIntegration
# =============================================================================


class TestCacheIntegration:
    """Test cache behavior with AvatarAIService."""

    def test_cache_miss_then_hit(self, tmp_path):
        """Cache miss on first call, hit on second."""
        service = _make_service(tmp_path, cache_enabled=True)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "Euler a"}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        r1 = service.extract_parameters("desc")
        assert r1.cached is False
        r2 = service.extract_parameters("desc")
        assert r2.cached is True
        assert r2.output["sampler"] == "Euler a"

    def test_cache_disabled(self, tmp_path):
        """When cache is disabled, always calls engine."""
        service = _make_service(tmp_path, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        service.extract_parameters("desc")
        service.extract_parameters("desc")
        assert mock_engine.chat_sync.call_count == 2

    def test_cache_different_descriptions(self, tmp_path):
        """Different descriptions get separate cache entries."""
        service = _make_service(tmp_path, cache_enabled=True)

        mock_engine = MagicMock()
        call_count = 0

        def side_effect(msg):
            nonlocal call_count
            call_count += 1
            return FakeBridgeResponse(
                content=f'{{"result": {call_count}}}',
                success=True,
            )

        mock_engine.chat_sync.side_effect = side_effect
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        r1 = service.extract_parameters("desc A")
        r2 = service.extract_parameters("desc B")
        assert r1.output["result"] == 1
        assert r2.output["result"] == 2

    def test_task_type_prefix_in_cache_key(self, tmp_path):
        """Cache key includes task_type prefix."""
        service = _make_service(tmp_path, cache_enabled=True)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        service.extract_parameters("test desc")

        cache_files = list(Path(str(tmp_path / "cache")).glob("*.json"))
        assert len(cache_files) == 1

        # Cache key includes task_type:provider:model:input
        expected_key = hashlib.sha256(
            "parameter_extraction:gemini:gemini-test:test desc".encode()
        ).hexdigest()[:16]
        assert cache_files[0].stem == expected_key


# =============================================================================
# TestEngineLifecycle
# =============================================================================


class TestEngineLifecycle:
    """Test engine lifecycle management."""

    def test_lazy_init(self, tmp_path):
        """Engine is created only when first needed."""
        service = _make_service(tmp_path)
        assert service._engine is None

    def test_shutdown(self, tmp_path):
        """Shutdown stops and clears engine."""
        service = _make_service(tmp_path)
        mock_engine = MagicMock()
        service._engine = mock_engine

        service.shutdown()

        mock_engine.stop_sync.assert_called_once()
        assert service._engine is None

    def test_reinit_after_shutdown(self, tmp_path):
        """Engine can be re-initialized after shutdown."""
        service = _make_service(tmp_path, cache_enabled=False)

        mock_engine = MagicMock()
        service._engine = mock_engine

        service.shutdown()
        assert service._engine is None

        # Set a new mock engine to simulate re-init
        mock_engine2 = MagicMock()
        mock_engine2.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 10}',
            success=True,
        )
        service._engine = mock_engine2
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("test")
        assert result.success is True


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
        text = 'Here are the parameters:\n{"steps": 20, "cfg": 7}\nHope this helps!'
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
    """Test thread safety of engine initialization."""

    def test_engine_has_lock(self, tmp_path):
        """AvatarAIService has an engine lock for thread safety."""
        service = _make_service(tmp_path)
        assert hasattr(service, "_engine_lock")

    def test_concurrent_calls_no_crash(self, tmp_path):
        """Concurrent calls don't crash."""
        service = _make_service(tmp_path, cache_enabled=False)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        engines = []

        def call():
            r = service.extract_parameters("test")
            engines.append(r)

        threads = [threading.Thread(target=call) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(engines) == 5
        assert all(r.success for r in engines)
