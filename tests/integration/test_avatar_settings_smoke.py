"""
Smoke / E2E tests for avatar settings (Iterace 4).

Tests the full avatar API lifecycle through a real FastAPI TestClient
with real filesystem operations (tmp_path). Only avatar-engine availability
and provider detection are mocked — config loading, skills scanning,
avatar directory scanning, and response serialization run against real files.

Covers:
  - Full lifecycle: status → config → providers → skills → avatars
  - Real filesystem: config, skills, custom avatars all from tmp_path
  - State transitions: disabled → setup_required → ready
  - Multiple custom avatars with varying validity
  - Skills + avatars combined consistency
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.avatar.config import AvatarConfig, AvatarProviderConfig, load_avatar_config
from src.avatar.routes import avatar_router, invalidate_avatar_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Invalidate avatar route cache before/after each test."""
    invalidate_avatar_cache()
    yield
    invalidate_avatar_cache()


@pytest.fixture
def avatar_root(tmp_path):
    """Create a realistic avatar directory structure."""
    root = tmp_path / ".synapse"
    root.mkdir()

    # Config file (top-level provider keys match config loader)
    config_file = root / "avatar.yaml"
    config_file.write_text(
        "enabled: true\n"
        "provider: gemini\n"
        "gemini:\n"
        "  model: gemini-2.5-pro\n"
        "claude:\n"
        "  model: claude-sonnet-4-20250514\n"
        "  enabled: false\n"
    )

    # Skills
    skills_dir = root / "avatar" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "inventory.md").write_text(
        "# Inventory Management\n\nManage blobs, verify integrity, cleanup orphans."
    )
    (skills_dir / "parameters.md").write_text(
        "# Generation Parameters\n\nExtract and manage AI generation metadata."
    )
    (skills_dir / "workflows.md").write_text(
        "# ComfyUI Workflows\n\nManage workflow files and symlinks."
    )

    # Custom skills
    custom_skills = root / "avatar" / "custom-skills"
    custom_skills.mkdir(parents=True)
    (custom_skills / "my-workflow.md").write_text("# My Custom Workflow\nDo cool things.")

    # Custom avatars
    avatars_dir = root / "avatar" / "avatars"
    avatars_dir.mkdir(parents=True)

    artist = avatars_dir / "artist"
    artist.mkdir()
    (artist / "avatar.json").write_text(json.dumps({
        "name": "The Artist",
        "description": "Creative and visual-thinking avatar",
        "personality": "artistic",
    }))

    coder = avatars_dir / "coder"
    coder.mkdir()
    (coder / "avatar.json").write_text(json.dumps({
        "name": "Code Master",
        "description": "Programming expert",
    }))

    # Invalid avatar (should be skipped)
    broken = avatars_dir / "broken"
    broken.mkdir()
    (broken / "avatar.json").write_text("{invalid")

    # Empty dir without avatar.json (should be skipped)
    (avatars_dir / "empty-dir").mkdir()

    return root


@pytest.fixture
def avatar_config(avatar_root):
    """Load real config from avatar_root filesystem."""
    return load_avatar_config(synapse_root=avatar_root)


@pytest.fixture
def app():
    """Create a test FastAPI app with avatar routes."""
    app = FastAPI()
    app.include_router(avatar_router, prefix="/api/avatar")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _providers_list(installed: list[str]):
    """Build provider detection results."""
    all_p = [
        {"name": "gemini", "display_name": "Gemini CLI", "command": "gemini"},
        {"name": "claude", "display_name": "Claude Code", "command": "claude"},
        {"name": "codex", "display_name": "Codex CLI", "command": "codex"},
    ]
    for p in all_p:
        p["installed"] = p["name"] in installed
    return all_p


