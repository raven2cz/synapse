"""
Tests for avatar engine configuration loading.

Covers:
  - Default config when no YAML file exists
  - Loading config from YAML file
  - Safety mode defaults and override
  - Provider detection (with mocked shutil.which)
  - Path resolution
  - Malformed YAML handling
"""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

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

    def test_no_providers_configured(self, tmp_path):
        config = load_avatar_config(synapse_root=tmp_path)
        assert config.providers == {}

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

    def test_gemini_installed(self):
        def mock_which(cmd):
            return "/usr/bin/gemini" if cmd == "gemini" else None

        with patch("shutil.which", side_effect=mock_which):
            providers = detect_available_providers()

        gemini = next(p for p in providers if p["name"] == "gemini")
        claude = next(p for p in providers if p["name"] == "claude")
        assert gemini["installed"] is True
        assert claude["installed"] is False

    def test_all_providers_installed(self):
        with patch(
            "shutil.which", return_value="/usr/bin/something"
        ):
            providers = detect_available_providers()
        assert all(p["installed"] for p in providers)

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
