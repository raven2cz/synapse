"""
Tests for avatar engine API routes.

Covers:
  - GET /status endpoint with various states
  - GET /providers endpoint
  - GET /config endpoint
  - try_mount_avatar_engine graceful degradation
  - Skills counting
"""

from unittest.mock import MagicMock, patch

import pytest

from src.avatar.routes import (
    _get_cached_config,
    avatar_config_endpoint,
    avatar_providers,
    avatar_status,
    invalidate_avatar_cache,
    try_mount_avatar_engine,
    update_avatar_config,
)


@pytest.fixture(autouse=True)
def _clear_avatar_cache():
    """Invalidate avatar route cache before each test."""
    invalidate_avatar_cache()
    yield
    invalidate_avatar_cache()


class TestAvatarStatusEndpoint:
    """GET /status returns correct state based on engine + provider availability."""

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_state_ready(self, mock_config, mock_providers):
        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = [
            {"name": "gemini", "id": "gemini", "installed": True, "available": True, "display_name": "Gemini CLI", "command": "gemini"}
        ]

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.1.0"), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=True):
            result = avatar_status()

        assert result["state"] == "ready"
        assert result["available"] is True
        assert result["engine_installed"] is True
        assert result["active_provider"] == "gemini"

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_state_no_provider(self, mock_config, mock_providers):
        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = [
            {"name": "gemini", "id": "gemini", "installed": False, "available": False, "display_name": "Gemini CLI", "command": "gemini"}
        ]

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.1.0"), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=True):
            result = avatar_status()

        assert result["state"] == "no_provider"
        assert result["available"] is False
        assert result["active_provider"] is None

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_state_incompatible(self, mock_config, mock_providers):
        """Engine installed but version too old → incompatible state."""
        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = [
            {"name": "gemini", "id": "gemini", "installed": True, "available": True, "display_name": "Gemini CLI", "command": "gemini"}
        ]

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.0.1"), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=False):
            result = avatar_status()

        assert result["state"] == "incompatible"
        assert result["available"] is False
        assert result["active_provider"] is None

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_state_no_engine(self, mock_config, mock_providers):
        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = [
            {"name": "claude", "id": "claude", "installed": True, "available": True, "display_name": "Claude Code", "command": "claude"}
        ]

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", None):
            result = avatar_status()

        assert result["state"] == "no_engine"
        assert result["available"] is False
        assert result["engine_version"] is None

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_state_setup_required(self, mock_config, mock_providers):
        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = [
            {"name": "gemini", "id": "gemini", "installed": False, "available": False, "display_name": "Gemini CLI", "command": "gemini"},
            {"name": "claude", "id": "claude", "installed": False, "available": False, "display_name": "Claude Code", "command": "claude"},
        ]

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", None):
            result = avatar_status()

        assert result["state"] == "setup_required"
        assert result["available"] is False

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_state_disabled(self, mock_config, mock_providers):
        mock_config.return_value = _make_config(enabled=False)
        mock_providers.return_value = []

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True):
            result = avatar_status()

        assert result["state"] == "disabled"
        assert result["available"] is False
        assert result["enabled"] is False

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_safety_field_returned(self, mock_config, mock_providers):
        mock_config.return_value = _make_config(safety="ask")
        mock_providers.return_value = []

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
            result = avatar_status()

        assert result["safety"] == "ask"

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_providers_list_in_response(self, mock_config, mock_providers):
        expected_providers = [
            {"name": "gemini", "id": "gemini", "installed": True, "available": True, "display_name": "Gemini CLI", "command": "gemini"},
        ]
        mock_config.return_value = _make_config()
        mock_providers.return_value = expected_providers

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
            result = avatar_status()

        assert result["providers"] == expected_providers


class TestAvatarProvidersEndpoint:
    """GET /providers delegates to detect_available_providers."""

    @patch("src.avatar.routes.detect_available_providers")
    def test_returns_provider_list(self, mock_detect):
        mock_detect.return_value = [
            {"name": "gemini", "id": "gemini", "installed": True, "available": True, "display_name": "Gemini CLI", "command": "gemini"},
        ]
        result = avatar_providers()
        assert len(result) == 1
        assert result[0]["name"] == "gemini"


