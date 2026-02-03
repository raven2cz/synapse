"""
Abstract Base Provider

Defines the interface that all AI providers must implement.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """Result from an AI provider execution."""

    success: bool
    output: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None
    provider_id: str = ""
    model: str = ""
    execution_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "raw_response": self.raw_response,
            "error": self.error,
            "provider_id": self.provider_id,
            "model": self.model,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ProviderStatus:
    """Status information about a provider."""

    provider_id: str
    available: bool
    running: bool = False
    version: Optional[str] = None
    models: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider_id": self.provider_id,
            "available": self.available,
            "running": self.running,
            "version": self.version,
            "models": self.models,
            "error": self.error,
        }


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    # Provider identifier (e.g., "ollama", "gemini", "claude")
    provider_id: str = ""

    def __init__(self, model: str = "", endpoint: Optional[str] = None):
        """
        Initialize the provider.

        Args:
            model: Model identifier to use
            endpoint: Optional custom endpoint (for Ollama)
        """
        self.model = model
        self.endpoint = endpoint

    @abstractmethod
    def detect_availability(self) -> ProviderStatus:
        """
        Check if this provider is available.

        Returns:
            ProviderStatus with availability information
        """
        pass

    @abstractmethod
    def execute(self, prompt: str, timeout: int = 60) -> ProviderResult:
        """
        Execute a prompt and return the result.

        Args:
            prompt: The prompt to execute
            timeout: Maximum execution time in seconds

        Returns:
            ProviderResult with the response or error
        """
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models for this provider.

        Returns:
            List of model identifiers
        """
        pass

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from AI response, handling various formats.

        AI models often:
        - Wrap JSON in markdown code fences (```json ... ```)
        - Add explanatory text before/after the JSON
        - Include thinking or commentary

        This parser tries multiple strategies to extract valid JSON.

        Args:
            response: Raw text response from AI provider

        Returns:
            Parsed dictionary

        Raises:
            json.JSONDecodeError: If no valid JSON found in response
        """
        text = response.strip()

        # Strategy 1: Try direct parse first (cleanest case)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code fences
        if "```" in text:
            # Find content between code fences
            import re
            # Match ```json or ``` followed by content and closing ```
            fence_pattern = r"```(?:json|JSON)?\s*\n?(.*?)\n?```"
            matches = re.findall(fence_pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

        # Strategy 3: Find JSON structure by looking for { or [ (whichever comes first)
        # This handles cases where AI adds text before/after JSON
        first_brace = text.find("{")
        first_bracket = text.find("[")

        # Determine which structure starts first
        if first_brace == -1 and first_bracket == -1:
            pass  # No JSON structure found, will raise error below
        else:
            # Try the structure that appears first in the text
            if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
                # Array appears first - parse array
                result = self._extract_json_structure(text, first_bracket, "[", "]")
                if result is not None:
                    return result
                # Fall through to try object
            if first_brace != -1:
                # Object appears first (or array parsing failed) - parse object
                result = self._extract_json_structure(text, first_brace, "{", "}")
                if result is not None:
                    return result

        # No valid JSON found - raise error with helpful context
        preview = text[:200] + "..." if len(text) > 200 else text
        raise json.JSONDecodeError(
            f"No valid JSON found in response. Preview: {preview}",
            text,
            0,
        )

    def _extract_json_structure(
        self, text: str, start: int, open_char: str, close_char: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract a JSON structure (object or array) from text.

        Handles nested structures and strings containing brackets.

        Args:
            text: The full text
            start: Starting position of the structure
            open_char: Opening bracket character ('{' or '[')
            close_char: Closing bracket character ('}' or ']')

        Returns:
            Parsed JSON or None if parsing fails
        """
        depth = 0
        in_string = False
        escape = False

        for i, char in enumerate(text[start:], start=start):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    json_str = text[start : i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        return None
        return None

    def _timed_execute(self, execute_fn) -> ProviderResult:
        """
        Wrapper to time execution and handle errors.

        Args:
            execute_fn: Function that performs the actual execution

        Returns:
            ProviderResult with timing information
        """
        start_time = time.time()
        try:
            result = execute_fn()
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[ai-service] Provider {self.provider_id} error: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider_id=self.provider_id,
                model=self.model,
                execution_time_ms=execution_time_ms,
            )
