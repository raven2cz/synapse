"""
Integration tests for AvatarTaskService (via AvatarAIService backward compat).

Tests the full extraction flow with mocked BridgeResponse
(not mocking the engine itself -- testing the complete pipeline).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.avatar.ai_service import AvatarAIService
from src.avatar.config import AvatarConfig, AvatarProviderConfig, ExtractionConfig
from src.avatar.task_service import AvatarTaskService
from src.avatar.tasks.base import TaskResult


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


def _make_config(tmp_path: Path, **overrides) -> AvatarConfig:
    """Create config for integration tests."""
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
# TestAvatarExtractFlow
# =============================================================================


class TestAvatarExtractFlow:
    """Test full extraction flow through AvatarAIService."""

    def test_full_extraction_returns_task_result(self, tmp_path):
        """Full extraction pipeline produces valid TaskResult."""
        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarAIService(config)

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
        service._current_task_type = "parameter_extraction"

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
        config = _make_config(tmp_path)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

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
        config = _make_config(tmp_path)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

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
        """When engine fails, rule-based extraction kicks in via task fallback."""
        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.side_effect = RuntimeError("Engine crashed")
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=True,
                output={"steps": 20},
            )
            result = service.extract_parameters("Steps: 20")

        assert result.success is True
        assert result.provider_id == "rule_based"

    def test_engine_and_rule_based_both_fail(self, tmp_path):
        """When both engine and rule-based fail, returns error."""
        config = _make_config(tmp_path, cache_enabled=False)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.side_effect = RuntimeError("Engine crashed")
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock_rb:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock_rb.return_value = RuleBasedResult(
                success=False,
                error="Rule-based also failed",
            )
            result = service.extract_parameters("Nonsense input")

        assert result.success is False


# =============================================================================
# TestAvatarProviderConfig
# =============================================================================


class TestAvatarProviderConfig:
    """Test provider config affects service behavior."""

    def test_provider_in_result(self, tmp_path):
        """Provider name appears in result and tracking."""
        config = _make_config(tmp_path, provider="claude", cache_enabled=False)
        service = AvatarAIService(config)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 30}',
            success=True,
        )
        service._engine = mock_engine
        service._current_task_type = "parameter_extraction"

        result = service.extract_parameters("Test")
        assert result.provider_id == "avatar:claude"
        assert result.output["_extracted_by"] == "avatar:claude"

    def test_different_providers(self, tmp_path):
        """Different provider values are reflected in results."""
        for provider in ["gemini", "claude", "codex"]:
            config = _make_config(
                tmp_path,
                provider=provider,
                cache_enabled=False,
            )
            service = AvatarAIService(config)

            mock_engine = MagicMock()
            mock_engine.chat_sync.return_value = FakeBridgeResponse(
                content='{"test": true}',
                success=True,
            )
            service._engine = mock_engine
            service._current_task_type = "parameter_extraction"

            result = service.extract_parameters("Test")
            assert result.provider_id == f"avatar:{provider}"


# =============================================================================
# TestBackwardCompatibility
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compat: AvatarAIService is AvatarTaskService."""

    def test_import_alias(self):
        """AvatarAIService from ai_service is AvatarTaskService."""
        assert AvatarAIService is AvatarTaskService

    def test_service_has_execute_task(self, tmp_path):
        """Service has execute_task method (new multi-task API)."""
        config = _make_config(tmp_path)
        service = AvatarAIService(config)
        assert hasattr(service, "execute_task")

    def test_service_has_registry(self, tmp_path):
        """Service has registry attribute."""
        config = _make_config(tmp_path)
        service = AvatarAIService(config)
        assert hasattr(service, "registry")
        assert "parameter_extraction" in service.registry.list_tasks()
