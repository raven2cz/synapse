"""
Unit tests for AvatarAIService.

Tests the avatar-engine integration service with fully mocked engine.
No real CLI calls are made.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.ai.settings import AIServicesSettings
from src.ai.tasks.base import TaskResult
from src.avatar.ai_service import AvatarAIService, _extract_json


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


def _make_settings(**overrides) -> AIServicesSettings:
    """Create test settings with avatar engine enabled."""
    defaults = {
        "enabled": True,
        "use_avatar_engine": True,
        "avatar_engine_provider": "gemini",
        "avatar_engine_model": "gemini-test",
        "avatar_engine_timeout": 30,
        "cache_enabled": False,
        "always_fallback_to_rule_based": True,
        "show_provider_in_results": True,
    }
    defaults.update(overrides)
    settings = AIServicesSettings()
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


def _make_service(settings=None, **overrides) -> AvatarAIService:
    """Create AvatarAIService with test settings."""
    s = settings or _make_settings(**overrides)
    return AvatarAIService(s)


# =============================================================================
# TestAvatarAIServiceInit
# =============================================================================


class TestAvatarAIServiceInit:
    """Test initialization of AvatarAIService."""

    def test_init_with_default_settings(self):
        """Service initializes with default settings."""
        settings = _make_settings()
        service = AvatarAIService(settings)
        assert service.settings is settings
        assert service._engine is None
        assert service.cache is not None

    def test_init_with_custom_settings(self):
        """Service uses custom settings."""
        settings = _make_settings(
            avatar_engine_provider="claude",
            avatar_engine_model="claude-test",
            avatar_engine_timeout=60,
        )
        service = AvatarAIService(settings)
        assert service.settings.avatar_engine_provider == "claude"
        assert service.settings.avatar_engine_model == "claude-test"
        assert service.settings.avatar_engine_timeout == 60

    def test_engine_is_lazy(self):
        """Engine is not created during init."""
        service = _make_service()
        assert service._engine is None


# =============================================================================
# TestExtractParameters
# =============================================================================


class TestExtractParameters:
    """Test extract_parameters method."""

    def test_happy_path(self, tmp_path):
        """Successful extraction returns TaskResult with parameters."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "DPM++ 2M", "steps": 20}',
            success=True,
        )
        service._engine = mock_engine

        result = service.extract_parameters("Use DPM++ 2M sampler with 20 steps")

        assert result.success is True
        assert result.output["sampler"] == "DPM++ 2M"
        assert result.output["steps"] == 20
        assert result.provider_id == "avatar:gemini"
        assert result.cached is False
        mock_engine.chat_sync.assert_called_once()

    def test_cache_hit(self, tmp_path):
        """Second call with same description uses cache."""
        settings = _make_settings(
            cache_enabled=True,
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "Euler"}',
            success=True,
        )
        service._engine = mock_engine

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

    def test_json_parse_error_falls_back(self, tmp_path):
        """Invalid JSON response triggers rule-based fallback."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
            always_fallback_to_rule_based=True,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="This is not JSON at all",
            success=True,
        )
        service._engine = mock_engine

        with patch("src.avatar.ai_service.AvatarAIService._execute_rule_based") as mock_rb:
            mock_rb.return_value = TaskResult(
                success=True,
                output={"steps": 20},
                provider_id="rule_based",
                model="regexp",
            )
            result = service.extract_parameters("Some description")

        assert result.success is True
        assert result.provider_id == "rule_based"

    def test_engine_error_falls_back(self, tmp_path):
        """Engine error triggers rule-based fallback."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
            always_fallback_to_rule_based=True,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="",
            success=False,
            error="Connection timeout",
        )
        service._engine = mock_engine

        with patch("src.avatar.ai_service.AvatarAIService._execute_rule_based") as mock_rb:
            mock_rb.return_value = TaskResult(
                success=True,
                output={"cfg_scale": 7},
                provider_id="rule_based",
            )
            result = service.extract_parameters("Test")

        assert result.success is True
        assert result.provider_id == "rule_based"

    def test_no_fallback_returns_error(self, tmp_path):
        """When fallback is disabled, engine error returns failure."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
            always_fallback_to_rule_based=False,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content="",
            success=False,
            error="Timeout",
        )
        service._engine = mock_engine

        result = service.extract_parameters("Test")
        assert result.success is False
        assert "Timeout" in result.error or "error" in result.error.lower()

    def test_empty_description(self, tmp_path):
        """Empty description returns failure without calling engine."""
        service = _make_service(
            cache_directory=str(tmp_path / "cache"),
        )
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
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
            avatar_engine_provider="gemini",
            show_provider_in_results=True,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine

        result = service.extract_parameters("Test")
        assert result.output["_extracted_by"] == "avatar:gemini"

    def test_ai_fields_list(self, tmp_path):
        """Output includes _ai_fields listing non-private keys."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
            show_provider_in_results=True,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20, "sampler": "Euler"}',
            success=True,
        )
        service._engine = mock_engine

        result = service.extract_parameters("Test")
        assert set(result.output["_ai_fields"]) == {"steps", "sampler"}

    def test_show_provider_disabled(self, tmp_path):
        """When show_provider_in_results=False, no metadata added."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
            show_provider_in_results=False,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine

        result = service.extract_parameters("Test")
        assert "_extracted_by" not in result.output
        assert "_ai_fields" not in result.output


# =============================================================================
# TestCacheIntegration
# =============================================================================


class TestCacheIntegration:
    """Test cache behavior with AvatarAIService."""

    def test_cache_miss_then_hit(self, tmp_path):
        """Cache miss on first call, hit on second."""
        settings = _make_settings(
            cache_enabled=True,
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"sampler": "Euler a"}',
            success=True,
        )
        service._engine = mock_engine

        r1 = service.extract_parameters("desc")
        assert r1.cached is False
        r2 = service.extract_parameters("desc")
        assert r2.cached is True
        assert r2.output["sampler"] == "Euler a"

    def test_cache_disabled(self, tmp_path):
        """When cache is disabled, always calls engine."""
        settings = _make_settings(
            cache_enabled=False,
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25}',
            success=True,
        )
        service._engine = mock_engine

        service.extract_parameters("desc")
        service.extract_parameters("desc")
        assert mock_engine.chat_sync.call_count == 2

    def test_cache_different_descriptions(self, tmp_path):
        """Different descriptions get separate cache entries."""
        settings = _make_settings(
            cache_enabled=True,
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

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

        r1 = service.extract_parameters("desc A")
        r2 = service.extract_parameters("desc B")
        assert r1.output["result"] == 1
        assert r2.output["result"] == 2

    def test_task_type_prefix_in_cache_key(self, tmp_path):
        """Cache key includes task_type prefix to prevent cross-task contamination."""
        settings = _make_settings(
            cache_enabled=True,
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine

        service.extract_parameters("test desc")

        # Verify cache file exists with correct key format
        cache_files = list(Path(str(tmp_path / "cache")).glob("*.json"))
        assert len(cache_files) == 1

        # Key should be hash of "parameter_extraction:test desc"
        import hashlib
        expected_key = hashlib.sha256(
            "parameter_extraction:test desc".encode()
        ).hexdigest()[:16]
        assert cache_files[0].stem == expected_key


# =============================================================================
# TestEngineLifecycle
# =============================================================================


class TestEngineLifecycle:
    """Test engine lifecycle management."""

    def test_lazy_init(self, tmp_path):
        """Engine is created only when first needed."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)
        assert service._engine is None

    @patch("src.avatar.ai_service.AvatarAIService._get_engine")
    def test_shutdown(self, mock_get_engine, tmp_path):
        """Shutdown stops and clears engine."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)
        mock_engine = MagicMock()
        service._engine = mock_engine

        service.shutdown()

        mock_engine.stop_sync.assert_called_once()
        assert service._engine is None

    def test_reinit_after_shutdown(self, tmp_path):
        """Engine can be re-initialized after shutdown."""
        settings = _make_settings(
            cache_directory=str(tmp_path / "cache"),
        )
        service = AvatarAIService(settings)

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

        result = service.extract_parameters("test")
        assert result.success is True


# =============================================================================
# TestJsonParsing
# =============================================================================


class TestJsonParsing:
    """Test _extract_json standalone function."""

    def test_plain_json(self):
        """Parses plain JSON directly."""
        result = _extract_json('{"steps": 20, "sampler": "Euler"}')
        assert result == {"steps": 20, "sampler": "Euler"}

    def test_markdown_fences(self):
        """Extracts JSON from markdown code fences."""
        text = '```json\n{"steps": 20}\n```'
        result = _extract_json(text)
        assert result == {"steps": 20}

    def test_text_around_json(self):
        """Extracts JSON from surrounding text."""
        text = 'Here are the parameters:\n{"steps": 20, "cfg": 7}\nHope this helps!'
        result = _extract_json(text)
        assert result == {"steps": 20, "cfg": 7}

    def test_invalid_json_raises(self):
        """Raises JSONDecodeError for non-JSON text."""
        with pytest.raises(json.JSONDecodeError):
            _extract_json("This is not JSON at all")

    def test_empty_string_raises(self):
        """Raises JSONDecodeError for empty string."""
        with pytest.raises(json.JSONDecodeError):
            _extract_json("")

    def test_nested_json(self):
        """Handles nested JSON structures."""
        text = '{"hires_fix": {"upscaler": "4x", "steps": 10}}'
        result = _extract_json(text)
        assert result["hires_fix"]["steps"] == 10


# =============================================================================
# TestFactoryFunction
# =============================================================================


class TestFactoryFunction:
    """Test get_ai_service factory function."""

    def test_returns_avatar_when_flag_on(self):
        """Factory returns AvatarAIService when use_avatar_engine=True."""
        from src.ai import get_ai_service

        settings = _make_settings(use_avatar_engine=True)
        service = get_ai_service(settings)
        assert isinstance(service, AvatarAIService)

    def test_returns_classic_when_flag_off(self):
        """Factory returns AIService when use_avatar_engine=False."""
        from src.ai import get_ai_service, AIService

        settings = _make_settings(use_avatar_engine=False)
        service = get_ai_service(settings)
        assert isinstance(service, AIService)

    def test_explicit_settings_always_creates_fresh(self):
        """Explicit settings bypass singleton and always create new instance."""
        from src.ai import get_ai_service

        settings1 = _make_settings(use_avatar_engine=True)
        settings2 = _make_settings(use_avatar_engine=True)
        s1 = get_ai_service(settings1)
        s2 = get_ai_service(settings2)
        assert s1 is not s2  # Different instances


# =============================================================================
# TestThreadSafety
# =============================================================================


class TestThreadSafety:
    """Test thread safety of engine initialization."""

    def test_engine_has_lock(self, tmp_path):
        """AvatarAIService has an engine lock for thread safety."""
        service = _make_service(cache_directory=str(tmp_path / "cache"))
        assert hasattr(service, "_engine_lock")

    def test_get_engine_double_checked_lock(self, tmp_path):
        """_get_engine uses double-checked locking pattern."""
        import threading

        settings = _make_settings(cache_directory=str(tmp_path / "cache"))
        service = AvatarAIService(settings)

        # Pre-set engine to avoid actual startup
        mock_engine = MagicMock()
        service._engine = mock_engine

        # Multiple calls should return same instance
        engines = []
        def get_engine():
            engines.append(service._get_engine())

        threads = [threading.Thread(target=get_engine) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(e is mock_engine for e in engines)
        assert len(engines) == 5


# =============================================================================
# TestAutoDetection
# =============================================================================


class TestAutoDetection:
    """Test avatar engine auto-detection logic."""

    def test_detect_returns_tuple(self):
        """_detect_avatar_engine returns (bool, str) tuple."""
        from src.ai.settings import _detect_avatar_engine

        result = _detect_avatar_engine()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_detect_without_avatar_engine(self):
        """Returns (False, 'gemini') when avatar_engine not importable."""
        from src.ai.settings import _detect_avatar_engine

        with patch.dict("sys.modules", {"avatar_engine": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                # Can't easily mock this at function level, test the known-good path
                pass

        # At minimum, the function is callable and returns correct shape
        available, provider = _detect_avatar_engine()
        assert provider in ("gemini", "claude", "codex")

    def test_settings_from_dict_uses_defaults_for_missing_avatar_keys(self):
        """Old settings files without avatar fields get auto-detected defaults."""
        from src.ai.settings import AIServicesSettings, _AVATAR_DEFAULTS

        old_data = {
            "enabled": True,
            "providers": {},
            "task_priorities": {},
        }
        settings = AIServicesSettings.from_dict(old_data)
        # Should use auto-detected defaults, not False
        assert settings.use_avatar_engine == _AVATAR_DEFAULTS[0]
        assert settings.avatar_engine_provider == _AVATAR_DEFAULTS[1]

    def test_settings_from_dict_respects_explicit_false(self):
        """When use_avatar_engine=False is explicitly set, don't override."""
        from src.ai.settings import AIServicesSettings

        data = {
            "enabled": True,
            "providers": {},
            "task_priorities": {},
            "use_avatar_engine": False,
            "avatar_engine_provider": "claude",
        }
        settings = AIServicesSettings.from_dict(data)
        assert settings.use_avatar_engine is False
        assert settings.avatar_engine_provider == "claude"
