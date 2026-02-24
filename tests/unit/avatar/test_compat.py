"""
Tests for avatar engine version compatibility checking.

Covers:
  - check_avatar_engine_compat() with various version scenarios
  - AVATAR_ENGINE_MIN_VERSION constant
  - engine_min_version in /status response
"""

from unittest.mock import patch

import pytest


class TestCheckAvatarEngineCompat:
    """Unit tests for check_avatar_engine_compat()."""

    def test_returns_false_when_not_available(self):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", False), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", None):
            assert check_avatar_engine_compat() is False

    def test_returns_false_when_version_unknown(self):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "unknown"):
            assert check_avatar_engine_compat() is False

    def test_returns_false_when_version_none(self):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", None):
            assert check_avatar_engine_compat() is False

    def test_returns_true_when_version_meets_minimum(self):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "1.0.0"):
            assert check_avatar_engine_compat() is True

    def test_returns_true_when_version_exceeds_minimum(self):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "2.3.1"):
            assert check_avatar_engine_compat() is True

    def test_returns_false_when_version_below_minimum(self):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "0.9.0"):
            assert check_avatar_engine_compat() is False

    def test_logs_warning_when_below_minimum(self, caplog):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "0.5.0"):
            import logging
            with caplog.at_level(logging.WARNING, logger="src.avatar"):
                check_avatar_engine_compat()

        assert "below minimum" in caplog.text

    def test_logs_warning_when_version_unknown(self, caplog):
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "unknown"):
            import logging
            with caplog.at_level(logging.WARNING, logger="src.avatar"):
                check_avatar_engine_compat()

        assert "unknown" in caplog.text

    def test_graceful_when_packaging_not_available(self):
        """If packaging module is missing, the check should return False (conservative)."""
        from src.avatar import check_avatar_engine_compat

        with patch("src.avatar.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.AVATAR_ENGINE_VERSION", "1.0.0"), \
             patch.dict("sys.modules", {"packaging": None, "packaging.version": None}):
            # Should not raise, returns False (treats as incompatible when can't verify)
            result = check_avatar_engine_compat()
            assert result is False


class TestMinVersionConstant:
    """Verify AVATAR_ENGINE_MIN_VERSION is set correctly."""

    def test_min_version_is_string(self):
        from src.avatar import AVATAR_ENGINE_MIN_VERSION

        assert isinstance(AVATAR_ENGINE_MIN_VERSION, str)
        # Should be valid semver
        parts = AVATAR_ENGINE_MIN_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_min_version_value(self):
        from src.avatar import AVATAR_ENGINE_MIN_VERSION

        assert AVATAR_ENGINE_MIN_VERSION == "1.0.0"


class TestStatusEndpointMinVersion:
    """Verify /status returns engine_min_version field."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from src.avatar.routes import invalidate_avatar_cache
        invalidate_avatar_cache()
        yield
        invalidate_avatar_cache()

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_status_includes_min_version(self, mock_config, mock_providers):
        from src.avatar.routes import avatar_status

        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = []

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
            result = avatar_status()

        assert "engine_min_version" in result
        assert result["engine_min_version"] == "1.0.0"

    @patch("src.avatar.routes.detect_available_providers")
    @patch("src.avatar.routes.load_avatar_config")
    def test_status_min_version_matches_constant(self, mock_config, mock_providers):
        from src.avatar import AVATAR_ENGINE_MIN_VERSION
        from src.avatar.routes import avatar_status

        mock_config.return_value = _make_config(enabled=True)
        mock_providers.return_value = []

        with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False):
            result = avatar_status()

        assert result["engine_min_version"] == AVATAR_ENGINE_MIN_VERSION


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
