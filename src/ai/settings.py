"""
AI Services Settings

Configuration models for AI providers and task priorities.
Uses str instead of Enum for flexibility - new providers/tasks can be added without code changes.
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Settings file path
def _get_settings_path() -> Path:
    """Get path to AI settings file."""
    root = Path(os.environ.get("SYNAPSE_ROOT", Path.home() / ".synapse" / "store"))
    return root / "data" / "ai_settings.json"


# Avatar Engine CLI binaries in preference order
_AVATAR_CLI_MAP = {
    "gemini": "gemini",
    "claude": "claude",
    "codex": "codex",
}


def _detect_avatar_engine() -> Tuple[bool, str]:
    """
    Detect if avatar-engine is available and find best provider CLI.

    Checks:
    1. avatar_engine package is importable
    2. At least one supported CLI (gemini, claude, codex) is in PATH

    Returns:
        (available, best_provider) — e.g. (True, "gemini") or (False, "gemini")
    """
    # Check if avatar-engine is installed
    try:
        import avatar_engine  # noqa: F401
    except ImportError:
        return False, "gemini"

    # Check for CLI binaries in preference order
    for provider, binary in _AVATAR_CLI_MAP.items():
        if shutil.which(binary):
            logger.debug(f"[ai-settings] Avatar engine available: {provider} ({binary})")
            return True, provider

    logger.debug("[ai-settings] Avatar engine installed but no CLI found in PATH")
    return False, "gemini"


# Cached result of auto-detection (runs once at import time)
_AVATAR_DEFAULTS: Tuple[bool, str] = _detect_avatar_engine()


# Well-known providers (for UI hints, but not restricting)
KNOWN_PROVIDERS = ["ollama", "gemini", "claude", "rule_based"]

# Well-known task types
KNOWN_TASKS = [
    "parameter_extraction",
    "description_translation",
    "auto_tagging",
    "workflow_generation",
    "model_compatibility",
    "preview_analysis",
    "config_migration",
]

# Default models per provider (from benchmark results)
DEFAULT_MODELS = {
    "ollama": "qwen2.5:14b",
    "gemini": "gemini-3-pro-preview",
    "claude": "claude-sonnet-4-20250514",
}


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""

    provider_id: str  # e.g., "ollama", "gemini", "my_custom_provider"
    enabled: bool = False
    model: str = ""  # Selected model
    available_models: List[str] = field(default_factory=list)
    endpoint: Optional[str] = None  # Custom endpoint (Ollama)
    extra_args: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "provider_id": self.provider_id,
            "enabled": self.enabled,
            "model": self.model,
            "available_models": self.available_models,
            "endpoint": self.endpoint,
            "extra_args": self.extra_args,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderConfig":
        """Create from dictionary."""
        return cls(
            provider_id=data.get("provider_id", ""),
            enabled=data.get("enabled", False),
            model=data.get("model", ""),
            available_models=data.get("available_models", []),
            endpoint=data.get("endpoint"),
            extra_args=data.get("extra_args", {}),
        )


@dataclass
class TaskPriorityConfig:
    """Priority chain for a specific task type."""

    task_type: str  # e.g., "parameter_extraction"
    provider_order: List[str] = field(default_factory=list)  # Provider IDs in order
    custom_timeout: Optional[int] = None  # Override global timeout
    custom_prompt: Optional[str] = None  # Override default prompt template

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_type": self.task_type,
            "provider_order": self.provider_order,
            "custom_timeout": self.custom_timeout,
            "custom_prompt": self.custom_prompt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPriorityConfig":
        """Create from dictionary."""
        return cls(
            task_type=data.get("task_type", ""),
            provider_order=data.get("provider_order", []),
            custom_timeout=data.get("custom_timeout"),
            custom_prompt=data.get("custom_prompt"),
        )


@dataclass
class AIServicesSettings:
    """
    Complete AI services configuration.

    Stored in: settings.json under "ai_services" key
    """

    # Master switch
    enabled: bool = True

    # Provider configurations (key = provider_id)
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)

    # Task-specific priorities (key = task_type)
    task_priorities: Dict[str, TaskPriorityConfig] = field(default_factory=dict)

    # Advanced settings
    cli_timeout_seconds: int = 60
    max_retries: int = 2
    retry_delay_seconds: int = 1

    # Caching
    cache_enabled: bool = True
    cache_ttl_days: int = 30
    cache_directory: str = "~/.synapse/store/data/cache/ai"

    # Behavior
    always_fallback_to_rule_based: bool = True
    show_provider_in_results: bool = True

    # Logging
    log_requests: bool = True
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_prompts: bool = False  # Verbose: log full prompts
    log_responses: bool = False  # Verbose: log raw responses

    # Avatar Engine integration (auto-detected at startup, overridable)
    use_avatar_engine: bool = False  # Overridden by get_defaults() / from_dict()
    avatar_engine_provider: str = "gemini"  # "gemini" | "claude" | "codex"
    avatar_engine_model: str = ""  # Empty = provider default
    avatar_engine_timeout: int = 120  # Seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "enabled": self.enabled,
            "providers": {k: v.to_dict() for k, v in self.providers.items()},
            "task_priorities": {k: v.to_dict() for k, v in self.task_priorities.items()},
            "cli_timeout_seconds": self.cli_timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "cache_enabled": self.cache_enabled,
            "cache_ttl_days": self.cache_ttl_days,
            "cache_directory": self.cache_directory,
            "always_fallback_to_rule_based": self.always_fallback_to_rule_based,
            "show_provider_in_results": self.show_provider_in_results,
            "log_requests": self.log_requests,
            "log_level": self.log_level,
            "log_prompts": self.log_prompts,
            "log_responses": self.log_responses,
            "use_avatar_engine": self.use_avatar_engine,
            "avatar_engine_provider": self.avatar_engine_provider,
            "avatar_engine_model": self.avatar_engine_model,
            "avatar_engine_timeout": self.avatar_engine_timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIServicesSettings":
        """Create from dictionary."""
        providers = {}
        for k, v in data.get("providers", {}).items():
            providers[k] = ProviderConfig.from_dict(v)

        task_priorities = {}
        for k, v in data.get("task_priorities", {}).items():
            task_priorities[k] = TaskPriorityConfig.from_dict(v)

        return cls(
            enabled=data.get("enabled", True),
            providers=providers,
            task_priorities=task_priorities,
            cli_timeout_seconds=data.get("cli_timeout_seconds", 60),
            max_retries=data.get("max_retries", 2),
            retry_delay_seconds=data.get("retry_delay_seconds", 1),
            cache_enabled=data.get("cache_enabled", True),
            cache_ttl_days=data.get("cache_ttl_days", 30),
            cache_directory=data.get("cache_directory", "~/.synapse/store/data/cache/ai"),
            always_fallback_to_rule_based=data.get("always_fallback_to_rule_based", True),
            show_provider_in_results=data.get("show_provider_in_results", True),
            log_requests=data.get("log_requests", True),
            log_level=data.get("log_level", "INFO"),
            log_prompts=data.get("log_prompts", False),
            log_responses=data.get("log_responses", False),
            use_avatar_engine=data.get("use_avatar_engine", _AVATAR_DEFAULTS[0]),
            avatar_engine_provider=data.get("avatar_engine_provider", _AVATAR_DEFAULTS[1]),
            avatar_engine_model=data.get("avatar_engine_model", ""),
            avatar_engine_timeout=data.get("avatar_engine_timeout", 120),
        )

    @classmethod
    def get_defaults(cls) -> "AIServicesSettings":
        """Get default settings with standard provider configurations."""
        settings = cls()

        # Auto-detect avatar-engine availability
        settings.use_avatar_engine = _AVATAR_DEFAULTS[0]
        settings.avatar_engine_provider = _AVATAR_DEFAULTS[1]

        # Default provider configs
        settings.providers = {
            "ollama": ProviderConfig(
                provider_id="ollama",
                enabled=True,
                model="qwen2.5:14b",
                available_models=["qwen2.5:14b", "qwen2.5:7b", "llama3.1:8b"],
                endpoint="http://localhost:11434",
            ),
            "gemini": ProviderConfig(
                provider_id="gemini",
                enabled=True,
                model="gemini-3-pro-preview",
                available_models=[
                    "gemini-3-pro-preview",
                    "gemini-3-flash-preview",
                    "gemini-2.5-pro",
                    "gemini-2.5-flash",
                ],
            ),
            "claude": ProviderConfig(
                provider_id="claude",
                enabled=False,  # Disabled by default to save quota
                model="claude-sonnet-4-20250514",
                available_models=[
                    "claude-sonnet-4-20250514",
                    "claude-haiku-4-5-20251001",
                    "claude-opus-4-5-20251101",
                ],
            ),
        }

        # Default task priorities (based on benchmark results)
        settings.task_priorities = {
            "parameter_extraction": TaskPriorityConfig(
                task_type="parameter_extraction",
                provider_order=["ollama", "gemini", "claude"],
            ),
            "description_translation": TaskPriorityConfig(
                task_type="description_translation",
                provider_order=["ollama", "gemini"],
            ),
        }

        return settings

    def get_provider_order(self, task_type: str) -> List[str]:
        """Get provider order for a task, falling back to defaults."""
        if task_type in self.task_priorities:
            return self.task_priorities[task_type].provider_order

        # Default order based on benchmark results
        return ["ollama", "gemini", "claude"]

    def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get list of enabled provider configurations."""
        return [p for p in self.providers.values() if p.enabled]

    def save(self) -> bool:
        """
        Save settings to disk.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            settings_path = _get_settings_path()
            settings_path.parent.mkdir(parents=True, exist_ok=True)

            with open(settings_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)

            logger.info(f"[ai-service] Settings saved to {settings_path}")
            return True
        except Exception as e:
            logger.error(f"[ai-service] Failed to save settings: {e}")
            return False

    @classmethod
    def load(cls) -> "AIServicesSettings":
        """
        Load settings from disk, or return defaults if not found.

        Returns:
            Loaded settings or defaults
        """
        settings_path = _get_settings_path()

        if settings_path.exists():
            try:
                with open(settings_path) as f:
                    data = json.load(f)
                logger.info(f"[ai-service] Settings loaded from {settings_path}")
                return cls.from_dict(data)
            except Exception as e:
                logger.warning(f"[ai-service] Failed to load settings, using defaults: {e}")

        return cls.get_defaults()

    @classmethod
    def load_or_create(cls) -> "AIServicesSettings":
        """
        Load settings from disk, or create defaults and save them.

        Returns:
            Loaded or newly created settings
        """
        settings = cls.load()

        # If settings file doesn't exist, save defaults
        settings_path = _get_settings_path()
        if not settings_path.exists():
            settings.save()

        return settings
