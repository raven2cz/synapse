"""
Parameter Extraction Task

Extracts generation parameters from model descriptions.
"""

from typing import Any, Callable, Dict, Optional

from ..prompts.parameter_extraction import PARAMETER_EXTRACTION_PROMPT
from .base import AITask, TaskResult


class ParameterExtractionTask(AITask):
    """
    Task for extracting generation parameters from descriptions.

    Uses Prompt V2 optimized for:
    - snake_case key naming
    - Flat structure (no unnecessary nesting)
    - Numeric ranges as {min, max}
    - No hallucinated base_model
    """

    task_type = "parameter_extraction"
    SKILL_NAMES = ("generation-params",)

    def build_system_prompt(self, skills_content: str) -> str:
        """Build V2 extraction prompt with optional skills knowledge.

        Args:
            skills_content: Concatenated markdown from skill files

        Returns:
            Complete system prompt for parameter extraction
        """
        prompt = PARAMETER_EXTRACTION_PROMPT
        if skills_content.strip():
            prompt += f"\n\n---\n\n# Reference Knowledge\n\n{skills_content}"
        return prompt

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate extraction result.

        Performs basic validation and normalization:
        - Ensures output is a dict
        - Removes any internal keys (starting with _)

        Args:
            raw_output: Raw JSON output from AI provider

        Returns:
            Cleaned parameter dictionary
        """
        if not isinstance(raw_output, dict):
            return {}

        # Remove internal keys
        return {
            k: v for k, v in raw_output.items() if not k.startswith("_")
        }

    def validate_output(self, output: Any) -> bool:
        """Validate extraction output.

        Args:
            output: Parsed parameters

        Returns:
            True if output is a non-empty dict
        """
        return isinstance(output, dict) and len(output) > 0

    def get_fallback(self) -> Optional[Callable[[str], TaskResult]]:
        """Return rule-based regexp fallback for parameter extraction."""

        def _fallback(description: str) -> TaskResult:
            from ..providers.rule_based import RuleBasedProvider

            provider = RuleBasedProvider()
            result = provider.execute(description)
            if result.success and result.output:
                parsed = self.parse_result(result.output)
                return TaskResult(
                    success=True,
                    output=parsed,
                    provider_id="rule_based",
                    model="regexp",
                    execution_time_ms=result.execution_time_ms,
                )
            return TaskResult(
                success=False,
                error=result.error or "Rule-based extraction failed",
                provider_id="rule_based",
            )

        return _fallback
