"""
Abstract Base Task

Defines the interface that all AI tasks must implement.
"""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TaskResult:
    """Result from an AI task execution."""

    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    provider_id: str = ""
    model: str = ""
    cached: bool = False
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "provider_id": self.provider_id,
            "model": self.model,
            "cached": self.cached,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


class AITask(ABC):
    """Abstract base class for AI-powered tasks."""

    # Task identifier (e.g., "parameter_extraction")
    task_type: str = ""

    @abstractmethod
    def build_prompt(self, input_data: Any) -> str:
        """
        Build the prompt for this task.

        Args:
            input_data: Task-specific input

        Returns:
            Prompt string for the AI provider
        """
        pass

    @abstractmethod
    def parse_result(self, raw_output: Dict[str, Any]) -> Any:
        """
        Parse and validate the AI response.

        Args:
            raw_output: Raw JSON output from AI provider

        Returns:
            Task-specific parsed result
        """
        pass

    @abstractmethod
    def get_raw_input(self, input_data: Any) -> str:
        """
        Get raw input for rule-based fallback.

        The rule-based provider doesn't use AI prompts,
        it needs the original input data.

        Args:
            input_data: Task-specific input

        Returns:
            Raw input for rule-based extraction
        """
        pass

    def get_cache_key(self, input_data: Any) -> str:
        """
        Generate cache key for input data.

        Default implementation uses SHA-256 hash.

        Args:
            input_data: Task-specific input

        Returns:
            16-character hex hash
        """
        content = str(input_data)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def validate_output(self, output: Any) -> bool:
        """
        Validate task output.

        Default implementation accepts any non-None output.

        Args:
            output: Parsed output to validate

        Returns:
            True if valid
        """
        return output is not None
