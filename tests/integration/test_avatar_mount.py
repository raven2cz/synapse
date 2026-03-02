"""
Integration tests for avatar API route mounting.

Verifies that the avatar router can be mounted into a real FastAPI app
and responds correctly, regardless of whether avatar-engine is installed.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.avatar.routes import avatar_router, try_mount_avatar_engine


@pytest.fixture
def app():
    """Create a test FastAPI app with avatar routes mounted."""
    app = FastAPI()
    app.include_router(avatar_router, prefix="/api/avatar")
    return app


@pytest.fixture
def client(app):
    """Test client for the avatar API."""
    return TestClient(app)


class TestAvatarApiMount:
    """Avatar routes can be mounted and respond correctly."""

    def test_status_endpoint_returns_200(self, client):
        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = _make_config()
            mock_providers.return_value = []
            response = client.get("/api/avatar/status")

        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "available" in data
        assert "providers" in data

    def test_providers_endpoint_returns_200(self, client):
        with patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_providers.return_value = [
                {"name": "gemini", "installed": False, "display_name": "Gemini CLI", "command": "gemini"},
            ]
            response = client.get("/api/avatar/providers")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_config_endpoint_returns_200(self, client):
        with patch("src.avatar.routes.load_avatar_config") as mock_config:
            mock_config.return_value = _make_config()
            response = client.get("/api/avatar/config")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "provider" in data
        assert "safety" in data

    def test_status_without_engine(self, client):
        """When avatar-engine is NOT installed, status returns setup_required."""
        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", None), \
             patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = _make_config()
            mock_providers.return_value = [
                {"name": "gemini", "installed": False, "display_name": "Gemini CLI", "command": "gemini"},
                {"name": "claude", "installed": False, "display_name": "Claude Code", "command": "claude"},
                {"name": "codex", "installed": False, "display_name": "Codex CLI", "command": "codex"},
            ]
            response = client.get("/api/avatar/status")

        data = response.json()
        assert data["state"] == "setup_required"
        assert data["available"] is False
        assert data["engine_installed"] is False

    def test_try_mount_graceful_when_no_engine(self, app):
        """try_mount_avatar_engine doesn't crash when avatar-engine is missing."""
        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
            result = try_mount_avatar_engine(app)
        assert result is False


# ── Helpers ──────────────────────────────────────────────────────────

def _make_config():
    from pathlib import Path
    from src.avatar.config import AvatarConfig
    return AvatarConfig(
        config_path=Path("/tmp/test-avatar.yaml"),
        skills_dir=Path("/tmp/nonexistent-skills"),
        custom_skills_dir=Path("/tmp/nonexistent-custom"),
    )
