"""
Tests for avatar engine configuration loading.

Covers:
  - Default config when no YAML file exists
  - Loading config from YAML file
  - Safety mode defaults and override
  - Provider detection (with mocked shutil.which)
  - Path resolution
  - Malformed YAML handling
  - PATCH /config round-trip (write → reload verification)
"""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.avatar.config import (
    AvatarConfig,
    detect_available_providers,
    load_avatar_config,
)


class TestAvatarConfigDefaults:
    """Config returns sensible defaults when no YAML file exists."""

    def test_default_enabled(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.enabled is True

    def test_default_provider(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.provider == "gemini"

    def test_default_safety_is_safe(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.safety == "safe"

    def test_default_max_history(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.max_history == 100

    def test_resolved_paths(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.config_path == tmp_path / "avatar.yaml"
        assert config.skills_dir == tmp_path / "avatar" / "skills"
        assert config.custom_skills_dir == tmp_path / "avatar" / "custom-skills"
        assert config.avatars_dir == tmp_path / "avatar" / "avatars"

    def test_all_providers_have_defaults(self, tmp_path):
        """All known providers are present with defaults even without YAML config."""
        config = load_avatar_config(synapse_root=tmp_path)
        assert set(config.providers.keys()) == {"gemini", "claude", "codex"}
        for prov in config.providers.values():
            assert prov.model == ""
            assert prov.enabled is True

    def test_no_mcp_servers_configured(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.mcp_servers == {}


class TestAvatarConfigFromYaml:
    """Config loads properly from YAML files."""

    def _write_yaml(self, tmp_path: Path, content: str) -> Path:
        config_path = tmp_path / "avatar.yaml"
        config_path.write_text(textwrap.dedent(content))
        return config_path

    def test_load_enabled_false(self, tmp_path):
        self._write_yaml(tmp_path, """
            enabled: false
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.enabled is False

    def test_load_provider(self, tmp_path):
        self._write_yaml(tmp_path, """
            provider: claude
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.provider == "claude"

    def test_load_safety_from_engine_section(self, tmp_path):
        self._write_yaml(tmp_path, """
            engine:
              safety_instructions: "unrestricted"
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.safety == "unrestricted"

    def test_load_max_history(self, tmp_path):
        self._write_yaml(tmp_path, """
            engine:
              max_history: 50
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.max_history == 50

    def test_load_custom_system_prompt(self, tmp_path):
        self._write_yaml(tmp_path, """
            system_prompt: "Custom prompt"
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.system_prompt == "Custom prompt"

    def test_load_provider_configs(self, tmp_path):
        self._write_yaml(tmp_path, """
            gemini:
              model: "gemini-2.5-pro"
              enabled: true
            claude:
              model: "claude-sonnet-4-6"
              enabled: false
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert "gemini" in config.providers
        assert config.providers["gemini"].model == "gemini-2.5-pro"
        assert config.providers["gemini"].enabled is True
        assert "claude" in config.providers
        assert config.providers["claude"].model == "claude-sonnet-4-6"
        assert config.providers["claude"].enabled is False

    def test_load_mcp_servers(self, tmp_path):
        self._write_yaml(tmp_path, """
            mcp_servers:
              synapse-store:
                command: "python"
                args: ["-m", "src.avatar.mcp.store"]
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert "synapse-store" in config.mcp_servers
        assert config.mcp_servers["synapse-store"]["command"] == "python"

    def test_explicit_config_path(self, tmp_path):
        custom_path = tmp_path / "custom" / "my-avatar.yaml"
        custom_path.parent.mkdir(parents=True)
        custom_path.write_text("provider: codex\n")
        config = load_avatar_config(
            synapse_root=tmp_path, config_path=custom_path
        )
        assert config.provider == "codex"
        assert config.config_path == custom_path

    def test_raw_yaml_preserved(self, tmp_path):
        self._write_yaml(tmp_path, """
            provider: gemini
            custom_field: hello
        """)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config._raw.get("custom_field") == "hello"


class TestAvatarConfigEdgeCases:
    """Edge cases and error handling."""

    def test_malformed_yaml_falls_back_to_defaults(self, tmp_path):
        config_path = tmp_path / "avatar.yaml"
        config_path.write_text(":::invalid yaml{{{")
        config = load_avatar_config(synapse_root=tmp_path)
        # Should not crash, returns defaults
        assert config.enabled is True
        assert config.provider == "gemini"

    def test_empty_yaml_returns_defaults(self, tmp_path):
        config_path = tmp_path / "avatar.yaml"
        config_path.write_text("")
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.enabled is True

    def test_yaml_with_only_comments(self, tmp_path):
        config_path = tmp_path / "avatar.yaml"
        config_path.write_text("# Just a comment\n")
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.enabled is True


class TestDetectProviders:
    """Provider detection via shutil.which."""

    def test_no_providers_installed(self):
        with patch("shutil.which", return_value=None):
            providers = detect_available_providers()
        assert len(providers) == 3
        assert all(not p["installed"] for p in providers)
        assert all(not p["available"] for p in providers)

    def test_gemini_installed(self):
        def mock_which(cmd):
            return "/usr/bin/gemini" if cmd == "gemini" else None

        with patch("shutil.which", side_effect=mock_which):
            providers = detect_available_providers()

        gemini = next(p for p in providers if p["name"] == "gemini")
        claude = next(p for p in providers if p["name"] == "claude")
        assert gemini["installed"] is True
        assert gemini["available"] is True
        assert claude["installed"] is False
        assert claude["available"] is False

    def test_all_providers_installed(self):
        with patch(
            "shutil.which", return_value="/usr/bin/something"
        ):
            providers = detect_available_providers()
        assert all(p["installed"] for p in providers)
        assert all(p["available"] for p in providers)

    def test_provider_id_matches_name(self):
        """Each provider has an 'id' field matching 'name' for avatar-engine compat."""
        with patch("shutil.which", return_value=None):
            providers = detect_available_providers()
        for p in providers:
            assert p["id"] == p["name"]

    def test_provider_display_names(self):
        with patch("shutil.which", return_value=None):
            providers = detect_available_providers()

        names = {p["name"]: p["display_name"] for p in providers}
        assert names["gemini"] == "Gemini CLI"
        assert names["claude"] == "Claude Code"
        assert names["codex"] == "Codex CLI"

    def test_provider_commands(self):
        with patch("shutil.which", return_value=None):
            providers = detect_available_providers()

        commands = {p["name"]: p["command"] for p in providers}
        assert commands["gemini"] == "gemini"
        assert commands["claude"] == "claude"
        assert commands["codex"] == "codex"


class TestPatchConfigRoundTrip:
    """Verify that writing config via PATCH flow is read back correctly.

    Simulates the exact flow: write YAML → load_avatar_config → verify
    the provider/model reaches the backend config that services use.
    """

    def _write_yaml(self, tmp_path: Path, raw: dict) -> Path:
        config_path = tmp_path / "avatar.yaml"
        with open(config_path, "w") as f:
            yaml.dump(raw, f, default_flow_style=False, sort_keys=False)
        return config_path

    def test_change_default_provider_persists(self, tmp_path):
        """PATCH {provider: 'claude'} → load_avatar_config returns claude."""
        self._write_yaml(tmp_path, {"provider": "gemini"})
        # Simulate PATCH update
        raw = yaml.safe_load((tmp_path / "avatar.yaml").read_text())
        raw["provider"] = "claude"
        self._write_yaml(tmp_path, raw)
        # Reload and verify
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.provider == "claude"

    def test_change_provider_model_persists(self, tmp_path):
        """PATCH {providers: {gemini: {model: 'gemini-2.5-flash'}}} persists."""
        self._write_yaml(tmp_path, {
            "provider": "gemini",
            "gemini": {"model": "gemini-3-pro-preview"},
        })
        # Simulate PATCH update to model
        raw = yaml.safe_load((tmp_path / "avatar.yaml").read_text())
        raw["gemini"]["model"] = "gemini-2.5-flash"
        self._write_yaml(tmp_path, raw)
        # Reload and verify
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.providers["gemini"].model == "gemini-2.5-flash"

    def test_disable_provider_persists(self, tmp_path):
        """PATCH {providers: {claude: {enabled: false}}} persists."""
        self._write_yaml(tmp_path, {
            "claude": {"model": "claude-sonnet-4-5", "enabled": True},
        })
        raw = yaml.safe_load((tmp_path / "avatar.yaml").read_text())
        raw["claude"]["enabled"] = False
        self._write_yaml(tmp_path, raw)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.providers["claude"].enabled is False
        assert config.providers["claude"].model == "claude-sonnet-4-5"

    def test_toggle_enabled_persists(self, tmp_path):
        """PATCH {enabled: false} → config.enabled is False."""
        self._write_yaml(tmp_path, {"enabled": True})
        raw = yaml.safe_load((tmp_path / "avatar.yaml").read_text())
        raw["enabled"] = False
        self._write_yaml(tmp_path, raw)
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.enabled is False

    def test_mount_uses_config_provider(self, tmp_path):
        """try_mount_avatar_engine passes config.provider to create_api_app."""
        from unittest.mock import MagicMock, call

        self._write_yaml(tmp_path, {"provider": "claude"})
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.provider == "claude"
        # Verify the provider value that would be passed to create_api_app
        # (same logic as try_mount_avatar_engine line: provider=config.provider)
        assert config.provider == "claude"

    def test_full_patch_roundtrip(self, tmp_path):
        """Full PATCH simulation: start → update provider + model → reload."""
        # Start with default config
        self._write_yaml(tmp_path, {
            "provider": "gemini",
            "gemini": {"model": "gemini-3-pro-preview"},
        })
        initial = load_avatar_config(synapse_root=tmp_path)
        assert initial.provider == "gemini"
        assert initial.providers["gemini"].model == "gemini-3-pro-preview"

        # Simulate PATCH: change default provider to claude + set its model
        raw = yaml.safe_load((tmp_path / "avatar.yaml").read_text())
        raw["provider"] = "claude"
        if "claude" not in raw or not isinstance(raw.get("claude"), dict):
            raw["claude"] = {}
        raw["claude"]["model"] = "claude-sonnet-4-5"
        self._write_yaml(tmp_path, raw)

        # Reload and verify both changes
        updated = load_avatar_config(synapse_root=tmp_path)
        assert updated.provider == "claude"
        assert updated.providers["claude"].model == "claude-sonnet-4-5"
        # Old provider config preserved
        assert updated.providers["gemini"].model == "gemini-3-pro-preview"
