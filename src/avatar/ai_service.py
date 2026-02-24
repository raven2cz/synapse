"""
Avatar AI Service

AI service using avatar-engine for parameter extraction.
Drop-in replacement for AIService with same public API.
"""

import json
import logging
import re
import threading
import time
from typing import Any, Dict, Optional

from src.ai.cache import AICache
from src.ai.prompts.parameter_extraction import PARAMETER_EXTRACTION_PROMPT
from src.ai.settings import AIServicesSettings
from src.ai.tasks.base import TaskResult
from src.ai.tasks.parameter_extraction import ParameterExtractionTask

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extract JSON from AI response text.

    Handles various formats: plain JSON, markdown code fences,
    text before/after JSON.

    Args:
        text: Raw text response from AI provider

    Returns:
        Parsed dictionary

    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code fences
    if "```" in text:
        fence_pattern = r"```(?:json|JSON)?\s*\n?(.*?)\n?```"
        matches = re.findall(fence_pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find JSON object by braces
    first_brace = text.find("{")
    if first_brace != -1:
        depth = 0
        in_string = False
        escape = False
        for i, char in enumerate(text[first_brace:], start=first_brace):
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
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    json_str = text[first_brace : i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        break

    preview = text[:200] + "..." if len(text) > 200 else text
    raise json.JSONDecodeError(
        f"No valid JSON found in response. Preview: {preview}",
        text,
        0,
    )


class AvatarAIService:
    """
    AI service using avatar-engine for parameter extraction.
    Drop-in replacement for AIService with same public API.
    """

    def __init__(self, settings: Optional[AIServicesSettings] = None):
        """
        Initialize Avatar AI service.

        Args:
            settings: Service configuration (loads from disk if not provided)
        """
        self.settings = settings or AIServicesSettings.load()
        self.cache = AICache(
            cache_dir=self.settings.cache_directory,
            ttl_days=self.settings.cache_ttl_days,
        )
        self._engine = None
        self._engine_lock = threading.Lock()
        self._task = ParameterExtractionTask()

    def extract_parameters(
        self,
        description: str,
        use_cache: bool = True,
    ) -> TaskResult:
        """
        Extract generation parameters from description using avatar-engine.

        Args:
            description: Model description
            use_cache: Whether to use caching

        Returns:
            TaskResult with extracted parameters
        """
        if not description or not description.strip():
            return TaskResult(
                success=False,
                error="Empty description",
            )

        cache_content = f"parameter_extraction:{description}"
        provider_label = f"avatar:{self.settings.avatar_engine_provider}"

        # Check cache
        if use_cache and self.settings.cache_enabled:
            cached = self.cache.get(cache_content)
            if cached:
                logger.info(
                    f"[avatar-ai] Cache hit for key: {cached.key} "
                    f"(age: {cached.age_days():.1f}d)"
                )
                parsed = self._task.parse_result(cached.result)

                if self.settings.show_provider_in_results and isinstance(parsed, dict):
                    parsed["_extracted_by"] = cached.provider_id
                    parsed["_ai_fields"] = [
                        k for k in parsed.keys() if not k.startswith("_")
                    ]

                return TaskResult(
                    success=True,
                    output=parsed,
                    provider_id=cached.provider_id,
                    model=cached.model,
                    cached=True,
                    execution_time_ms=cached.execution_time_ms,
                )

        # Execute via avatar-engine
        start_time = time.time()
        try:
            engine = self._get_engine()
            response = engine.chat_sync(description)
            execution_time_ms = int((time.time() - start_time) * 1000)

            if not response.success:
                raise RuntimeError(response.error or "Avatar engine returned error")

            # Parse JSON from response
            raw_output = _extract_json(response.content)
            parsed = self._task.parse_result(raw_output)

            if not self._task.validate_output(parsed):
                raise ValueError("Output validation failed: empty or invalid result")

            model_name = self.settings.avatar_engine_model or "default"

            logger.info(
                f"[avatar-ai] Response received in "
                f"{execution_time_ms / 1000:.1f}s, "
                f"extracted {len(parsed)} parameters via {provider_label}"
            )

            # Add tracking metadata
            if self.settings.show_provider_in_results and isinstance(parsed, dict):
                parsed["_extracted_by"] = provider_label
                parsed["_ai_fields"] = [
                    k for k in parsed.keys() if not k.startswith("_")
                ]

            # Cache result
            if use_cache and self.settings.cache_enabled:
                self.cache.set(
                    content=cache_content,
                    result=parsed,
                    provider_id=provider_label,
                    model=model_name,
                    execution_time_ms=execution_time_ms,
                )

            return TaskResult(
                success=True,
                output=parsed,
                provider_id=provider_label,
                model=model_name,
                cached=False,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"[avatar-ai] Extraction failed: {e}")

            # Fallback to rule-based
            if self.settings.always_fallback_to_rule_based:
                logger.info("[avatar-ai] Falling back to rule-based extraction")
                return self._execute_rule_based(description)

            return TaskResult(
                success=False,
                error=str(e),
                provider_id=provider_label,
                execution_time_ms=execution_time_ms,
            )

    def _execute_rule_based(self, description: str) -> TaskResult:
        """Execute rule-based fallback extraction."""
        from src.ai.providers import ProviderRegistry

        provider = ProviderRegistry.get("rule_based")
        if not provider:
            return TaskResult(
                success=False,
                error="Rule-based provider not available",
            )

        result = provider.execute(description)

        if result.success and result.output:
            parsed = self._task.parse_result(result.output)

            if self.settings.show_provider_in_results and isinstance(parsed, dict):
                parsed["_extracted_by"] = "rule_based"
                parsed["_ai_fields"] = [
                    k for k in parsed.keys() if not k.startswith("_")
                ]

            return TaskResult(
                success=True,
                output=parsed,
                provider_id="rule_based",
                model="regexp",
                cached=False,
                execution_time_ms=result.execution_time_ms,
            )

        return TaskResult(
            success=False,
            error=result.error or "Rule-based extraction failed",
            provider_id="rule_based",
        )

    def _get_engine(self):
        """Lazy singleton engine with guard import. Thread-safe."""
        if self._engine is not None:
            return self._engine

        with self._engine_lock:
            # Double-check after acquiring lock
            if self._engine is not None:
                return self._engine

            try:
                from avatar_engine import AvatarEngine
            except ImportError:
                raise ImportError(
                    "avatar-engine is not installed. "
                    "Install it with: uv pip install -e ~/git/github/avatar-engine"
                )

            engine = AvatarEngine(
                provider=self.settings.avatar_engine_provider,
                model=self.settings.avatar_engine_model or None,
                system_prompt=PARAMETER_EXTRACTION_PROMPT,
                timeout=self.settings.avatar_engine_timeout,
                safety_instructions="unrestricted",
            )
            engine.start_sync()
            self._engine = engine
            logger.info(
                f"[avatar-ai] Engine started: "
                f"provider={self.settings.avatar_engine_provider}, "
                f"model={self.settings.avatar_engine_model or 'default'}"
            )

        return self._engine

    def shutdown(self) -> None:
        """Stop engine if running. Thread-safe."""
        with self._engine_lock:
            if self._engine:
                try:
                    self._engine.stop_sync()
                except Exception as e:
                    logger.warning(f"[avatar-ai] Error stopping engine: {e}")
                self._engine = None
                logger.info("[avatar-ai] Engine stopped")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.stats()

    def clear_cache(self) -> int:
        """Clear all cached results."""
        return self.cache.clear()

    def cleanup_cache(self) -> int:
        """Remove expired cache entries."""
        return self.cache.cleanup_expired()
