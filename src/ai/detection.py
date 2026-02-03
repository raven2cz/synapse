"""
Provider Detection

Auto-detection of available AI providers.
"""

import logging
from typing import Dict

from .providers import ProviderRegistry
from .providers.base import ProviderStatus

logger = logging.getLogger(__name__)


def detect_ai_providers() -> Dict[str, ProviderStatus]:
    """
    Detect which AI CLI tools are installed and accessible.

    Checks for:
    - Ollama: CLI installed and server running
    - Gemini: CLI installed
    - Claude: CLI installed
    - Rule-based: Always available

    Returns:
        Dict mapping provider_id to ProviderStatus
    """
    logger.info("[ai-service] Detecting AI providers...")

    results = ProviderRegistry.detect_all()

    # Log summary
    available = [pid for pid, status in results.items() if status.available]
    running = [pid for pid, status in results.items() if status.running]

    logger.info(
        f"[ai-service] Provider detection complete: "
        f"{len(available)} available, {len(running)} running"
    )

    for pid, status in results.items():
        if status.available and status.running:
            models = ", ".join(status.models[:3])
            if len(status.models) > 3:
                models += f", ... ({len(status.models)} total)"
            logger.info(f"[ai-service] ✓ {pid}: available, models: [{models}]")
        elif status.available:
            logger.info(f"[ai-service] ○ {pid}: available but not running")
        else:
            logger.debug(f"[ai-service] ✗ {pid}: not available ({status.error})")

    return results


def get_available_providers() -> Dict[str, ProviderStatus]:
    """
    Get only available and running providers.

    Returns:
        Dict of running providers with their status
    """
    all_providers = detect_ai_providers()
    return {
        pid: status
        for pid, status in all_providers.items()
        if status.available and status.running
    }


def check_provider(provider_id: str) -> ProviderStatus:
    """
    Check status of a specific provider.

    Args:
        provider_id: Provider to check

    Returns:
        ProviderStatus for the provider
    """
    provider = ProviderRegistry.get(provider_id)
    if provider is None:
        return ProviderStatus(
            provider_id=provider_id,
            available=False,
            error=f"Unknown provider: {provider_id}",
        )

    return provider.detect_availability()
