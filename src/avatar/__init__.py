"""
Avatar Engine integration for Synapse.

Provides AI assistant capabilities via avatar-engine library.
All features gracefully degrade when avatar-engine is not installed.

Structure:
  - config.py: Configuration loading (avatar.yaml)
  - mcp/: MCP servers for Synapse tools (store, import, workflow, deps)
"""

import logging

logger = logging.getLogger(__name__)

AVATAR_ENGINE_MIN_VERSION = "1.0.0"

# Check avatar-engine availability at import time
try:
    import avatar_engine  # noqa: F401
    AVATAR_ENGINE_AVAILABLE = True
    AVATAR_ENGINE_VERSION = getattr(avatar_engine, "__version__", "unknown")
    logger.debug(f"avatar-engine v{AVATAR_ENGINE_VERSION} available")
except ImportError:
    AVATAR_ENGINE_AVAILABLE = False
    AVATAR_ENGINE_VERSION = None
    logger.debug("avatar-engine not installed — AI avatar features disabled")


def check_avatar_engine_compat() -> bool:
    """Check if installed avatar-engine meets the minimum version requirement.

    Returns True if version is compatible, False otherwise.
    Logs a warning when the installed version is below minimum.
    """
    if not AVATAR_ENGINE_AVAILABLE or not AVATAR_ENGINE_VERSION:
        return False
    if AVATAR_ENGINE_VERSION == "unknown":
        logger.warning("avatar-engine version unknown — cannot verify compatibility")
        return False
    try:
        from packaging.version import Version

        if Version(AVATAR_ENGINE_VERSION) < Version(AVATAR_ENGINE_MIN_VERSION):
            logger.warning(
                "avatar-engine %s is below minimum %s — upgrade recommended",
                AVATAR_ENGINE_VERSION,
                AVATAR_ENGINE_MIN_VERSION,
            )
            return False
    except Exception:
        logger.warning(
            "Cannot verify avatar-engine version '%s' — treating as incompatible",
            AVATAR_ENGINE_VERSION,
        )
        return False
    return True
