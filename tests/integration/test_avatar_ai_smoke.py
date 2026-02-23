"""
Smoke tests for AvatarAIService.

Tests full lifecycle with minimal mocking — only HTTP/subprocess is mocked.
Uses real Store, real cache, real settings serialization.
"""

import json
from dataclasses import dataclass
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


def _make_avatar_settings(tmp_path: Path, **overrides) -> AIServicesSettings:
    """Create real settings with avatar engine enabled."""
    settings = AIServicesSettings.get_defaults()
    settings.use_avatar_engine = True
    settings.avatar_engine_provider = "gemini"
    settings.avatar_engine_model = "gemini-test"
    settings.avatar_engine_timeout = 30
    settings.cache_enabled = True
    settings.cache_directory = str(tmp_path / "cache")
    settings.always_fallback_to_rule_based = True
    settings.show_provider_in_results = True
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


# =============================================================================
# TestAvatarImportSmoke
# =============================================================================


class TestAvatarImportSmoke:
    """Smoke tests simulating parameter extraction during import."""

    @pytest.mark.slow
    def test_extract_realistic_parameters(self, tmp_path):
        """Extract parameters from a realistic Civitai model description."""
        settings = _make_avatar_settings(tmp_path)
        service = AvatarAIService(settings)

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
        settings = _make_avatar_settings(tmp_path)
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 25, "sampler": "DPM++ SDE"}',
            success=True,
        )
        service._engine = mock_engine

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
    def test_settings_serialization_roundtrip(self, tmp_path):
        """Settings with avatar fields survive serialization roundtrip."""
        settings = _make_avatar_settings(tmp_path)
        settings.use_avatar_engine = True
        settings.avatar_engine_provider = "claude"
        settings.avatar_engine_model = "claude-sonnet-4-5"
        settings.avatar_engine_timeout = 90

        # Serialize
        data = settings.to_dict()
        assert data["use_avatar_engine"] is True
        assert data["avatar_engine_provider"] == "claude"
        assert data["avatar_engine_model"] == "claude-sonnet-4-5"
        assert data["avatar_engine_timeout"] == 90

        # Deserialize
        loaded = AIServicesSettings.from_dict(data)
        assert loaded.use_avatar_engine is True
        assert loaded.avatar_engine_provider == "claude"
        assert loaded.avatar_engine_model == "claude-sonnet-4-5"
        assert loaded.avatar_engine_timeout == 90

    @pytest.mark.slow
    def test_cache_stats_after_extraction(self, tmp_path):
        """Cache stats reflect actual cached entries."""
        settings = _make_avatar_settings(tmp_path)
        service = AvatarAIService(settings)

        mock_engine = MagicMock()
        mock_engine.chat_sync.return_value = FakeBridgeResponse(
            content='{"steps": 20}',
            success=True,
        )
        service._engine = mock_engine

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
