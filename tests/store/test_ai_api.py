"""
API Tests for AI Service Endpoints

Tests cover:
- GET /api/ai/providers - detect available AI providers
- POST /api/ai/extract - extract parameters from description
- GET /api/ai/cache/stats - get cache statistics
- DELETE /api/ai/cache - clear all cache entries
- POST /api/ai/cache/cleanup - cleanup expired entries
- GET /api/ai/settings - get current settings

Author: Synapse Team
License: MIT
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.store.api import ai_router


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Create test client with AI router.

    Note: ai_router has prefix="/ai", so we mount it at /api
    to get /api/ai/* paths matching production setup.
    """
    app = FastAPI()
    app.include_router(ai_router, prefix="/api")
    return TestClient(app)


# =============================================================================
# Provider Detection Tests
# =============================================================================

class TestDetectProviders:
    """Tests for GET /api/ai/providers endpoint."""

    def test_detect_providers_returns_status(self, client):
        """Should return provider detection results."""
        with patch("src.ai.detect_ai_providers") as mock_detect:
            mock_detect.return_value = {
                "ollama": MagicMock(
                    provider_id="ollama",
                    available=True,
                    running=True,
                    version="0.5.0",
                    models=["qwen2.5:14b"],
                    error=None,
                ),
                "gemini": MagicMock(
                    provider_id="gemini",
                    available=True,
                    running=True,
                    version=None,
                    models=["gemini-3-pro-preview"],
                    error=None,
                ),
                "claude": MagicMock(
                    provider_id="claude",
                    available=False,
                    running=False,
                    version=None,
                    models=[],
                    error="Claude CLI not found",
                ),
            }

            response = client.get("/api/ai/providers")

            assert response.status_code == 200
            data = response.json()

            assert "providers" in data
            assert "available_count" in data
            assert "running_count" in data

            assert data["available_count"] == 2
            assert data["running_count"] == 2

            assert data["providers"]["ollama"]["available"] is True
            assert data["providers"]["ollama"]["running"] is True
            assert data["providers"]["claude"]["available"] is False


# =============================================================================
# Extract Parameters Tests
# =============================================================================

