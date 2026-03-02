"""
Abstract Base Task

Defines the interface that all AI tasks must implement.
Each task type has:
  - AI path: skill-based system prompt + structured JSON output
  - Semi-automatic fallback: rule-based / heuristic alternative
  - Manual path: GUI for manual input (handled by frontend)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple


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
    """Abstract base class for AI-powered tasks.

    Each task defines:
    - task_type: unique identifier (e.g., "parameter_extraction")
    - SKILL_NAMES: tuple of skill markdown files to include as domain knowledge
    - build_system_prompt(): combines task instructions with skills content
    - parse_result(): parses raw AI output into task-specific format
    - validate_output(): validates parsed output
    - get_fallback(): optional semi-automatic alternative (rule-based, heuristic)
    """

    # Task identifier (e.g., "parameter_extraction")
    task_type: str = ""

    # Immutable tuple of skill markdown file names (without .md extension)
    SKILL_NAMES: Tuple[str, ...] = ()

    @abstractmethod
    def build_system_prompt(self, skills_content: str) -> str:
        """Build complete system prompt: task instructions + skills knowledge.

        Args:
            skills_content: Concatenated markdown from skill files

        Returns:
            Complete system prompt for the AI engine
        """

    @abstractmethod
    def parse_result(self, raw_output: Dict[str, Any]) -> Any:
        """Parse and validate the AI response.

        Args:
            raw_output: Raw JSON output from AI provider

        Returns:
            Task-specific parsed result
        """

    def validate_output(self, output: Any) -> bool:
        """Validate task output.

        Default implementation accepts any non-None output.

        Args:
            output: Parsed output to validate

        Returns:
            True if valid
        """
        return output is not None

    def get_fallback(self) -> Optional[Callable[[str], "TaskResult"]]:
        """Return fallback function, or None if no semi-automatic alternative.

        The fallback receives the raw input string and returns a TaskResult.
        """
        return None

    def get_cache_prefix(self) -> str:
        """Return cache key prefix for this task type."""
        return self.task_type