@pytest.mark.smoke
class TestAvatarFullLifecycle:
    """Full lifecycle: hit every endpoint, verify consistency."""

    def test_full_lifecycle_ready_state(self, client, avatar_config):
        """
        Lifecycle: status → config → providers → skills → avatars.
        All data is consistent and reflects the real filesystem.
        """
        providers = _providers_list(["gemini"])

        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp, \
             patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
            mock_lc.return_value = avatar_config
            mock_dp.return_value = providers

            # Step 1: Status — should be "ready"
            status = client.get("/api/avatar/status").json()
            assert status["state"] == "ready"
            assert status["available"] is True
            assert status["engine_installed"] is True
            assert status["engine_version"] == "0.3.0"
            assert status["active_provider"] == "gemini"
            assert status["safety"] == "safe"
            assert len(status["providers"]) == 3

            # Step 2: Config — should include skills and provider configs
            config = client.get("/api/avatar/config").json()
            assert config["enabled"] is True
            assert config["provider"] == "gemini"
            assert config["safety"] == "safe"
            assert config["max_history"] == 100
            assert config["skills_count"]["builtin"] == 3  # inventory, parameters, workflows
            assert config["skills_count"]["custom"] == 1   # my-workflow
            assert "skills" in config

            builtin_names = [s["name"] for s in config["skills"]["builtin"]]
            assert "inventory" in builtin_names
            assert "parameters" in builtin_names
            assert "workflows" in builtin_names

            custom_names = [s["name"] for s in config["skills"]["custom"]]
            assert "my-workflow" in custom_names

            # Provider configs from YAML
            assert "gemini" in config["provider_configs"]

            # Step 3: Providers — should match status
            prov_resp = client.get("/api/avatar/providers").json()
            assert prov_resp == status["providers"]

            # Step 4: Skills — dedicated endpoint
            skills = client.get("/api/avatar/skills").json()
            assert skills["builtin"] == config["skills"]["builtin"]
            assert skills["custom"] == config["skills"]["custom"]

            # Step 5: Avatars — builtin + custom from filesystem
            avatars = client.get("/api/avatar/avatars").json()
            assert len(avatars["builtin"]) == 8  # hardcoded built-in list

            # Custom: artist + coder (broken + empty-dir skipped)
            custom_ids = [a["id"] for a in avatars["custom"]]
            assert "artist" in custom_ids
            assert "coder" in custom_ids
            assert "broken" not in custom_ids
            assert "empty-dir" not in custom_ids
            assert len(avatars["custom"]) == 2

            # Verify custom avatar names
            artist_avatar = next(a for a in avatars["custom"] if a["id"] == "artist")
            assert artist_avatar["name"] == "The Artist"

    def test_full_lifecycle_disabled_state(self, client, avatar_root):
        """When disabled, status reflects it but other endpoints still work."""
        config = load_avatar_config(synapse_root=avatar_root)
        config.enabled = False

        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp, \
             patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
            mock_lc.return_value = config
            mock_dp.return_value = _providers_list(["gemini"])

            status = client.get("/api/avatar/status").json()
            assert status["state"] == "disabled"
            assert status["available"] is False
            assert status["active_provider"] is None

            # Config endpoint still returns data
            cfg = client.get("/api/avatar/config").json()
            assert cfg["enabled"] is False
            assert cfg["provider"] == "gemini"  # still reports configured provider


@pytest.mark.smoke
class TestAvatarStateTransitions:
    """Test different state scenarios end-to-end."""

    def test_setup_required_to_ready(self, client, avatar_config):
        """Simulate going from setup_required to ready by adding a provider."""
        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp:
            mock_lc.return_value = avatar_config

            # State 1: No engine, no providers → setup_required
            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False), \
                 patch("src.avatar.routes.AVATAR_ENGINE_VERSION", None):
                mock_dp.return_value = _providers_list([])
                status1 = client.get("/api/avatar/status").json()
                assert status1["state"] == "setup_required"

            # Invalidate cache to simulate config reload
            invalidate_avatar_cache()

            # State 2: Engine installed, provider available → ready
            with patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
                 patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
                mock_dp.return_value = _providers_list(["gemini"])
                status2 = client.get("/api/avatar/status").json()
                assert status2["state"] == "ready"
                assert status2["available"] is True

    def test_no_engine_state(self, client, avatar_config):
        """Provider installed but no engine → no_engine state."""
        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp, \
             patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", None):
            mock_lc.return_value = avatar_config
            mock_dp.return_value = _providers_list(["claude"])

            status = client.get("/api/avatar/status").json()
            assert status["state"] == "no_engine"
            assert status["engine_installed"] is False
            assert status["engine_version"] is None
            assert status["available"] is False

    def test_no_provider_state(self, client, avatar_config):
        """Engine installed but no provider → no_provider state."""
        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp, \
             patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", True), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", "0.3.0"):
            mock_lc.return_value = avatar_config
            mock_dp.return_value = _providers_list([])

            status = client.get("/api/avatar/status").json()
            assert status["state"] == "no_provider"
            assert status["engine_installed"] is True
            assert status["available"] is False


