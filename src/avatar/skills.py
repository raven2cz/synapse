"""
Avatar Skills System — domain knowledge loader.

Skills are markdown files with Synapse-specific knowledge that get appended
to the system prompt. Built-in skills ship in config/avatar/skills/,
custom skills go in ~/.synapse/avatar/custom-skills/.

Custom skills can override built-in skills by using the same filename.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from .config import AvatarConfig

logger = logging.getLogger(__name__)

# Maximum file size for a single skill (50 KB)
MAX_SKILL_SIZE = 50 * 1024


def load_skill(path: Path) -> str:
    """
    Read a single skill file and return its content.

    Strips YAML frontmatter (--- delimited) if present.
    Returns empty string for binary/unreadable files.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        logger.warning("Cannot read skill file %s: %s", path, e)
        return ""

    # Strip YAML frontmatter (--- ... ---)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].lstrip("\n")

    return content


def list_skills(config: AvatarConfig) -> Dict[str, List[Dict[str, Any]]]:
    """
    List available skills with metadata.

    Returns {"builtin": [...], "custom": [...]}, each entry containing:
      - name: filename without extension
      - path: absolute path string
      - size: file size in bytes
      - category: "builtin" or "custom"
    """
    result: Dict[str, List[Dict[str, Any]]] = {"builtin": [], "custom": []}

    for category, skills_dir in [
        ("builtin", config.skills_dir),
        ("custom", config.custom_skills_dir),
    ]:
        if skills_dir is None or not skills_dir.is_dir():
            continue

        for path in sorted(skills_dir.glob("*.md")):
            try:
                if not path.is_file():
                    continue
                size = path.stat().st_size
            except OSError:
                continue
            result[category].append({
                "name": path.stem,
                "path": str(path),
                "size": size,
                "category": category,
            })

    return result


def build_system_prompt(config: AvatarConfig) -> str:
    """
    Build complete system prompt: base_prompt + built-in skills + custom skills.

    Skills are loaded alphabetically. Custom skills with the same filename
    as a built-in skill override the built-in version.
    Files larger than MAX_SKILL_SIZE are skipped with a warning.
    """
    parts = [config.system_prompt]

    # Collect skills: built-in first, then custom overrides
    skill_map: Dict[str, tuple[Path, str]] = {}  # name -> (path, category)

    for category, skills_dir in [
        ("builtin", config.skills_dir),
        ("custom", config.custom_skills_dir),
    ]:
        if skills_dir is None or not skills_dir.is_dir():
            continue

        for path in sorted(skills_dir.glob("*.md")):
            try:
                if not path.is_file():
                    continue
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_SKILL_SIZE:
                logger.warning(
                    "Skipping skill %s (%d bytes > %d limit)",
                    path.name, size, MAX_SKILL_SIZE,
                )
                continue

            name = path.stem
            if name in skill_map and category == "custom":
                logger.info(
                    "Custom skill '%s' overrides built-in", name,
                )
            skill_map[name] = (path, category)

    # Append skills in alphabetical order
    if skill_map:
        parts.append("\n---\n\n# Domain Knowledge\n")

        for name in sorted(skill_map):
            path, _category = skill_map[name]
            content = load_skill(path)
            if content.strip():
                parts.append(f"## Skill: {name}\n\n{content.strip()}\n")

    return "\n".join(parts)
