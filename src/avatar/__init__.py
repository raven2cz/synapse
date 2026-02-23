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