@pytest.mark.smoke
class TestAvatarFilesystemSmoke:
    """Smoke tests with real filesystem operations."""

    def test_many_custom_avatars(self, client, tmp_path):
        """Stress test: 20 custom avatars, some valid, some not."""
        avatars_dir = tmp_path / "avatars"
        avatars_dir.mkdir()

        valid_count = 0
        for i in range(20):
            d = avatars_dir / f"avatar-{i:02d}"
            d.mkdir()
            if i % 3 == 0:
                # Invalid: no avatar.json
                pass
            elif i % 3 == 1:
                # Valid
                (d / "avatar.json").write_text(json.dumps({"name": f"Avatar #{i}"}))
                valid_count += 1
            else:
                # Valid, no name (fallback to dirname)
                (d / "avatar.json").write_text(json.dumps({"description": "test"}))
                valid_count += 1

        config = AvatarConfig(
            config_path=Path("/tmp/test.yaml"),
            skills_dir=Path("/tmp/no-skills"),
            custom_skills_dir=Path("/tmp/no-custom"),
            avatars_dir=avatars_dir,
        )

        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp:
            mock_lc.return_value = config
            mock_dp.return_value = []

            resp = client.get("/api/avatar/avatars")

        data = resp.json()
        assert len(data["custom"]) == valid_count
        assert len(data["builtin"]) == 8

        # Verify fallback names for nameless avatars
        nameless = [a for a in data["custom"] if a["name"].startswith("avatar-")]
        assert len(nameless) > 0  # Some used dirname as fallback

    def test_skills_from_real_files(self, client, tmp_path):
        """Skills are read from real .md files with correct metadata."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        content_a = "# Alpha Skill\n\nDoes alpha things.\nWith multiple lines."
        content_b = "# Beta\n\nShort."
        (skills_dir / "alpha.md").write_text(content_a)
        (skills_dir / "beta.md").write_text(content_b)

        # Non-.md files should be ignored
        (skills_dir / "notes.txt").write_text("not a skill")
        (skills_dir / "README").write_text("also not a skill")

        config = AvatarConfig(
            config_path=Path("/tmp/test.yaml"),
            skills_dir=skills_dir,
            custom_skills_dir=Path("/tmp/no-custom"),
        )

        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp:
            mock_lc.return_value = config
            mock_dp.return_value = []

            resp = client.get("/api/avatar/skills")

        data = resp.json()
        names = [s["name"] for s in data["builtin"]]
        assert "alpha" in names
        assert "beta" in names
        assert len(data["builtin"]) == 2  # .txt and README ignored

        # Verify size is actual file size
        alpha = next(s for s in data["builtin"] if s["name"] == "alpha")
        assert alpha["size"] == len(content_a.encode("utf-8"))

    def test_config_real_load(self, client, avatar_root):
        """Load real config from YAML and verify all endpoints work."""
        config = load_avatar_config(synapse_root=avatar_root)

        with patch("src.avatar.routes.load_avatar_config") as mock_lc, \
             patch("src.avatar.routes.detect_available_providers") as mock_dp, \
             patch("src.avatar.routes.AVATAR_ENGINE_AVAILABLE", False), \
             patch("src.avatar.routes.AVATAR_ENGINE_VERSION", None):
            mock_lc.return_value = config
            mock_dp.return_value = _providers_list([])

            # All endpoints should return 200 with real config
            for endpoint in ["/api/avatar/status", "/api/avatar/config",
                             "/api/avatar/providers", "/api/avatar/skills",
                             "/api/avatar/avatars"]:
                resp = client.get(endpoint)
                assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"
