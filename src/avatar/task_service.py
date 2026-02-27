"""
Avatar Task Service

Multi-task AI service using avatar-engine. Supports any registered task type
with unified interface: AI execution -> fallback -> error.

Thread-safe: a single lock covers engine lifecycle + chat_sync() calls.
Concurrent requests with different task types are serialized.
"""

import json
import logging
import re
import threading
import time
from typing import Any, Dict, Optional

from .cache import AICache
from .config import AvatarConfig, load_avatar_config
from .tasks.base import AITask, TaskResult
from .tasks.registry import TaskRegistry, get_default_registry

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


class AvatarTaskService:
    """
    Multi-task AI service using avatar-engine.

    Supports any registered task type with a unified interface:
    1. Cache check
    2. AI execution via avatar-engine with task-specific system prompt
    3. Fallback to semi-automatic (rule-based) if AI fails
    4. Error result if all paths fail

    Thread-safe: a single lock covers engine + chat_sync().
    """

    def __init__(
        self,
        config: Optional[AvatarConfig] = None,
        registry: Optional[TaskRegistry] = None,
    ):
        self.config = config or load_avatar_config()
        self.registry = registry or get_default_registry()
        ext = self.config.extraction
        self.cache = AICache(
            cache_dir=ext.cache_directory,
            ttl_days=ext.cache_ttl_days,
        )
        self._engine = None
        self._engine_lock = threading.Lock()
        self._current_task_type: Optional[str] = None

    @property
    def _provider(self) -> str:
        """Active provider name."""
        return self.config.provider

    @property
    def _model(self) -> str:
        """Active model name from provider config."""
        prov = self.config.providers.get(self.config.provider)
        return prov.model if prov else ""

    def execute_task(
        self,
        task_type: str,
        input_data: str,
        use_cache: bool = True,
    ) -> TaskResult:
        """Execute any registered task type. Thread-safe.

        Args:
            task_type: Registered task type name
            input_data: Raw input for the task
            use_cache: Whether to check/store cache

        Returns:
            TaskResult with output or error
        """
        task = self.registry.get(task_type)
        if task is None:
            return TaskResult(success=False, error=f"Unknown task type: {task_type}")

        if not input_data or not input_data.strip():
            return TaskResult(success=False, error="Empty input")

        model_name = self._model or "default"
        cache_content = f"{task.get_cache_prefix()}:{self._provider}:{model_name}:{input_data}"
        provider_label = f"avatar:{self._provider}"
        ext = self.config.extraction

        # 1. Cache check (outside lock -- read-only, thread-safe)
        #    Cache stores already-parsed output (no parse_result on hit).
        if use_cache and ext.cache_enabled:
            cached = self.cache.get(cache_content)
            if cached:
                logger.debug(
                    "[task-service] Cache hit for %s (age: %.1fd)",
                    task_type,
                    cached.age_days(),
                )
                output = self._enrich_output(cached.result, cached.provider_id)
                return TaskResult(
                    success=True,
                    output=output,
                    provider_id=cached.provider_id,
                    model=cached.model,
                    cached=True,
                    execution_time_ms=cached.execution_time_ms,
                )

        # 2. AI execution (lock covers engine + chat_sync)
        start_time = time.time()
        last_error: Optional[Exception] = None

        with self._engine_lock:
            # Double-call race guard: re-check cache after acquiring lock
            if use_cache and ext.cache_enabled:
                cached = self.cache.get(cache_content)
                if cached:
                    output = self._enrich_output(cached.result, cached.provider_id)
                    return TaskResult(
                        success=True,
                        output=output,
                        provider_id=cached.provider_id,
                        model=cached.model,
                        cached=True,
                        execution_time_ms=cached.execution_time_ms,
                    )

            try:
                engine = self._ensure_engine_for_task(task)
                response = engine.chat_sync(input_data)
                execution_time_ms = int((time.time() - start_time) * 1000)

                if not response.success:
                    raise RuntimeError(response.error or "Engine error")

                raw_output = _extract_json(response.content)
                parsed = task.parse_result(raw_output)

                if not task.validate_output(parsed):
                    raise ValueError("Output validation failed: empty or invalid result")

                logger.info(
                    "[task-service] %s completed in %.1fs via %s",
                    task_type,
                    execution_time_ms / 1000,
                    provider_label,
                )

                # Cache clean data (without _ metadata)
                if use_cache and ext.cache_enabled:
                    self.cache.set(
                        content=cache_content,
                        result=parsed,
                        provider_id=provider_label,
                        model=model_name,
                        execution_time_ms=execution_time_ms,
                    )

                # Add tracking metadata AFTER caching
                output = self._enrich_output(parsed, provider_label)
                return TaskResult(
                    success=True,
                    output=output,
                    provider_id=provider_label,
                    model=model_name,
                    cached=False,
                    execution_time_ms=execution_time_ms,
                )

            except Exception as e:
                execution_time_ms = int((time.time() - start_time) * 1000)
                last_error = e
                logger.warning("[task-service] %s AI failed: %s", task_type, e)

        # 3. Fallback (outside lock -- doesn't need engine)
        fallback = task.get_fallback()
        if fallback:
            logger.info("[task-service] %s falling back to semi-automatic", task_type)
            try:
                fb_result = fallback(input_data)
                if fb_result.success and isinstance(fb_result.output, dict):
                    fb_result.output = self._enrich_output(
                        fb_result.output, fb_result.provider_id or "fallback"
                    )
                return fb_result
            except Exception as fb_err:
                logger.warning("[task-service] %s fallback failed: %s", task_type, fb_err)
                return TaskResult(
                    success=False,
                    error=f"AI failed: {last_error}; Fallback failed: {fb_err}",
                    provider_id=provider_label,
                    execution_time_ms=execution_time_ms,
                )

        return TaskResult(
            success=False,
            error=str(last_error),
            provider_id=provider_label,
            execution_time_ms=execution_time_ms,
        )

    @staticmethod
    def _enrich_output(output: Any, provider_id: str) -> Any:
        """Add _extracted_by and _ai_fields tracking metadata to output.

        Works on dict outputs only. Returns the enriched copy.
        """
        if not isinstance(output, dict):
            return output
        enriched = dict(output)
        enriched["_extracted_by"] = provider_id
        enriched["_ai_fields"] = [
            k for k in enriched.keys() if not k.startswith("_")
        ]
        return enriched

    def _ensure_engine_for_task(self, task: AITask):
        """Get or restart engine for task. MUST be called under _engine_lock."""
        if self._engine and self._current_task_type == task.task_type:
            return self._engine

        # Clean stop before restart
        if self._engine:
            try:
                self._engine.stop_sync()
            except Exception as e:
                logger.warning("[task-service] Engine stop failed: %s", e)
            self._engine = None
            self._current_task_type = None

        # Load skills + create engine
        skills_content = self._load_skills(task.SKILL_NAMES)
        system_prompt = task.build_system_prompt(skills_content)

        try:
            from avatar_engine import AvatarEngine
        except ImportError:
            raise ImportError(
                "avatar-engine is not installed. "
                "See docs/avatar/getting-started.md for installation instructions."
            )

        engine = AvatarEngine(
            provider=self._provider,
            model=self._model or None,
            system_prompt=system_prompt,
            timeout=120,
            safety_instructions="unrestricted",
        )
        engine.start_sync()
        self._engine = engine
        self._current_task_type = task.task_type

        logger.info(
            "[task-service] Engine started for %s: provider=%s, model=%s",
            task.task_type,
            self._provider,
            self._model or "default",
        )

        return self._engine

    def _load_skills(self, skill_names: tuple) -> str:
        """Load skill markdown files by name. Graceful on missing files."""
        if not self.config.skills_dir:
            return ""

        from .skills import load_skill

        parts = []
        for name in skill_names:
            path = self.config.skills_dir / f"{name}.md"
            if path.exists():
                content = load_skill(path)
                if content.strip():
                    parts.append(content)
            else:
                logger.warning("[task-service] Skill file not found: %s", path)
        return "\n\n---\n\n".join(parts)

    # -- Convenience wrappers --

    def extract_parameters(
        self,
        description: str,
        use_cache: bool = True,
    ) -> TaskResult:
        """Extract generation parameters from description.

        Convenience wrapper around execute_task("parameter_extraction", ...).
        """
        return self.execute_task("parameter_extraction", description, use_cache)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.stats()

    def clear_cache(self) -> int:
        """Clear all cached results."""
        return self.cache.clear()

    def cleanup_cache(self) -> int:
        """Remove expired cache entries."""
        return self.cache.cleanup_expired()

    def shutdown(self) -> None:
        """Stop engine if running. Thread-safe."""
        with self._engine_lock:
            if self._engine:
                try:
                    self._engine.stop_sync()
                except Exception as e:
                    logger.warning("[task-service] Shutdown error: %s", e)
                self._engine = None
                self._current_task_type = None
                logger.info("[task-service] Engine stopped")


# Backward compat alias
AvatarAIService = AvatarTaskService
