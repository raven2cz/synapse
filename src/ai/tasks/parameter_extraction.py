"""
Parameter Extraction Task

Extracts generation parameters from model descriptions.
"""

from typing import Any, Dict

from ..prompts import build_extraction_prompt
from .base import AITask


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

    def build_prompt(self, input_data: str) -> str:
        """
        Build extraction prompt.

        Args:
            input_data: Model description (may contain HTML)

        Returns:
            Complete prompt for AI provider
        """
        return build_extraction_prompt(input_data)

    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate extraction result.

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
        result = {
            k: v for k, v in raw_output.items() if not k.startswith("_")
        }

        return result

    def get_raw_input(self, input_data: str) -> str:
        """
        Get raw input for rule-based fallback.

        Args:
            input_data: Model description

        Returns:
            Same description (rule-based uses original input)
        """
        return input_data

    def validate_output(self, output: Any) -> bool:
        """
        Validate extraction output.

        Args:
            output: Parsed parameters

        Returns:
            True if output is a non-empty dict
        """
        return isinstance(output, dict) and len(output) > 0