class TestAvatarConfigEndpoint:
    """GET /config returns non-sensitive configuration."""

    @patch("src.avatar.routes.load_avatar_config")
    def test_returns_config_fields(self, mock_config):
        config = _make_config(provider="claude", safety="unrestricted")
        mock_config.return_value = config
        result = avatar_config_endpoint()

        assert result["enabled"] is True
        assert result["provider"] == "claude"
        assert result["safety"] == "unrestricted"
        assert result["max_history"] == 100
        assert "skills_count" in result

    @patch("src.avatar.routes.load_avatar_config")
    def test_config_path_field(self, mock_config):
        config = _make_config()
        mock_config.return_value = config
        result = avatar_config_endpoint()

        assert "config_path" in result
        assert "has_config_file" in result

    @patch("src.avatar.routes.load_avatar_config")
    def test_provider_configs_included(self, mock_config):
        from src.avatar.config import AvatarProviderConfig
        config = _make_config()
        config.providers = {
            "gemini": AvatarProviderConfig(model="gemini-2.5-pro", enabled=True),
        }
        mock_config.return_value = config
        result = avatar_config_endpoint()

        assert "gemini" in result["provider_configs"]
        assert result["provider_configs"]["gemini"]["model"] == "gemini-2.5-pro"


class TestTryMountAvatarEngine:
    """try_mount_avatar_engine graceful degradation."""

    def test_returns_false_when_engine_not_available(self):
        app = MagicMock()
        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
            result = try_mount_avatar_engine(app)
        assert result is False
        app.mount.assert_not_called()

    def test_returns_false_when_engine_incompatible(self):
        """Mount should be skipped when engine version is incompatible."""
        app = MagicMock()
        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=False):
            result = try_mount_avatar_engine(app)
        assert result is False
        app.mount.assert_not_called()

    def test_returns_false_when_config_disabled(self):
        app = MagicMock()
        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=True), \
             patch("src.avatar.routes.load_avatar_config") as mock_config:
            mock_config.return_value = _make_config(enabled=False)
            result = try_mount_avatar_engine(app)
        assert result is False
        app.mount.assert_not_called()

    def test_returns_false_on_import_error(self):
        app = MagicMock()
        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=True), \
             patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch.dict("sys.modules", {"avatar_engine.web": None}):
            mock_config.return_value = _make_config(enabled=True)
            result = try_mount_avatar_engine(app)
        assert result is False

    def test_mounts_when_available_and_enabled(self):
        app = MagicMock()
        mock_avatar_app = MagicMock()

        mock_web = MagicMock()
        mock_web.create_api_app.return_value = mock_avatar_app

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.check_avatar_engine_compat", return_value=True), \
             patch("src.avatar.routes.load_avatar_config") as mock_config, \
             patch.dict("sys.modules", {"avatar_engine": MagicMock(), "avatar_engine.web": mock_web}), \
             patch("builtins.__import__", side_effect=_make_import_patcher(mock_web)):
            mock_config.return_value = _make_config(enabled=True)
            result = try_mount_avatar_engine(app)

        assert result is True
        app.mount.assert_called_once_with("/api/avatar/engine", mock_avatar_app)


