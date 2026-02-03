"""
AI Service

Main orchestrator for AI-powered tasks.
Handles provider selection, fallback chain, caching, and retries.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .cache import AICache
from .providers import ProviderRegistry
from .providers.base import AIProvider, ProviderResult
from .settings import AIServicesSettings
from .tasks.base import AITask, TaskResult

logger = logging.getLogger(__name__)


class AIService:
    """
    Main AI service - orchestrates providers and tasks.

    Handles:
    - Provider selection based on task priorities
    - Fallback chain when providers fail
    - Result caching
    - Retries with configurable delay
    - Logging at configurable verbosity
    """

    def __init__(self, settings: Optional[AIServicesSettings] = None):
        """
        Initialize AI service.

        Args:
            settings: Service configuration (loads from disk if not provided)
        """
        self.settings = settings or AIServicesSettings.load()
        self.cache = AICache(
            cache_dir=self.settings.cache_directory,
            ttl_days=self.settings.cache_ttl_days,
        )

    def execute_task(
        self,
        task: AITask,
        input_data: Any,
        use_cache: bool = True,
    ) -> TaskResult:
        """
        Execute an AI task using the configured provider chain.

        Args:
            task: Task to execute
            input_data: Task-specific input data
            use_cache: Whether to use caching (default: True)

        Returns:
            TaskResult with output or error
        """
        if not self.settings.enabled:
            logger.info("[ai-service] AI services disabled, using rule-based fallback")
            return self._execute_rule_based(task, input_data)

        # Check cache first
        if use_cache and self.settings.cache_enabled:
            cache_key = task.get_cache_key(input_data)
            cached = self.cache.get(str(input_data))
            if cached:
                logger.info(
                    f"[ai-service] Cache hit for key: {cached.key} "
                    f"(age: {cached.age_days():.1f}d)"
                )
                parsed = task.parse_result(cached.result)

                # Add _extracted_by to output if configured (per spec 4.5)
                if self.settings.show_provider_in_results and isinstance(parsed, dict):
                    parsed["_extracted_by"] = cached.provider_id

                return TaskResult(
                    success=True,
                    output=parsed,
                    provider_id=cached.provider_id,
                    model=cached.model,
                    cached=True,
                    execution_time_ms=cached.execution_time_ms,
                )

        # Get provider order for this task
        provider_order = self.settings.get_provider_order(task.task_type)

        logger.info(
            f"[ai-service] Task: {task.task_type}, "
            f"Provider chain: {' → '.join(provider_order)}"
        )

        # Try each provider in order
        for provider_id in provider_order:
            # Skip rule_based - it's handled separately at the end
            if provider_id == "rule_based":
                continue

            result = self._try_provider(task, input_data, provider_id)
            if result.success:
                # Cache successful result
                if use_cache and self.settings.cache_enabled and result.output:
                    self.cache.set(
                        content=str(input_data),
                        result=result.output,
                        provider_id=result.provider_id,
                        model=result.model,
                        execution_time_ms=result.execution_time_ms,
                    )
                return result

            # Log WHY the provider failed (critical for debugging)
            logger.warning(
                f"[ai-service] Fallback: {provider_id} failed "
                f"(reason: {result.error or 'unknown'}), trying next..."
            )

        # Final fallback to rule-based if configured
        if self.settings.always_fallback_to_rule_based:
            logger.info(
                "[ai-service] All AI providers failed, using rule-based fallback"
            )
            return self._execute_rule_based(task, input_data)

        # No fallback, return error
        return TaskResult(
            success=False,
            error="All AI providers failed and rule-based fallback is disabled",
        )

    def _try_provider(
        self,
        task: AITask,
        input_data: Any,
        provider_id: str,
    ) -> TaskResult:
        """
        Try executing task with a specific provider.

        Handles retries with configurable delay.

        Args:
            task: Task to execute
            input_data: Task input
            provider_id: Provider to use

        Returns:
            TaskResult
        """
        # Get provider config
        provider_config = self.settings.providers.get(provider_id)
        if not provider_config or not provider_config.enabled:
            return TaskResult(
                success=False,
                error=f"Provider {provider_id} is not configured or disabled",
            )

        # Get provider instance
        provider = ProviderRegistry.get(
            provider_id,
            model=provider_config.model,
            endpoint=provider_config.endpoint,
        )
        if not provider:
            return TaskResult(
                success=False,
                error=f"Unknown provider: {provider_id}",
            )

        # Build prompt
        prompt = task.build_prompt(input_data)

        if self.settings.log_prompts:
            logger.debug(f"[ai-service] Prompt:\n{prompt[:500]}...")

        # Get timeout (task-specific or global)
        timeout = self.settings.cli_timeout_seconds
        if task.task_type in self.settings.task_priorities:
            task_config = self.settings.task_priorities[task.task_type]
            if task_config.custom_timeout:
                timeout = task_config.custom_timeout

        # Execute with retries
        last_error = None
        for attempt in range(self.settings.max_retries + 1):
            if attempt > 0:
                logger.info(
                    f"[ai-service] Retry {attempt}/{self.settings.max_retries} "
                    f"for {provider_id}"
                )
                time.sleep(self.settings.retry_delay_seconds)

            result = provider.execute(prompt, timeout=timeout)

            if self.settings.log_responses and result.raw_response:
                logger.debug(
                    f"[ai-service] Raw response:\n{result.raw_response[:500]}..."
                )

            if result.success and result.output:
                # Parse and validate
                parsed = task.parse_result(result.output)
                if task.validate_output(parsed):
                    logger.info(
                        f"[ai-service] Response received in "
                        f"{result.execution_time_ms / 1000:.1f}s, "
                        f"extracted {len(parsed) if isinstance(parsed, dict) else '?'} parameters"
                    )

                    # Add _extracted_by to output if configured (per spec 4.5)
                    if self.settings.show_provider_in_results and isinstance(parsed, dict):
                        parsed["_extracted_by"] = result.provider_id

                    return TaskResult(
                        success=True,
                        output=parsed,
                        provider_id=result.provider_id,
                        model=result.model,
                        cached=False,
                        execution_time_ms=result.execution_time_ms,
                    )
                else:
                    last_error = "Output validation failed"
            else:
                last_error = result.error

        return TaskResult(
            success=False,
            error=last_error or "Unknown error",
            provider_id=provider_id,
        )

    def _execute_rule_based(self, task: AITask, input_data: Any) -> TaskResult:
        """
        Execute task using rule-based fallback.

        Args:
            task: Task to execute
            input_data: Task input

        Returns:
            TaskResult from rule-based provider
        """
        provider = ProviderRegistry.get("rule_based")
        if not provider:
            return TaskResult(
                success=False,
                error="Rule-based provider not available",
            )

        # Use raw input (not AI prompt) for rule-based
        raw_input = task.get_raw_input(input_data)
        result = provider.execute(raw_input)

        if result.success and result.output:
            parsed = task.parse_result(result.output)

            # Add _extracted_by to output if configured (per spec 4.5)
            if self.settings.show_provider_in_results and isinstance(parsed, dict):
                parsed["_extracted_by"] = "rule_based"

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

    def extract_parameters(
        self,
        description: str,
        use_cache: bool = True,
    ) -> TaskResult:
        """
        Convenience method for parameter extraction.

        Args:
            description: Model description
            use_cache: Whether to use caching

        Returns:
            TaskResult with extracted parameters
        """
        from .tasks import ParameterExtractionTask

        task = ParameterExtractionTask()
        return self.execute_task(task, description, use_cache=use_cache)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.stats()

    def clear_cache(self) -> int:
        """Clear all cached results."""
        return self.cache.clear()

    def cleanup_cache(self) -> int:
        """Remove expired cache entries."""
        return self.cache.cleanup_expired()
