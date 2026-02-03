"""
Rule-Based Fallback Provider

Uses existing regexp-based parameter extraction as fallback.
No external dependencies, works offline.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import AIProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class RuleBasedProvider(AIProvider):
    """
    Rule-based fallback provider using regexp extraction.

    Wraps the existing parameter_extractor.py implementation.
    Always available, no external dependencies.
    """

    provider_id = "rule_based"

    def __init__(self, model: str = "regexp", endpoint: Optional[str] = None):
        """
        Initialize rule-based provider.

        Args:
            model: Always "regexp" for this provider
            endpoint: Not used
        """
        super().__init__(model="regexp", endpoint=None)

    def detect_availability(self) -> ProviderStatus:
        """
        Rule-based is always available.

        Returns:
            ProviderStatus (always available)
        """
        return ProviderStatus(
            provider_id=self.provider_id,
            available=True,
            running=True,
            version="1.0",
            models=["regexp"],
        )

    def execute(self, prompt: str, timeout: int = 60) -> ProviderResult:
        """
        Execute rule-based extraction.

        Note: This provider ignores the prompt format and expects
        the raw description to be passed. The AIService handles
        this by passing the original description for rule_based.

        Args:
            prompt: The description to extract from (not the AI prompt)
            timeout: Not used for rule-based

        Returns:
            ProviderResult with extracted parameters
        """

        def _execute():
            logger.info("[ai-service] Task: executing, Provider: rule_based (regexp)")

            try:
                # Import here to avoid circular imports
                from src.utils.parameter_extractor import (
                    ParameterExtractor,
                )

                extractor = ParameterExtractor()

                # Extract parameters from the description
                # Note: For rule_based, we expect the raw description, not the AI prompt
                result = extractor.extract(prompt)

                # Convert to dict format expected by the system
                output = self._normalize_result(result)

                logger.info(
                    f"[ai-service] Extracted {len(output)} parameters (rule-based)"
                )

                return ProviderResult(
                    success=True,
                    output=output,
                    raw_response=None,
                    provider_id=self.provider_id,
                    model=self.model,
                )

            except Exception as e:
                logger.error(f"[ai-service] Rule-based extraction failed: {e}")
                return ProviderResult(
                    success=False,
                    error=str(e),
                    provider_id=self.provider_id,
                    model=self.model,
                )

        return self._timed_execute(_execute)

    def list_models(self) -> List[str]:
        """
        List available models (always just regexp).

        Returns:
            ["regexp"]
        """
        return ["regexp"]

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        """
        Normalize extraction result to dict format.

        The ParameterExtractor may return different formats,
        this ensures consistent dict output.

        Args:
            result: Result from ParameterExtractor

        Returns:
            Normalized dictionary
        """
        if isinstance(result, dict):
            return result

        # If it's a dataclass or object with __dict__
        if hasattr(result, "__dict__"):
            return {k: v for k, v in result.__dict__.items() if not k.startswith("_")}

        # If it's a NamedTuple or similar
        if hasattr(result, "_asdict"):
            return result._asdict()

        # Last resort: convert to string dict
        return {"raw": str(result)}
