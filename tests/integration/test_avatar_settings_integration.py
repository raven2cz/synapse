"""
Integration tests for avatar settings endpoints (Iterace 4).

Tests the interaction between avatar routes, config loading, and cache
through a real FastAPI TestClient. Only external I/O (filesystem reads
for config) is mocked — route logic, caching, and response serialization
are tested end-to-end.

Covers:
  - GET /avatars via TestClient (builtin + custom, filesystem interaction)
  - GET /config via TestClient (skills integration)
  - GET /skills via TestClient
  - Cache behavior across multiple endpoints
  - Config → providers → status consistency
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.avatar.config import AvatarConfig, AvatarProviderConfig
from src.avatar.routes import avatar_router, invalidate_avatar_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Invalidate avatar route cache before/after each test."""
    invalidate_avatar_cache()
    yield
    invalidate_avatar_cache()


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


def _make_config(
    enabled: bool = True,
    provider: str = "gemini",
    safety: str = "safe",
    avatars_dir: Path | None = None,
    skills_dir: Path | None = None,
    custom_skills_dir: Path | None = None,
) -> AvatarConfig:
    return AvatarConfig(
        enabled=enabled,
        provider=provider,
        safety=safety,
        config_path=Path("/tmp/test-avatar.yaml"),
        skills_dir=skills_dir or Path("/tmp/nonexistent-skills"),
        custom_skills_dir=custom_skills_dir or Path("/tmp/nonexistent-custom"),
        avatars_dir=avatars_dir,
    )


def _make_providers(installed_names: list[str] | None = None):
    """Build provider list with specified names marked as installed."""
    installed = set(installed_names or [])
    all_providers = [
        {"name": "gemini", "display_name": "Gemini CLI", "command": "gemini"},
        {"name": "claude", "display_name": "Claude Code", "command": "claude"},
        {"name": "codex", "display_name": "Codex CLI", "command": "codex"},
    ]
    for p in all_providers:
        p["installed"] = p["name"] in installed
    return all_providers


@pytest.mark.integration
class TestAvatarsEndpointIntegration:
    """GET /avatars through TestClient with real filesystem."""

    def test_avatars_returns_builtin_and_custom(self, client, tmp_path):
        """Full request: builtin avatars + custom from real tmp dir."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        custom_dir = avatars_dir / "my-custom"
        custom_dir.mkdir()
        (custom_dir / "avatar.json").write_text(json.dumps({"name": "My Custom Avatar"}))

        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = _make_config(avatars_dir=avatars_dir)
            mock_providers.return_value = []
            response = client.get("/api/avatar/avatars")

        assert response.status_code == 200
        data = response.json()

        # Builtin: 8 hardcoded avatars
        assert len(data["builtin"]) == 8
        assert all(a["category"] == "builtin" for a in data["builtin"])

        # Custom: 1 from filesystem
        assert len(data["custom"]) == 1
        assert data["custom"][0]["id"] == "my-custom"
        assert data["custom"][0]["name"] == "My Custom Avatar"
        assert data["custom"][0]["category"] == "custom"

    def test_avatars_with_mixed_valid_invalid(self, client, tmp_path):
        """Invalid avatar.json files are skipped, valid ones returned."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        # Valid
        good = avatars_dir / "good"
        good.mkdir()
        (good / "avatar.json").write_text(json.dumps({"name": "Good"}))

        # Invalid JSON
        bad = avatars_dir / "bad"
        bad.mkdir()
        (bad / "avatar.json").write_text("{not valid")

        # No avatar.json
        empty = avatars_dir / "empty"
        empty.mkdir()

        # Non-dict JSON
        arr = avatars_dir / "array"
        arr.mkdir()
        (arr / "avatar.json").write_text(json.dumps([1, 2, 3]))

        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = _make_config(avatars_dir=avatars_dir)
            mock_providers.return_value = []
            response = client.get("/api/avatar/avatars")

        assert response.status_code == 200
        data = response.json()
        assert len(data["custom"]) == 1
        assert data["custom"][0]["id"] == "good"

    def test_avatars_none_dir(self, client):
        """None avatars_dir returns empty custom list."""
        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = _make_config(avatars_dir=None)
            mock_providers.return_value = []
            response = client.get("/api/avatar/avatars")

        assert response.status_code == 200
        data = response.json()
        assert data["custom"] == []
        assert len(data["builtin"]) == 8


