"""
AI Services Module

Provides AI-powered functionality for Synapse using CLI-based providers:
- Ollama (local, GPU-accelerated)
- Gemini CLI (cloud, Google AI)
- Claude Code (cloud, Anthropic)

Falls back to rule-based extraction when AI is unavailable.

When use_avatar_engine is enabled, uses avatar-engine library instead of
CLI-based providers for gemini/claude/codex.
"""

import threading
from typing import Optional, Union

from .service import AIService
from .settings import AIServicesSettings, ProviderConfig, TaskPriorityConfig
from .detection import detect_ai_providers
from .cache import AICache

# Singleton cache for AI service instances (avoids engine process leaks)
_ai_service_instance: Optional[Union[AIService, "AvatarAIService"]] = None
_ai_service_lock = threading.Lock()


def get_ai_service(
    settings: Optional[AIServicesSettings] = None,
) -> Union[AIService, "AvatarAIService"]:
    """
    Return appropriate AI service based on settings.

    Uses singleton pattern to avoid creating multiple engine processes.
    When use_avatar_engine is enabled, returns AvatarAIService
    (avatar-engine library). Otherwise returns classic AIService
    (CLI-based providers).

    When settings are explicitly provided, always creates a fresh instance
    (for testing and per-request configuration). When settings=None,
    returns a cached singleton.

    Args:
        settings: Optional settings (loads from disk if not provided)

    Returns:
        AIService or AvatarAIService instance
    """
    global _ai_service_instance

    # Explicit settings = fresh instance (tests, custom config)
    if settings is not None:
        if settings.use_avatar_engine:
            from src.avatar.ai_service import AvatarAIService

            return AvatarAIService(settings)
        return AIService(settings)

    # Singleton path (default settings from disk)
    if _ai_service_instance is not None:
        return _ai_service_instance

    with _ai_service_lock:
        if _ai_service_instance is not None:
            return _ai_service_instance

        loaded = AIServicesSettings.load()
        if loaded.use_avatar_engine:
            from src.avatar.ai_service import AvatarAIService

            _ai_service_instance = AvatarAIService(loaded)
        else:
            _ai_service_instance = AIService(loaded)

    return _ai_service_instance


__all__ = [
    "AIService",
    "AIServicesSettings",
    "ProviderConfig",
    "TaskPriorityConfig",
    "detect_ai_providers",
    "AICache",
    "get_ai_service",
]
