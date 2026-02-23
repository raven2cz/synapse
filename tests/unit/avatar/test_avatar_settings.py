"""
Tests for avatar settings endpoints.

Covers:
  - GET /avatars endpoint: builtin list, custom from dir, edge cases
  - _list_custom_avatars: size guard, symlinks, edge cases
  - GET /providers uses cache
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.avatar.routes import (
    avatar_avatars_endpoint,
    avatar_providers,
    invalidate_avatar_cache,
    _list_custom_avatars,
    _MAX_AVATAR_JSON_SIZE,
    BUILTIN_AVATARS,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Invalidate avatar route cache before each test."""
    invalidate_avatar_cache()
    yield
    invalidate_avatar_cache()


def _make_config(avatars_dir=None, **kwargs):
    """Create a minimal AvatarConfig for testing."""
    from src.avatar.config import AvatarConfig

    return AvatarConfig(
        enabled=kwargs.get("enabled", True),
        provider=kwargs.get("provider", "gemini"),
        safety=kwargs.get("safety", "safe"),
        config_path=Path("/tmp/test-avatar.yaml"),
        skills_dir=Path("/tmp/nonexistent-skills"),
        custom_skills_dir=Path("/tmp/nonexistent-custom"),
        avatars_dir=avatars_dir,
    )


class TestAvatarsEndpoint:
    """GET /avatars returns built-in + custom avatars."""

    @patch("src.avatar.routes.load_avatar_config")
    def test_builtin_list(self, mock_config, tmp_path):
        """Built-in avatars are always returned (8 total)."""
        mock_config.return_value = _make_config(avatars_dir=tmp_path / "empty")
        result = avatar_avatars_endpoint()

        assert len(result["builtin"]) == len(BUILTIN_AVATARS)
        ids = [a["id"] for a in result["builtin"]]
        assert "bella" in ids
        assert "astronautka" in ids
        for avatar in result["builtin"]:
            assert avatar["category"] == "builtin"

    @patch("src.avatar.routes.load_avatar_config")
    def test_custom_from_dir(self, mock_config, tmp_path):
        """Custom avatars are read from avatar.json in subdirs."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        # Create a valid custom avatar
        custom = avatars_dir / "my-avatar"
        custom.mkdir()
        (custom / "avatar.json").write_text(json.dumps({"name": "My Avatar"}))

        mock_config.return_value = _make_config(avatars_dir=avatars_dir)
        result = avatar_avatars_endpoint()

        assert len(result["custom"]) == 1
        assert result["custom"][0]["id"] == "my-avatar"
        assert result["custom"][0]["name"] == "My Avatar"
        assert result["custom"][0]["category"] == "custom"

    @patch("src.avatar.routes.load_avatar_config")
    def test_empty_dir(self, mock_config, tmp_path):
        """Empty avatars dir returns no custom avatars."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        mock_config.return_value = _make_config(avatars_dir=avatars_dir)
        result = avatar_avatars_endpoint()

        assert result["custom"] == []

    @patch("src.avatar.routes.load_avatar_config")
    def test_nonexistent_dir(self, mock_config, tmp_path):
        """Nonexistent avatars dir returns empty list."""
        mock_config.return_value = _make_config(
            avatars_dir=tmp_path / "does-not-exist"
        )
        result = avatar_avatars_endpoint()

        assert result["custom"] == []

    @patch("src.avatar.routes.load_avatar_config")
    def test_invalid_json_skipped(self, mock_config, tmp_path):
        """Subdirs with invalid avatar.json are silently skipped."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        # Invalid JSON
        bad_avatar = avatars_dir / "bad-avatar"
        bad_avatar.mkdir()
        (bad_avatar / "avatar.json").write_text("{invalid json")

        # Valid avatar
        good_avatar = avatars_dir / "good-avatar"
        good_avatar.mkdir()
        (good_avatar / "avatar.json").write_text(json.dumps({"name": "Good"}))

        mock_config.return_value = _make_config(avatars_dir=avatars_dir)
        result = avatar_avatars_endpoint()

        assert len(result["custom"]) == 1
        assert result["custom"][0]["id"] == "good-avatar"


class TestListCustomAvatars:
    """Direct tests for _list_custom_avatars helper."""

    def test_none_dir(self):
        """None avatars_dir returns empty list."""
        assert _list_custom_avatars(None) == []

    def test_dir_without_avatar_json_ignored(self, tmp_path):
        """Subdirectories without avatar.json are ignored."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        # Dir without avatar.json
        (avatars_dir / "no-json-dir").mkdir()
        # File (not dir)
        (avatars_dir / "some-file.txt").write_text("not a dir")

        result = _list_custom_avatars(avatars_dir)
        assert result == []

    def test_name_fallback_to_dirname(self, tmp_path):
        """If avatar.json has no 'name' field, use directory name."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        avatar_dir = avatars_dir / "unnamed-avatar"
        avatar_dir.mkdir()
        (avatar_dir / "avatar.json").write_text(json.dumps({"description": "test"}))

        result = _list_custom_avatars(avatars_dir)
        assert len(result) == 1
        assert result[0]["name"] == "unnamed-avatar"

    def test_oversized_avatar_json_skipped(self, tmp_path):
        """avatar.json larger than size guard is skipped."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        big_avatar = avatars_dir / "big-avatar"
        big_avatar.mkdir()
        # Create a file larger than the guard
        (big_avatar / "avatar.json").write_text("x" * (_MAX_AVATAR_JSON_SIZE + 1))

        result = _list_custom_avatars(avatars_dir)
        assert result == []

    def test_symlink_dir_skipped(self, tmp_path):
        """Symlinked directories are skipped (follow_symlinks=False)."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        # Create a real dir with valid avatar
        real_dir = tmp_path / "real-avatar"
        real_dir.mkdir()
        (real_dir / "avatar.json").write_text(json.dumps({"name": "Real"}))

        # Create symlink in avatars dir
        symlink = avatars_dir / "linked-avatar"
        try:
            symlink.symlink_to(real_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this platform")

        result = _list_custom_avatars(avatars_dir)
        assert result == []

    def test_non_dict_json_skipped(self, tmp_path):
        """avatar.json with non-dict content (e.g. array) is skipped."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        arr_avatar = avatars_dir / "array-avatar"
        arr_avatar.mkdir()
        (arr_avatar / "avatar.json").write_text(json.dumps(["not", "a", "dict"]))

        result = _list_custom_avatars(avatars_dir)
        assert result == []


class TestProvidersEndpointCache:
    """GET /providers should use cache instead of direct detection."""

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_providers_uses_cache(self, mock_config, mock_detect):
        """Calling /providers twice should only detect once (cached)."""
        mock_config.return_value = _make_config()
        mock_detect.return_value = [
            {"name": "gemini", "installed": True, "display_name": "Gemini CLI", "command": "gemini"},
        ]

        result1 = avatar_providers()
        result2 = avatar_providers()

        assert len(result1) == 1
        assert result1 == result2
        # detect_available_providers called once (by _get_cached_config), not twice
        mock_detect.assert_called_once()