@pytest.mark.integration
class TestConfigEndpointIntegration:
    """GET /config through TestClient with skills resolution."""

    def test_config_includes_skills_and_providers(self, client, tmp_path):
        """Config endpoint returns skills count and provider configs."""
        # Create a skill file so list_skills finds it
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "inventory.md").write_text("# Inventory skill\nManage blobs.")

        config = _make_config(skills_dir=skills_dir)
        config.providers = {
            "gemini": AvatarProviderConfig(model="gemini-2.5-pro", enabled=True),
            "claude": AvatarProviderConfig(model="claude-sonnet-4-20250514", enabled=False),
        }

        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = config
            mock_providers.return_value = []
            response = client.get("/api/avatar/config")

        assert response.status_code == 200
        data = response.json()

        # Skills from real directory
        assert data["skills_count"]["builtin"] >= 1
        assert "skills" in data
        assert any(s["name"] == "inventory" for s in data["skills"]["builtin"])

        # Provider configs
        assert "gemini" in data["provider_configs"]
        assert data["provider_configs"]["gemini"]["model"] == "gemini-2.5-pro"
        assert "claude" in data["provider_configs"]
        assert data["provider_configs"]["claude"]["enabled"] is False

    def test_config_with_custom_skills(self, client, tmp_path):
        """Config includes both builtin and custom skills."""
        skills_dir = tmp_path / "builtin-skills"
        skills_dir.mkdir()
        (skills_dir / "workflows.md").write_text("# Workflows")

        custom_dir = tmp_path / "custom-skills"
        custom_dir.mkdir()
        (custom_dir / "my-skill.md").write_text("# My Custom Skill")

        config = _make_config(skills_dir=skills_dir, custom_skills_dir=custom_dir)

        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = config
            mock_providers.return_value = []
            response = client.get("/api/avatar/config")

        data = response.json()
        assert data["skills_count"]["builtin"] >= 1
        assert data["skills_count"]["custom"] >= 1
        assert any(s["name"] == "my-skill" for s in data["skills"]["custom"])


@pytest.mark.integration
class TestSkillsEndpointIntegration:
    """GET /skills through TestClient."""

    def test_skills_returns_categorized_list(self, client, tmp_path):
        """Skills endpoint returns builtin + custom lists."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "parameters.md").write_text("# Parameters\nGeneration params.")
        (skills_dir / "inventory.md").write_text("# Inventory\nBlob management.")

        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "helper.md").write_text("# Helper")

        config = _make_config(skills_dir=skills_dir, custom_skills_dir=custom_dir)

        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_providers:
            mock_config.return_value = config
            mock_providers.return_value = []
            response = client.get("/api/avatar/skills")

        assert response.status_code == 200
        data = response.json()
        assert "builtin" in data
        assert "custom" in data
        assert len(data["builtin"]) == 2
        assert len(data["custom"]) == 1


@pytest.mark.integration
class TestCacheBehaviorIntegration:
    """Cache behavior across multiple endpoints via TestClient."""

    def test_cache_shared_between_endpoints(self, client):
        """Status and providers share the same cache — config loaded once."""
        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_detect:
            mock_config.return_value = _make_config()
            mock_detect.return_value = _make_providers(["gemini"])

            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
                 patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
                resp_status = client.get("/api/avatar/status")
                resp_providers = client.get("/api/avatar/providers")

            # Both should succeed
            assert resp_status.status_code == 200
            assert resp_providers.status_code == 200

            # Config loaded only once (cached)
            mock_config.assert_called_once()
            mock_detect.assert_called_once()

    def test_cache_invalidation_reloads(self, client):
        """After invalidate_avatar_cache, config is reloaded."""
        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_detect:
            mock_config.return_value = _make_config(provider="gemini")
            mock_detect.return_value = _make_providers(["gemini"])

            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
                client.get("/api/avatar/status")

            # Invalidate and change config
            invalidate_avatar_cache()
            mock_config.return_value = _make_config(provider="claude")

            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
                resp = client.get("/api/avatar/config")

            # Should have reloaded — provider changed
            assert resp.json()["provider"] == "claude"
            assert mock_config.call_count == 2


@pytest.mark.integration
class TestStatusProvidersConsistency:
    """Status and providers endpoints return consistent data."""

    def test_status_providers_match(self, client):
        """Provider list in /status matches /providers response."""
        providers = _make_providers(["gemini", "codex"])

        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_detect:
            mock_config.return_value = _make_config()
            mock_detect.return_value = providers

            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
                 patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
                status_resp = client.get("/api/avatar/status")
                providers_resp = client.get("/api/avatar/providers")

        status_data = status_resp.json()
        providers_data = providers_resp.json()

        # Provider list in status should match standalone providers endpoint
        assert status_data["providers"] == providers_data

    def test_active_provider_consistency(self, client):
        """Active provider in /status matches provider in /config."""
        with patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch("src.avatar.routes.detect_available_providers") as mock_detect:
            mock_config.return_value = _make_config(provider="gemini")
            mock_detect.return_value = _make_providers(["gemini"])

            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
                 patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
                status_resp = client.get("/api/avatar/status")
                config_resp = client.get("/api/avatar/config")

        assert status_resp.json()["active_provider"] == "gemini"
        assert config_resp.json()["provider"] == "gemini"