class TestExtractParameters:
    """Tests for POST /api/ai/extract endpoint."""

    def test_extract_parameters_success(self, client):
        """Should extract parameters from description."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service
            mock_service.extract_parameters.return_value = MagicMock(
                success=True,
                output={"cfg_scale": 7, "steps": 25},
                error=None,
                provider_id="ollama",
                model="qwen2.5:14b",
                cached=False,
                execution_time_ms=1500,
            )

            response = client.post(
                "/api/ai/extract",
                json={"description": "CFG 7, Steps 25"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["parameters"]["cfg_scale"] == 7
            assert data["parameters"]["steps"] == 25
            assert data["provider_id"] == "ollama"
            assert data["execution_time_ms"] == 1500

    def test_extract_parameters_failure(self, client):
        """Should return error on extraction failure."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service
            mock_service.extract_parameters.return_value = MagicMock(
                success=False,
                output=None,
                error="All providers failed",
                provider_id=None,
                model=None,
                cached=False,
                execution_time_ms=5000,
            )

            response = client.post(
                "/api/ai/extract",
                json={"description": "No parameters here"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is False
            assert data["error"] == "All providers failed"
            assert data["parameters"] is None

    def test_extract_parameters_with_cache(self, client):
        """Should use cache when specified."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service
            mock_service.extract_parameters.return_value = MagicMock(
                success=True,
                output={"cfg_scale": 7},
                error=None,
                provider_id="gemini",
                model="gemini-3-pro-preview",
                cached=True,
                execution_time_ms=5,
            )

            response = client.post(
                "/api/ai/extract",
                json={"description": "CFG 7", "use_cache": True},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["cached"] is True
            mock_service.extract_parameters.assert_called_once_with(
                description="CFG 7",
                use_cache=True,
            )


# =============================================================================
# Cache Stats Tests
# =============================================================================

class TestCacheStats:
    """Tests for GET /api/ai/cache/stats endpoint."""

    def test_get_cache_stats(self, client):
        """Should return cache statistics."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service
            mock_service.get_cache_stats.return_value = {
                "cache_dir": "/tmp/ai_cache",
                "entry_count": 42,
                "total_size_bytes": 12345,
                "total_size_mb": 0.012,
                "ttl_days": 30,
            }

            response = client.get("/api/ai/cache/stats")

            assert response.status_code == 200
            data = response.json()

            assert data["entry_count"] == 42
            assert data["total_size_bytes"] == 12345
            assert data["ttl_days"] == 30


# =============================================================================
# Clear Cache Tests
# =============================================================================

class TestClearCache:
    """Tests for DELETE /api/ai/cache endpoint."""

    def test_clear_cache(self, client):
        """Should clear all cache entries."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service
            mock_service.clear_cache.return_value = 42

            response = client.delete("/api/ai/cache")

            assert response.status_code == 200
            data = response.json()

            assert data["cleared"] == 42


# =============================================================================
# Cleanup Cache Tests
# =============================================================================

class TestCleanupCache:
    """Tests for POST /api/ai/cache/cleanup endpoint."""

    def test_cleanup_cache(self, client):
        """Should cleanup expired cache entries."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service
            mock_service.cleanup_cache.return_value = 10

            response = client.post("/api/ai/cache/cleanup")

            assert response.status_code == 200
            data = response.json()

            assert data["cleaned"] == 10


# =============================================================================
# Settings Tests
# =============================================================================

class TestGetSettings:
    """Tests for GET /api/ai/settings endpoint."""

    def test_get_ai_settings(self, client):
        """Should return current AI settings."""
        with patch("src.ai.AIServicesSettings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.enabled = True
            mock_settings.cli_timeout_seconds = 60
            mock_settings.max_retries = 2
            mock_settings.retry_delay_seconds = 1
            mock_settings.cache_enabled = True
            mock_settings.cache_ttl_days = 30
            mock_settings.cache_directory = "~/.synapse/store/data/cache/ai"
            mock_settings.always_fallback_to_rule_based = True
            mock_settings.show_provider_in_results = True
            mock_settings.log_requests = True
            mock_settings.log_level = "INFO"
            mock_settings.log_prompts = False
            mock_settings.log_responses = False
            mock_settings.use_avatar_engine = False
            mock_settings.avatar_engine_provider = "gemini"
            mock_settings.avatar_engine_model = ""
            mock_settings.avatar_engine_timeout = 120
            mock_settings.providers = {
                "ollama": MagicMock(to_dict=lambda: {"enabled": True, "model": "qwen2.5:14b"}),
            }
            mock_settings.task_priorities = {
                "parameter_extraction": MagicMock(to_dict=lambda: {"provider_order": ["ollama", "gemini"]}),
            }
            # Mock load() instead of get_defaults() - settings are now persisted
            mock_settings_cls.load.return_value = mock_settings

            response = client.get("/api/ai/settings")

            assert response.status_code == 200
            data = response.json()

            assert data["enabled"] is True
            assert data["cli_timeout_seconds"] == 60
            assert data["max_retries"] == 2
            assert data["cache_enabled"] is True
            assert data["cache_ttl_days"] == 30
            assert data["always_fallback_to_rule_based"] is True
            assert "ollama" in data["providers"]


# =============================================================================
# Integration Tests
# =============================================================================

class TestAIAPIIntegration:
    """Integration tests for AI API flow."""

    def test_full_extraction_flow(self, client):
        """Should handle full extraction flow."""
        with patch("src.ai.get_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_factory.return_value = mock_service

            # First call - no cache
            mock_service.extract_parameters.return_value = MagicMock(
                success=True,
                output={"cfg_scale": 7, "steps": 25},
                error=None,
                provider_id="ollama",
                model="qwen2.5:14b",
                cached=False,
                execution_time_ms=2000,
            )

            response1 = client.post(
                "/api/ai/extract",
                json={"description": "Test description with CFG 7"},
            )

            assert response1.status_code == 200
            assert response1.json()["cached"] is False

            # Second call - cached
            mock_service.extract_parameters.return_value = MagicMock(
                success=True,
                output={"cfg_scale": 7, "steps": 25},
                error=None,
                provider_id="ollama",
                model="qwen2.5:14b",
                cached=True,
                execution_time_ms=5,
            )

            response2 = client.post(
                "/api/ai/extract",
                json={"description": "Test description with CFG 7"},
            )

            assert response2.status_code == 200
            assert response2.json()["cached"] is True
