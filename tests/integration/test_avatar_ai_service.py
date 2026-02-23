"""
Integration tests for AvatarAIService.

Tests the full extraction flow with mocked BridgeResponse
(not mocking the engine itself — testing the complete pipeline).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.ai.settings import AIServicesSettings
from src.ai.tasks.base import TaskResult
from src.avatar.ai_service import AvatarAIService


# =============================================================================
# Fake BridgeResponse
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


def _make_settings(tmp_path: Path, **overrides) -> AIServicesSettings:
    """Create settings for integration tests."""
    defaults = {
        "enabled": True,
        "use_avatar_engine": True,
        "avatar_engine_provider": "gemini",
        "avatar_engine_model": "gemini-test",
        "avatar_engine_timeout": 30,
        "cache_enabled": True,
        "cache_directory": str(tmp_path / "cache"),
        "cache_ttl_days": 30,
        "always_fallback_to_rule_based": True,
        "show_provider_in_results": True,
    }
    defaults.update(overrides)
    settings = AIServicesSettings()
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


# =============================================================================
# TestAvatarExtractFlow
# =============================================================================


class TestAvatarExtractFlow:
    """Test full extraction flow through AvatarAIService."""

    def test_full_extraction_returns_task_result(self, tmp_path):
        """Full extraction pipeline produces valid TaskResult."""
        settings = _make_settings(tmp_path)
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content=json.dumps({
                "sampler": "DPM++ 2M Karras",
                "steps": {"min": 20, "max": 30},
                "cfg_scale": 7,
                "clip_skip": 2,
            }),
            success=True,
        )
        service._engine = mock_engine

        result = service.extract_parameters(
            "Use DPM++ 2M Karras sampler, 20-30 steps, CFG 7, clip skip 2"
        )

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.output["sampler"] == "DPM++ 2M Karras"
        assert result.output["steps"] == {"min": 20, "max": 30}
        assert result.output["cfg_scale"] == 7
        assert result.output["clip_skip"] == 2
        assert result.provider_id == "avatar:gemini"
        assert result.model == "gemini-test"
        assert result.execution_time_ms >= 0

    def test_cache_persistence(self, tmp_path):
        """Results are persisted to cache files on disk."""
        settings = _make_settings(tmp_path)
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25}',
            success=True,
        )
        service._engine = mock_engine

        service.extract_parameters("Cache test description")

        # Verify cache file exists on disk
        cache_dir = tmp_path / "cache"
        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Verify cache content
        with open(cache_files[0]) as f:
            cached = json.load(f)
        assert cached["provider_id"] == "avatar:gemini"
        assert cached["result"]["steps"] == 25

    def test_reextract_uses_cache(self, tmp_path):
        """Re-extraction of same description uses cache, not engine."""
        settings = _make_settings(tmp_path)
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25}',
            success=True,
        )
        service._engine = mock_engine

        r1 = service.extract_parameters("Same description")
        r2 = service.extract_parameters("Same description")

        assert r1.cached is False
        assert r2.cached is True
        assert r1.output["steps"] == r2.output["steps"]
        assert mock_engine.chat_sync.call_count == 1


# =============================================================================
# TestAvatarFallbackChain
# =============================================================================


class TestAvatarFallbackChain:
    """Test fallback behavior when avatar engine fails."""

    def test_engine_fails_rule_based_succeeds(self, tmp_path):
        """When engine fails, rule-based extraction kicks in."""
        settings = _make_settings(
            tmp_path,
            always_fallback_to_rule_based=True,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.side_effect = RuntimeError("Engine crashed")
        service._engine = mock_engine

        with patch("src.avatar.ai_service.AvatarAIService._execute_rule_based") as mock_rb:
            mock_rb.return_value = TaskResult(
                success=True,
                output={"steps": 20},
                provider_id="rule_based",
                model="regexp",
            )
            result = service.extract_parameters("Steps: 20")

        assert result.success is True
        assert result.provider_id == "rule_based"

    def test_engine_and_rule_based_both_fail(self, tmp_path):
        """When both engine and rule-based fail, returns error."""
        settings = _make_settings(
            tmp_path,
            always_fallback_to_rule_based=True,
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.side_effect = RuntimeError("Engine crashed")
        service._engine = mock_engine

        with patch("src.avatar.ai_service.AvatarAIService._execute_rule_based") as mock_rb:
            mock_rb.return_value = TaskResult(
                success=False,
                error="Rule-based also failed",
            )
            result = service.extract_parameters("Nonsense input")

        assert result.success is False


# =============================================================================
# TestAvatarSettingsIntegration
# =============================================================================


class TestAvatarSettingsIntegration:
    """Test settings affect service behavior."""

    def test_feature_flag_toggle(self, tmp_path):
        """get_ai_service returns correct type based on flag."""
        from src.ai import get_ai_service, AIService

        settings_on = _make_settings(tmp_path, use_avatar_engine=True)
        settings_off = _make_settings(tmp_path, use_avatar_engine=False)

        service_on = get_ai_service(settings_on)
        service_off = get_ai_service(settings_off)

        assert isinstance(service_on, AvatarAIService)
        assert isinstance(service_off, AIService)

    def test_provider_in_result(self, tmp_path):
        """Provider name appears in result and tracking."""
        settings = _make_settings(
            tmp_path,
            avatar_engine_provider="claude",
        )
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 30}',
            success=True,
        )
        service._engine = mock_engine

        result = service.extract_parameters("Test")
        assert result.provider_id == "avatar:claude"
        assert result.output["_extracted_by"] == "avatar:claude"

    def test_different_providers(self, tmp_path):
        """Different avatar_engine_provider values are reflected in results."""
        for provider in ["gemini", "claude", "codex"]:
            settings = _make_settings(
                tmp_path,
                avatar_engine_provider=provider,
                cache_enabled=False,
            )
            service = AvatarAIService(settings)

            mock_engine = MagicMock()
            mock_engine.chat_sync.return_value = FakeBridgeResponse(
                content='{"test": true}',
                success=True,
            )
            service._engine = mock_engine

            result = service.extract_parameters("Test")
            assert result.provider_id == f"avatar:{provider}"
