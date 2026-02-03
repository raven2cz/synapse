"""
Provider Registry

Dynamic provider registration and lookup.
Allows adding custom providers without modifying core code.
"""

import logging
from typing import Dict, Optional, Type

from .base import AIProvider, ProviderStatus
from .ollama import OllamaProvider
from .gemini import GeminiProvider
from .claude import ClaudeProvider
from .rule_based import RuleBasedProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for AI providers.

    Provides dynamic lookup and instantiation of providers.
    """

    # Built-in providers
    _providers: Dict[str, Type[AIProvider]] = {
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "rule_based": RuleBasedProvider,
    }

    @classmethod
    def register(cls, provider_id: str, provider_class: Type[AIProvider]) -> None:
        """
        Register a new provider.

        Args:
            provider_id: Unique identifier for the provider
            provider_class: Provider class (must extend AIProvider)
        """
        if not issubclass(provider_class, AIProvider):
            raise TypeError(f"{provider_class} must be a subclass of AIProvider")

        cls._providers[provider_id] = provider_class
        logger.info(f"[ai-service] Registered provider: {provider_id}")

    @classmethod
    def unregister(cls, provider_id: str) -> bool:
        """
        Unregister a provider.

        Args:
            provider_id: Provider to remove

        Returns:
            True if provider was removed, False if not found
        """
        if provider_id in cls._providers:
            del cls._providers[provider_id]
            return True
        return False

    @classmethod
    def get(
        cls,
        provider_id: str,
        model: str = "",
        endpoint: Optional[str] = None,
    ) -> Optional[AIProvider]:
        """
        Get a provider instance.

        Args:
            provider_id: Provider identifier
            model: Model to use
            endpoint: Optional endpoint (for Ollama)

        Returns:
            Provider instance or None if not found
        """
        provider_class = cls._providers.get(provider_id)
        if provider_class is None:
            logger.warning(f"[ai-service] Unknown provider: {provider_id}")
            return None

        return provider_class(model=model, endpoint=endpoint)

    @classmethod
    def list_providers(cls) -> list[str]:
        """
        List all registered provider IDs.

        Returns:
            List of provider identifiers
        """
        return list(cls._providers.keys())

    @classmethod
    def detect_all(cls) -> Dict[str, ProviderStatus]:
        """
        Detect availability of all registered providers.

        Returns:
            Dict mapping provider_id to ProviderStatus
        """
        results = {}
        for provider_id, provider_class in cls._providers.items():
            try:
                provider = provider_class()
                results[provider_id] = provider.detect_availability()
            except Exception as e:
                logger.error(f"[ai-service] Error detecting {provider_id}: {e}")
                results[provider_id] = ProviderStatus(
                    provider_id=provider_id,
                    available=False,
                    error=str(e),
                )

        return results

    @classmethod
    def get_available_providers(cls) -> Dict[str, ProviderStatus]:
        """
        Get only available providers.

        Returns:
            Dict of available providers with their status
        """
        all_providers = cls.detect_all()
        return {
            pid: status
            for pid, status in all_providers.items()
            if status.available
        }
