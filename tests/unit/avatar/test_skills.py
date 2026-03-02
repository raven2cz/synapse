"""
Unit tests for avatar skills system.

Covers:
  - build_system_prompt: base only, builtin, custom, overrides, ordering, size guard
  - list_skills: builtin, custom, both, empty, metadata
  - load_skill: basic, empty, unicode, binary, frontmatter
  - Skills endpoint integration
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.avatar.config import AvatarConfig
from src.avatar.skills import (
    MAX_SKILL_SIZE,
    build_system_prompt,
    list_skills,
    load_skill,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_config(
    tmp_path: Path,
    skills_dir: str = "skills",
    custom_dir: str = "custom-skills",
    create_dirs: bool = True,
) -> AvatarConfig:
    """Create AvatarConfig with tmp_path-based skill directories."""
    sd = tmp_path / skills_dir
    cd = tmp_path / custom_dir
    if create_dirs:
        sd.mkdir(parents=True, exist_ok=True)
        cd.mkdir(parents=True, exist_ok=True)
    return AvatarConfig(
        skills_dir=sd,
        custom_skills_dir=cd,
        config_path=tmp_path / "avatar.yaml",
    )


def _write_skill(directory: Path, name: str, content: str) -> Path:
    """Write a skill .md file into a directory."""
    path = directory / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ── TestBuildSystemPrompt ────────────────────────────────────────────


class TestBuildSystemPrompt:
    """build_system_prompt merges base prompt with skill files."""

    def test_base_only_no_skill_dirs(self, tmp_path):
        config = _make_config(tmp_path, create_dirs=False)
        result = build_system_prompt(config)
        assert result == config.system_prompt

    def test_base_only_empty_dirs(self, tmp_path):
        config = _make_config(tmp_path)
        result = build_system_prompt(config)
        assert result == config.system_prompt

    def test_with_builtin_skills(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "basics", "# Basics\nSome content.")

        result = build_system_prompt(config)
        assert config.system_prompt in result
        assert "## Skill: basics" in result
        assert "Some content." in result

    def test_with_custom_skills(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.custom_skills_dir, "my-skill", "Custom knowledge.")

        result = build_system_prompt(config)
        assert "## Skill: my-skill" in result
        assert "Custom knowledge." in result

    def test_custom_overrides_builtin(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "basics", "Built-in version.")
        _write_skill(config.custom_skills_dir, "basics", "Custom override version.")

        result = build_system_prompt(config)
        assert "Custom override version." in result
        assert "Built-in version." not in result

    def test_alphabetical_order(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "zebra", "Zebra content.")
        _write_skill(config.skills_dir, "alpha", "Alpha content.")
        _write_skill(config.skills_dir, "middle", "Middle content.")

        result = build_system_prompt(config)
        alpha_pos = result.index("## Skill: alpha")
        middle_pos = result.index("## Skill: middle")
        zebra_pos = result.index("## Skill: zebra")
        assert alpha_pos < middle_pos < zebra_pos

    def test_nonexistent_dirs(self, tmp_path):
        config = AvatarConfig(
            skills_dir=tmp_path / "does-not-exist",
            custom_skills_dir=tmp_path / "also-missing",
        )
        result = build_system_prompt(config)
        assert result == config.system_prompt

    def test_none_dirs(self):
        config = AvatarConfig(skills_dir=None, custom_skills_dir=None)
        result = build_system_prompt(config)
        assert result == config.system_prompt

    def test_size_guard_skips_large(self, tmp_path):
        config = _make_config(tmp_path)
        large_path = config.skills_dir / "large-skill.md"
        large_path.write_text("x" * (MAX_SKILL_SIZE + 1), encoding="utf-8")
        _write_skill(config.skills_dir, "small", "Small content.")

        result = build_system_prompt(config)
        assert "## Skill: small" in result
        assert "## Skill: large-skill" not in result

    def test_empty_skill_file_skipped(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "empty", "")
        _write_skill(config.skills_dir, "good", "Good content.")

        result = build_system_prompt(config)
        assert "## Skill: good" in result
        assert "## Skill: empty" not in result

    def test_multiple_builtin_and_custom(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "a-builtin", "Builtin A.")
        _write_skill(config.skills_dir, "b-builtin", "Builtin B.")
        _write_skill(config.custom_skills_dir, "c-custom", "Custom C.")

        result = build_system_prompt(config)
        assert "## Skill: a-builtin" in result
        assert "## Skill: b-builtin" in result
        assert "## Skill: c-custom" in result

    def test_domain_knowledge_header_present(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "test", "Content.")

        result = build_system_prompt(config)
        assert "# Domain Knowledge" in result

    def test_stat_oserror_skips_file(self, tmp_path):
        """File deleted between glob and stat is gracefully skipped (TOCTOU)."""
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "good", "Good content.")
        _write_skill(config.skills_dir, "vanishing", "Gone soon.")

        original_stat = Path.stat

        def patched_stat(self, *args, **kwargs):
            if self.stem == "vanishing":
                raise OSError("File vanished")
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", patched_stat):
            result = build_system_prompt(config)

        assert "## Skill: good" in result
        assert "vanishing" not in result


# ── TestListSkills ───────────────────────────────────────────────────


class TestListSkills:
    """list_skills returns categorized metadata."""

    def test_builtin_only(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "basics", "# Basics")

        result = list_skills(config)
        assert len(result["builtin"]) == 1
        assert len(result["custom"]) == 0
        assert result["builtin"][0]["name"] == "basics"
        assert result["builtin"][0]["category"] == "builtin"

    def test_custom_only(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.custom_skills_dir, "my-skill", "Custom.")

        result = list_skills(config)
        assert len(result["builtin"]) == 0
        assert len(result["custom"]) == 1
        assert result["custom"][0]["name"] == "my-skill"

    def test_both_categories(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "builtin-one", "B.")
        _write_skill(config.custom_skills_dir, "custom-one", "C.")

        result = list_skills(config)
        assert len(result["builtin"]) == 1
        assert len(result["custom"]) == 1

    def test_empty_dirs(self, tmp_path):
        config = _make_config(tmp_path)
        result = list_skills(config)
        assert result == {"builtin": [], "custom": []}

    def test_nonexistent_dirs(self, tmp_path):
        config = AvatarConfig(
            skills_dir=tmp_path / "missing",
            custom_skills_dir=tmp_path / "also-missing",
        )
        result = list_skills(config)
        assert result == {"builtin": [], "custom": []}

    def test_includes_metadata(self, tmp_path):
        config = _make_config(tmp_path)
        content = "# Test skill with some content"
        _write_skill(config.skills_dir, "test-skill", content)

        result = list_skills(config)
        skill = result["builtin"][0]
        assert skill["name"] == "test-skill"
        assert "path" in skill
        assert skill["size"] > 0
        assert skill["category"] == "builtin"

    def test_alphabetical_order(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "zebra", "Z.")
        _write_skill(config.skills_dir, "alpha", "A.")

        result = list_skills(config)
        names = [s["name"] for s in result["builtin"]]
        assert names == ["alpha", "zebra"]

    def test_none_dirs(self):
        config = AvatarConfig(skills_dir=None, custom_skills_dir=None)
        result = list_skills(config)
        assert result == {"builtin": [], "custom": []}

    def test_stat_oserror_skips_file(self, tmp_path):
        """File deleted between glob and stat is gracefully skipped (TOCTOU)."""
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "good", "Content.")
        _write_skill(config.skills_dir, "vanishing", "Gone soon.")

        original_stat = Path.stat

        def patched_stat(self, *args, **kwargs):
            if self.stem == "vanishing":
                raise OSError("File vanished")
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", patched_stat):
            result = list_skills(config)

        assert len(result["builtin"]) == 1
        assert result["builtin"][0]["name"] == "good"


# ── TestLoadSkill ────────────────────────────────────────────────────


class TestLoadSkill:
    """load_skill reads and processes individual skill files."""

    def test_basic_load(self, tmp_path):
        path = _write_skill(tmp_path, "test", "# Test\nContent here.")
        result = load_skill(path)
        assert result == "# Test\nContent here."

    def test_empty_file(self, tmp_path):
        path = _write_skill(tmp_path, "empty", "")
        result = load_skill(path)
        assert result == ""

    def test_unicode_content(self, tmp_path):
        path = _write_skill(tmp_path, "unicode", "# Přehled\nČeský obsah 🎨")
        result = load_skill(path)
        assert "Přehled" in result
        assert "Český obsah" in result

    def test_binary_file_returns_empty(self, tmp_path):
        path = tmp_path / "binary.md"
        path.write_bytes(b"\x00\x01\x02\xff\xfe\xfd" * 100)
        result = load_skill(path)
        assert result == ""

    def test_strips_yaml_frontmatter(self, tmp_path):
        content = "---\ntitle: Test\ncategory: basics\n---\n# Actual content\nBody."
        path = _write_skill(tmp_path, "frontmatter", content)
        result = load_skill(path)
        assert result == "# Actual content\nBody."
        assert "title:" not in result

    def test_no_frontmatter_unchanged(self, tmp_path):
        content = "# Plain content\nNo frontmatter here."
        path = _write_skill(tmp_path, "plain", content)
        result = load_skill(path)
        assert result == content

    def test_incomplete_frontmatter_preserved(self, tmp_path):
        content = "---\ntitle: No closing delimiter\n# Content"
        path = _write_skill(tmp_path, "broken", content)
        result = load_skill(path)
        # With only one ---, split produces <3 parts, content preserved as-is
        assert "---" in result

    def test_nonexistent_file(self, tmp_path):
        path = tmp_path / "nonexistent.md"
        result = load_skill(path)
        assert result == ""


# ── TestSkillsEndpoint ───────────────────────────────────────────────


class TestSkillsEndpoint:
    """GET /skills returns skills list."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from src.avatar.routes import invalidate_avatar_cache
        invalidate_avatar_cache()
        yield
        invalidate_avatar_cache()

    @patch("src.avatar.routes.load_avatar_config")
    def test_returns_skills_list(self, mock_config, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "test-skill", "Content.")
        mock_config.return_value = config

        from src.avatar.routes import avatar_skills_endpoint
        result = avatar_skills_endpoint()

        assert "builtin" in result
        assert "custom" in result
        assert len(result["builtin"]) == 1
        assert result["builtin"][0]["name"] == "test-skill"

    @patch("src.avatar.routes.load_avatar_config")
    def test_empty_skills(self, mock_config, tmp_path):
        config = _make_config(tmp_path)
        mock_config.return_value = config

        from src.avatar.routes import avatar_skills_endpoint
        result = avatar_skills_endpoint()

        assert result == {"builtin": [], "custom": []}


# ── TestSystemPromptIntegration ──────────────────────────────────────


class TestSystemPromptIntegration:
    """Verify system prompt structure with skills."""

    def test_prompt_contains_base(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "test", "Skill content.")
        result = build_system_prompt(config)
        assert result.startswith(config.system_prompt)

    def test_prompt_contains_skills(self, tmp_path):
        config = _make_config(tmp_path)
        _write_skill(config.skills_dir, "skill-a", "Skill A content.")
        _write_skill(config.skills_dir, "skill-b", "Skill B content.")
        result = build_system_prompt(config)
        assert "Skill A content." in result
        assert "Skill B content." in result

    def test_prompt_length_reasonable(self, tmp_path):
        config = _make_config(tmp_path)
        # Add several skills, each ~100 chars
        for i in range(5):
            _write_skill(config.skills_dir, f"skill-{i}", f"Content for skill {i}.\n" * 5)
        result = build_system_prompt(config)
        # Should be reasonable size (base + 5 small skills)
        assert len(result) < 10_000
        assert len(result) > len(config.system_prompt)
