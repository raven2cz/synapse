"""
Avatar Engine API routes for Synapse.

Provides:
  - GET /status: Health check — is avatar-engine available?
  - GET /providers: List available AI CLI providers on this system
  - GET /config: Current avatar configuration (non-sensitive)

These routes work regardless of whether avatar-engine is installed.
When avatar-engine IS installed, additional routes are mounted by the engine itself.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body

from . import AVATAR_ENGINE_AVAILABLE, AVATAR_ENGINE_MIN_VERSION, AVATAR_ENGINE_VERSION, check_avatar_engine_compat
from .config import AvatarConfig, detect_available_providers, load_avatar_config
from .skills import build_system_prompt, list_skills

logger = logging.getLogger(__name__)

avatar_router = APIRouter(tags=["avatar"])

# Lightweight config/provider cache (avoids re-reading YAML + shutil.which on every request)
# Thread-safe: _cache_snapshot is replaced atomically (single reference assignment)
_cache_snapshot: Optional[Tuple[Any, Any, float]] = None  # (config, providers, timestamp)
_cache_lock = threading.Lock()
_CACHE_TTL = 30.0  # seconds


def _get_cached_config() -> Tuple[AvatarConfig, List[Dict[str, Any]]]:
    """Load config with a short TTL cache. Thread-safe.

    Never raises — returns safe defaults on failure (prevents 500 on all endpoints).
    """
    global _cache_snapshot
    snapshot = _cache_snapshot
    now = time.monotonic()
    if snapshot is not None and (now - snapshot[2]) <= _CACHE_TTL:
        return snapshot[0], snapshot[1]
    with _cache_lock:
        # Double-check after lock
        snapshot = _cache_snapshot
        if snapshot is not None and (now - snapshot[2]) <= _CACHE_TTL:
            return snapshot[0], snapshot[1]
        try:
            config = load_avatar_config()
            providers = detect_available_providers()
        except Exception as e:
            logger.error("Failed to load avatar config: %s — using defaults", e)
            config = AvatarConfig()
            providers = []
        _cache_snapshot = (config, providers, now)
        return config, providers


def invalidate_avatar_cache() -> None:
    """Force cache refresh (e.g. after config change)."""
    global _cache_snapshot
    with _cache_lock:
        _cache_snapshot = None
    logger.debug("Avatar config cache invalidated")


@avatar_router.get("/status")
def avatar_status() -> Dict[str, Any]:
    """
    Check avatar-engine availability and overall AI status.

    Always returns 200 — the availability info is in the response body.
    Frontend uses this to decide whether to show AI features.
    """
    config, providers = _get_cached_config()
    any_provider_installed = any(p["installed"] for p in providers)
    engine_compatible = check_avatar_engine_compat() if AVATAR_ENGINE_AVAILABLE else False

    # Determine state (matches plan: STATE 1/2/3)
    if not config.enabled:
        state = "disabled"  # STATE 3: master switch OFF
    elif AVATAR_ENGINE_AVAILABLE and engine_compatible and any_provider_installed:
        state = "ready"  # STATE 1: fully operational
    elif AVATAR_ENGINE_AVAILABLE and not engine_compatible:
        state = "incompatible"  # Engine installed but version too old
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
        "engine_min_version": AVATAR_ENGINE_MIN_VERSION,
        "active_provider": config.provider if state == "ready" else None,
        "safety": config.safety,
        "providers": providers,
    }


@avatar_router.get("/providers")
def avatar_providers() -> List[Dict[str, Any]]:
    """List available AI CLI providers on this system."""
    _, providers = _get_cached_config()
    return providers


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


@avatar_router.patch("/config")
def update_avatar_config(updates: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Update avatar configuration (enabled, default provider, provider settings).

    Accepts a partial update dict.  Allowed top-level keys:
      - enabled (bool): master AI toggle
      - provider (str): default provider for backend services
      - providers (dict): per-provider updates, e.g.
            {"gemini": {"enabled": true, "model": "gemini-3-pro-preview"}}
    Writes changes back to avatar.yaml and invalidates the config cache.
    """
    import yaml  # noqa: local import — yaml only needed for writes

    config = load_avatar_config()
    yaml_path = config.config_path
    if yaml_path is None:
        from .config import DEFAULT_SYNAPSE_ROOT
        yaml_path = DEFAULT_SYNAPSE_ROOT / "store" / "state" / "avatar.yaml"

    # Load raw YAML (or start from empty dict)
    raw: Dict[str, Any] = {}
    if yaml_path.exists():
        try:
            with open(yaml_path) as f:
                loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw = loaded
        except Exception:
            pass

    valid_providers = ("gemini", "claude", "codex")

    # Apply allowed updates
    if "enabled" in updates:
        raw["enabled"] = bool(updates["enabled"])

    if "provider" in updates:
        prov = str(updates["provider"])
        if prov in valid_providers:
            raw["provider"] = prov

    if "providers" in updates and isinstance(updates["providers"], dict):
        for prov_name, prov_updates in updates["providers"].items():
            if prov_name not in valid_providers or not isinstance(prov_updates, dict):
                continue
            # Ensure top-level provider section exists
            if prov_name not in raw or not isinstance(raw.get(prov_name), dict):
                raw[prov_name] = {}
            if "enabled" in prov_updates:
                raw[prov_name]["enabled"] = bool(prov_updates["enabled"])
            if "model" in prov_updates:
                raw[prov_name]["model"] = str(prov_updates["model"])

    # Write back
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(yaml_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Invalidate cache so next GET returns fresh data
    invalidate_avatar_cache()

    # Return updated config via the normal GET logic
    return avatar_config_endpoint()


@avatar_router.get("/skills")
def avatar_skills_endpoint() -> Dict[str, Any]:
    """List available skills with metadata."""
    config, _ = _get_cached_config()
    return list_skills(config)


# Built-in avatar IDs (shipped with avatar-engine)
BUILTIN_AVATARS = [
    {"id": "bella", "name": "Bella"},
    {"id": "heart", "name": "Heart"},
    {"id": "nicole", "name": "Nicole"},
    {"id": "sky", "name": "Sky"},
    {"id": "adam", "name": "Adam"},
    {"id": "michael", "name": "Michael"},
    {"id": "george", "name": "George"},
    {"id": "astronautka", "name": "Astronautka"},
]


@avatar_router.get("/avatars")
def avatar_avatars_endpoint() -> Dict[str, Any]:
    """
    List available avatars: built-in + custom.

    Custom avatars are subdirectories of avatars_dir containing avatar.json.
    """
    config, _ = _get_cached_config()

    builtin = [
        {"id": a["id"], "name": a["name"], "category": "builtin"}
        for a in BUILTIN_AVATARS
    ]

    custom = _list_custom_avatars(config.avatars_dir)

    return {"builtin": builtin, "custom": custom}


_MAX_AVATAR_JSON_SIZE = 1_048_576  # 1 MB guard


def _list_custom_avatars(avatars_dir: Optional[Path]) -> List[Dict[str, Any]]:
    """Scan avatars_dir for subdirectories containing avatar.json."""
    result: List[Dict[str, Any]] = []
    if avatars_dir is None or not avatars_dir.is_dir():
        return result

    for entry in sorted(avatars_dir.iterdir()):
        if entry.is_symlink() or not entry.is_dir():
            continue
        avatar_json = entry / "avatar.json"
        if not avatar_json.is_file():
            continue
        try:
            size = avatar_json.stat().st_size
            if size > _MAX_AVATAR_JSON_SIZE:
                logger.warning("Skipping oversized avatar.json in %s (%d bytes)", entry.name, size)
                continue
            data = json.loads(avatar_json.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            result.append({
                "id": entry.name,
                "name": data.get("name", entry.name),
                "category": "custom",
            })
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping custom avatar %s: %s", entry.name, e)

    return result


def try_mount_avatar_engine(app) -> bool:
    """
    Attempt to mount avatar-engine's WebSocket/REST API into the FastAPI app.

    Returns True if mounted successfully, False if avatar-engine not available.
    This is called from main.py during app initialization.
    """
    if not AVATAR_ENGINE_AVAILABLE:
        logger.info("Avatar Engine not installed — skipping mount")
        return False

    if not check_avatar_engine_compat():
        logger.warning("Avatar Engine version incompatible — skipping mount")
        return False

    try:
        from avatar_engine.web import create_api_app as create_avatar_app

        config = load_avatar_config()
        if not config.enabled:
            logger.info("Avatar Engine disabled in config — skipping mount")
            return False

        system_prompt = build_system_prompt(config)

        # Only pass config_path if the file actually exists — avatar-engine
        # raises FileNotFoundError for missing paths instead of using defaults.
        config_file = config.config_path
        avatar_app = create_avatar_app(
            provider=config.provider,
            config_path=str(config_file) if config_file and config_file.exists() else None,
            system_prompt=system_prompt,
        )
        app.mount("/api/avatar/engine", avatar_app)

        # Store manager reference on parent app so its lifespan can
        # initialize the engine (mounted sub-app lifespans are not
        # called automatically by Starlette).
        app.state.avatar_manager = getattr(avatar_app.state, "manager", None)

        logger.info("Avatar Engine mounted at /api/avatar/engine")
        return True

    except Exception as e:
        logger.warning("Failed to mount Avatar Engine: %s", e)
        return False
