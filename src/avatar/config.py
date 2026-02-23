"""
Avatar Engine configuration loader.

Loads avatar configuration from ~/.synapse/avatar.yaml with fallback defaults.
The config file controls provider selection, safety mode, skills, and MCP servers.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_SYNAPSE_ROOT = Path.home() / ".synapse"
DEFAULT_CONFIG_FILENAME = "avatar.yaml"
DEFAULT_SKILLS_DIR = "avatar/skills"
DEFAULT_CUSTOM_SKILLS_DIR = "avatar/custom-skills"
DEFAULT_AVATARS_DIR = "avatar/avatars"


@dataclass
class AvatarProviderConfig:
    """Configuration for a single AI provider."""
    model: str = ""
    enabled: bool = True


@dataclass
class AvatarConfig:
    """Complete avatar-engine configuration for Synapse."""

    # Master switch
    enabled: bool = True

    # Provider selection
    provider: str = "gemini"

    # Safety mode: safe (default), ask (Gemini only), unrestricted
    safety: str = "safe"

    # System prompt (base, before skills are appended)
    system_prompt: str = (
        "You are a Synapse AI assistant — an expert in AI model management, "
        "ComfyUI workflows, Stable Diffusion, and image generation.\n\n"
        "You have access to Synapse tools via MCP. Use them to help the user "
        "manage their model inventory, import packs, resolve dependencies, "
        "and optimize generation parameters.\n\n"
        "Always be helpful, concise, and proactive."
    )

    # Provider-specific configs
    providers: Dict[str, AvatarProviderConfig] = field(default_factory=dict)

    # MCP server definitions
    mcp_servers: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Engine settings
    working_dir: str = str(DEFAULT_SYNAPSE_ROOT)
    max_history: int = 100

    # Paths (resolved at load time)
    config_path: Optional[Path] = None
    skills_dir: Optional[Path] = None
    custom_skills_dir: Optional[Path] = None
    avatars_dir: Optional[Path] = None

    # Raw YAML data for pass-through to avatar-engine
    _raw: Dict[str, Any] = field(default_factory=dict)


def _resolve_paths(synapse_root: Path) -> Dict[str, Path]:
    """Resolve avatar-related paths from Synapse root."""
    return {
        "config_path": synapse_root / DEFAULT_CONFIG_FILENAME,
        "skills_dir": synapse_root / DEFAULT_SKILLS_DIR,
        "custom_skills_dir": synapse_root / DEFAULT_CUSTOM_SKILLS_DIR,
        "avatars_dir": synapse_root / DEFAULT_AVATARS_DIR,
    }


def load_avatar_config(
    synapse_root: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> AvatarConfig:
    """
    Load avatar configuration from YAML file.

    Priority:
    1. Explicit config_path parameter
    2. <synapse_root>/avatar.yaml
    3. Default config (no file)

    Returns AvatarConfig with resolved paths and merged defaults.
    """
    if synapse_root is None:
        synapse_root = Path(
            os.environ.get("SYNAPSE_ROOT", DEFAULT_SYNAPSE_ROOT)
        ).expanduser().resolve()

    paths = _resolve_paths(synapse_root)

    # Determine config file location
    if config_path is None:
        config_path = paths["config_path"]

    # Load YAML if exists
    raw_config: Dict[str, Any] = {}
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw_config = loaded
            elif loaded is not None:
                logger.warning(f"Avatar config at {config_path} is not a mapping, using defaults")
            logger.info(f"Loaded avatar config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load avatar config from {config_path}: {e}")
    else:
        logger.debug(f"No avatar config at {config_path}, using defaults")

    # Build config from raw YAML + defaults
    config = AvatarConfig(
        enabled=raw_config.get("enabled", True),
        provider=raw_config.get("provider", "gemini"),
        safety=raw_config.get("engine", {}).get("safety_instructions", "safe"),
        system_prompt=raw_config.get("system_prompt", AvatarConfig.system_prompt),
        working_dir=raw_config.get("engine", {}).get(
            "working_dir", str(synapse_root)
        ),
        max_history=raw_config.get("engine", {}).get("max_history", 100),
        mcp_servers=raw_config.get("mcp_servers", {}),
        config_path=config_path,
        skills_dir=paths["skills_dir"],
        custom_skills_dir=paths["custom_skills_dir"],
        avatars_dir=paths["avatars_dir"],
        _raw=raw_config,
    )

    # Validate provider
    valid_providers = ("gemini", "claude", "codex")
    if config.provider not in valid_providers:
        logger.warning(
            "Unknown avatar provider '%s', expected one of %s. Falling back to 'gemini'.",
            config.provider,
            valid_providers,
        )
        config.provider = "gemini"

    # Validate safety mode
    valid_safety = ("safe", "ask", "unrestricted")
    if config.safety not in valid_safety:
        logger.warning(
            "Unknown safety mode '%s', expected one of %s. Falling back to 'safe'.",
            config.safety,
            valid_safety,
        )
        config.safety = "safe"

    # Parse provider configs
    for provider_name in ("gemini", "claude", "codex"):
        if provider_name in raw_config:
            prov_data = raw_config[provider_name]
            config.providers[provider_name] = AvatarProviderConfig(
                model=prov_data.get("model", ""),
                enabled=prov_data.get("enabled", True),
            )

    return config


def detect_available_providers() -> List[Dict[str, Any]]:
    """
    Detect which AI CLI providers are installed on the system.

    Returns list of provider info dicts with name, command, installed status.
    """
    import shutil  # noqa: module-level import not desired (optional dependency context)

    providers = [
        {
            "name": "gemini",
            "display_name": "Gemini CLI",
            "command": "gemini",
            "installed": False,
        },
        {
            "name": "claude",
            "display_name": "Claude Code",
            "command": "claude",
            "installed": False,
        },
        {
            "name": "codex",
            "display_name": "Codex CLI",
            "command": "codex",
            "installed": False,
        },
    ]

    for provider in providers:
        provider["installed"] = shutil.which(provider["command"]) is not None

    return providers