class TestPatchConfigEndpoint:
    """PATCH /config writes to YAML and returns updated config."""

    def test_patch_changes_provider(self, tmp_path):
        """PATCH with {provider: 'claude'} updates YAML and returns new config."""
        import yaml
        yaml_path = tmp_path / "avatar.yaml"
        yaml_path.write_text("provider: gemini\n")

        with patch("src.avatar.routes.load_avatar_config") as mock_config:
            config = _make_config(provider="gemini")
            config.config_path = yaml_path
            mock_config.return_value = config

            result = update_avatar_config({"provider": "claude"})

        raw = yaml.safe_load(yaml_path.read_text())
        assert raw["provider"] == "claude"

    def test_patch_changes_provider_model(self, tmp_path):
        """PATCH with providers dict updates per-provider model in YAML."""
        import yaml
        yaml_path = tmp_path / "avatar.yaml"
        yaml_path.write_text("provider: gemini\ngemini:\n  model: old-model\n")

        with patch("src.avatar.routes.load_avatar_config") as mock_config:
            config = _make_config()
            config.config_path = yaml_path
            mock_config.return_value = config

            update_avatar_config({
                "providers": {"gemini": {"model": "gemini-2.5-flash"}}
            })

        raw = yaml.safe_load(yaml_path.read_text())
        assert raw["gemini"]["model"] == "gemini-2.5-flash"

    def test_patch_toggle_enabled(self, tmp_path):
        """PATCH with {enabled: false} persists to YAML."""
        import yaml
        yaml_path = tmp_path / "avatar.yaml"
        yaml_path.write_text("enabled: true\n")

        with patch("src.avatar.routes.load_avatar_config") as mock_config:
            config = _make_config()
            config.config_path = yaml_path
            mock_config.return_value = config

            update_avatar_config({"enabled": False})

        raw = yaml.safe_load(yaml_path.read_text())
        assert raw["enabled"] is False

    def test_patch_rejects_invalid_provider(self, tmp_path):
        """PATCH with invalid provider name is silently ignored."""
        import yaml
        yaml_path = tmp_path / "avatar.yaml"
        yaml_path.write_text("provider: gemini\n")

        with patch("src.avatar.routes.load_avatar_config") as mock_config:
            config = _make_config()
            config.config_path = yaml_path
            mock_config.return_value = config

            update_avatar_config({"provider": "invalid_provider"})

        raw = yaml.safe_load(yaml_path.read_text())
        assert raw["provider"] == "gemini"  # Unchanged

    def test_patch_creates_provider_section(self, tmp_path):
        """PATCH creates provider section in YAML if it doesn't exist."""
        import yaml
        yaml_path = tmp_path / "avatar.yaml"
        yaml_path.write_text("provider: gemini\n")

        with patch("src.avatar.routes.load_avatar_config") as mock_config:
            config = _make_config()
            config.config_path = yaml_path
            mock_config.return_value = config

            update_avatar_config({
                "providers": {"claude": {"model": "claude-sonnet-4-5", "enabled": True}}
            })

        raw = yaml.safe_load(yaml_path.read_text())
        assert raw["claude"]["model"] == "claude-sonnet-4-5"
        assert raw["claude"]["enabled"] is True


class TestCachedConfigExceptionHandling:
    """_get_cached_config returns safe defaults on failure."""

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_returns_defaults_on_config_load_failure(self, mock_config, mock_providers):
        """Malformed YAML or broken config should not 500 all endpoints."""
        mock_config.side_effect = Exception("YAML parse error")

        config, providers = _get_cached_config()

        # Should return safe defaults, not raise
        assert config.enabled is True  # AvatarConfig default
        assert providers == []

    @patch("src.avatar.routes.load_avatar_config")
    @patch("src.avatar.routes.detect_available_providers")
    def test_returns_defaults_on_provider_detection_failure(self, mock_providers, mock_config):
        """Provider detection crash should not 500 all endpoints."""
        mock_config.return_value = _make_config()
        mock_providers.side_effect = OSError("shutil broken")

        config, providers = _get_cached_config()

        assert config.enabled is True
        assert providers == []


# ── Helpers ──────────────────────────────────────────────────────────

def _make_config(
    enabled: bool = True,
    provider: str = "gemini",
    safety: str = "safe",
) -> "AvatarConfig":
    """Create a minimal AvatarConfig for testing."""
    from pathlib import Path
    from src.avatar.config import AvatarConfig

    return AvatarConfig(
        enabled=enabled,
        provider=provider,
        safety=safety,
        config_path=Path("/tmp/test-avatar.yaml"),
        skills_dir=Path("/tmp/nonexistent-skills"),
        custom_skills_dir=Path("/tmp/nonexistent-custom"),
    )


def _make_import_patcher(mock_web):
    """Create an import side-effect that returns mock_web for avatar_engine.web."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def patched_import(name, *args, **kwargs):
        if name == "avatar_engine.web":
            return mock_web
        return real_import(name, *args, **kwargs)

    return patched_import
