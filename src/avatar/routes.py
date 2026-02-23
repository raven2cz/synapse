"""
Avatar Engine API routes for Synapse.

Provides:
  - GET /status: Health check — is avatar-engine available?
  - GET /providers: List available AI CLI providers on this system
  - GET /config: Current avatar configuration (non-sensitive)

These routes work regardless of whether avatar-engine is installed.
When avatar-engine IS installed, additional routes are mounted by the engine itself.
"""

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter

from . import AVATAR_ENGINE_AVAILABLE, AVATAR_ENGINE_VERSION
from .config import detect_available_providers, load_avatar_config
from .skills import build_system_prompt, list_skills

logger = logging.getLogger(__name__)

avatar_router = APIRouter(tags=["avatar"])

# Lightweight config/provider cache (avoids re-reading YAML + shutil.which on every request)
_cache: Dict[str, Any] = {"config": None, "providers": None, "ts": 0.0}
_CACHE_TTL = 30.0  # seconds


def _get_cached_config():
    """Load config with a short TTL cache."""
    now = time.monotonic()
    if _cache["config"] is None or (now - _cache["ts"]) > _CACHE_TTL:
        _cache["config"] = load_avatar_config()
        _cache["providers"] = detect_available_providers()
        _cache["ts"] = now
    return _cache["config"], _cache["providers"]


def invalidate_avatar_cache() -> None:
    """Force cache refresh (e.g. after config change)."""
    _cache["config"] = None
    _cache["providers"] = None
    _cache["ts"] = 0.0


@avatar_router.get("/status")
def avatar_status() -> Dict[str, Any]:
    """
    Check avatar-engine availability and overall AI status.

    Always returns 200 — the availability info is in the response body.
    Frontend uses this to decide whether to show AI features.
    """
    config, providers = _get_cached_config()
    any_provider_installed = any(p["installed"] for p in providers)

    # Determine state (matches plan: STATE 1/2/3)
    if not config.enabled:
        state = "disabled"  # STATE 3: master switch OFF
    elif AVATAR_ENGINE_AVAILABLE and any_provider_installed:
        state = "ready"  # STATE 1: fully operational
    elif AVATAR_ENGINE_AVAILABLE:
        state = "no_provider"  # STATE 2 variant: engine OK but no CLI
    elif any_provider_installed:
        state = "no_engine"  # STATE 2 variant: CLI OK but no engine
    else:
        state = "setup_required"  # STATE 2: nothing installed

    return {
        "available": state == "ready",
        "state": state,
        "enabled": config.enabled,
        "engine_installed": AVATAR_ENGINE_AVAILABLE,
        "engine_version": AVATAR_ENGINE_VERSION,
        "active_provider": config.provider if state == "ready" else None,
        "safety": config.safety,
        "providers": providers,
    }


@avatar_router.get("/providers")
def avatar_providers() -> List[Dict[str, Any]]:
    """List available AI CLI providers on this system."""
    return detect_available_providers()


@avatar_router.get("/config")
def avatar_config_endpoint() -> Dict[str, Any]:
    """
    Get current avatar configuration (non-sensitive fields only).

    Used by Settings UI to populate the AI Assistant tab.
    """
    config, _ = _get_cached_config()
    skills = list_skills(config)
    return {
        "enabled": config.enabled,
        "provider": config.provider,
        "safety": config.safety,
        "max_history": config.max_history,
        "has_config_file": config.config_path is not None and config.config_path.exists(),
        "config_path": str(config.config_path) if config.config_path else None,
        "skills_count": {
            "builtin": len(skills["builtin"]),
            "custom": len(skills["custom"]),
        },
        "skills": skills,
        "provider_configs": {
            name: {"model": prov.model, "enabled": prov.enabled}
            for name, prov in config.providers.items()
        },
    }


@avatar_router.get("/skills")
def avatar_skills_endpoint() -> Dict[str, Any]:
    """List available skills with metadata."""
    config, _ = _get_cached_config()
    return list_skills(config)


def _count_skills(config) -> Dict[str, int]:
    """Count built-in and custom skills."""
    builtin = 0
    custom = 0

    if config.skills_dir and config.skills_dir.exists():
        builtin = len(list(config.skills_dir.glob("*.md")))
    if config.custom_skills_dir and config.custom_skills_dir.exists():
        custom = len(list(config.custom_skills_dir.glob("*.md")))

    return {"builtin": builtin, "custom": custom}


def try_mount_avatar_engine(app) -> bool:
    """
    Attempt to mount avatar-engine's WebSocket/REST API into the FastAPI app.

    Returns True if mounted successfully, False if avatar-engine not available.
    This is called from main.py during app initialization.
    """
    if not AVATAR_ENGINE_AVAILABLE:
        logger.info("Avatar Engine not installed — skipping mount")
        return False

    try:
        from avatar_engine.web import create_api_app as create_avatar_app

        config = load_avatar_config()
        if not config.enabled:
            logger.info("Avatar Engine disabled in config — skipping mount")
            return False

        system_prompt = build_system_prompt(config)

        avatar_app = create_avatar_app(
            provider=config.provider,
            config_path=str(config.config_path) if config.config_path else None,
            system_prompt=system_prompt,
        )
        app.mount("/api/avatar/engine", avatar_app)
        logger.info("Avatar Engine mounted at /api/avatar/engine")
        return True

    except Exception as e:
        logger.warning("Failed to mount Avatar Engine: %s", e)
        return False
