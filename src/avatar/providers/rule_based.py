"""
Rule-Based Fallback Provider

Uses existing regexp-based parameter extraction as fallback.
No external dependencies, works offline.

Standalone implementation — does not depend on the legacy provider hierarchy.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RuleBasedResult:
    """Result from rule-based extraction."""

    success: bool
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0


class RuleBasedProvider:
    """
    Rule-based fallback provider using regexp extraction.

    Wraps the existing parameter_extractor.py implementation.
    Always available, no external dependencies.
    """

    provider_id = "rule_based"
    model = "regexp"

    def execute(self, description: str) -> RuleBasedResult:
        """
        Execute rule-based extraction on a description.

        Args:
            description: The description to extract parameters from

        Returns:
            RuleBasedResult with extracted parameters
        """
        start_time = time.time()

        try:
            logger.info("[ai-service] Task: executing, Provider: rule_based (regexp)")

            # Import here to avoid circular imports
            from src.utils.parameter_extractor import extract_from_description

            result = extract_from_description(description)
            output = self._normalize_result(result)
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"[ai-service] Extracted {len(output)} parameters (rule-based)"
            )

            return RuleBasedResult(
                success=True,
                output=output,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[ai-service] Rule-based extraction failed: {e}")
            return RuleBasedResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        """
        Normalize extraction result to dict format.

        Args:
            result: ExtractionResult from parameter_extractor

        Returns:
            Normalized dictionary of parameters
        """
        # ExtractionResult has a .parameters dict
        if hasattr(result, "parameters") and isinstance(result.parameters, dict):
            return result.parameters

        if isinstance(result, dict):
            return result

        # Last resort: convert to string dict
        return {"raw": str(result)}
