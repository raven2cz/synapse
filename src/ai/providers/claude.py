"""
Claude Code Provider

Anthropic Claude via the claude CLI (Claude Code).
Recommended model: claude-sonnet-4-20250514 (highest quality, limited quota)
"""

import json
import logging
import shutil
import subprocess
from typing import List, Optional

from .base import AIProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProvider):
    """
    Claude Code provider for Anthropic AI.

    Uses the `claude --print` command for execution.
    Highest quality (Ø 11.5 keys) but limited quota with Max subscription.
    """

    provider_id = "claude"

    # Known Claude models
    KNOWN_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-5-20251101",
    ]

    def __init__(
        self, model: str = "claude-sonnet-4-20250514", endpoint: Optional[str] = None
    ):
        """
        Initialize Claude provider.

        Args:
            model: Model to use (default: claude-sonnet-4-20250514)
            endpoint: Not used for Claude CLI
        """
        super().__init__(model=model, endpoint=endpoint)

    def detect_availability(self) -> ProviderStatus:
        """
        Check if Claude CLI is installed.

        Returns:
            ProviderStatus with availability information
        """
        # Check if claude CLI is installed
        if not shutil.which("claude"):
            return ProviderStatus(
                provider_id=self.provider_id,
                available=False,
                running=False,
                error="Claude Code CLI not found. Install from: https://claude.ai/claude-code",
            )

        # Get version
        version = self._get_version()

        return ProviderStatus(
            provider_id=self.provider_id,
            available=True,
            running=True,  # CLI doesn't need a server
            version=version,
            models=self.KNOWN_MODELS,
        )

    def execute(self, prompt: str, timeout: int = 60) -> ProviderResult:
        """
        Execute prompt using Claude Code.

        Args:
            prompt: The prompt to execute
            timeout: Maximum execution time in seconds

        Returns:
            ProviderResult with parsed JSON output
        """

        def _execute():
            logger.info(
                f"[ai-service] Task: executing, Provider: claude ({self.model})"
            )

            try:
                # Claude Code: claude --print --model <model> "<prompt>"
                result = subprocess.run(
                    ["claude", "--print", "--model", self.model, prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "Unknown error"
                    return ProviderResult(
                        success=False,
                        error=f"Claude returned error: {error_msg}",
                        provider_id=self.provider_id,
                        model=self.model,
                    )

                raw_response = result.stdout.strip()
                logger.debug(f"[ai-service] Raw response length: {len(raw_response)}")

                # Parse JSON response
                try:
                    output = self.parse_json_response(raw_response)
                    logger.info(
                        f"[ai-service] Extracted {len(output)} parameters"
                    )

                    return ProviderResult(
                        success=True,
                        output=output,
                        raw_response=raw_response,
                        provider_id=self.provider_id,
                        model=self.model,
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"[ai-service] JSON parse error: {e}")
                    return ProviderResult(
                        success=False,
                        error=f"Invalid JSON response: {e}",
                        raw_response=raw_response,
                        provider_id=self.provider_id,
                        model=self.model,
                    )

            except subprocess.TimeoutExpired:
                logger.warning(
                    f"[ai-service] WARNING: Provider claude failed: timeout after {timeout}s"
                )
                return ProviderResult(
                    success=False,
                    error=f"Timeout after {timeout}s",
                    provider_id=self.provider_id,
                    model=self.model,
                )

        return self._timed_execute(_execute)

    def list_models(self) -> List[str]:
        """
        List available Claude models.

        Returns:
            List of known Claude models
        """
        return self.KNOWN_MODELS

    def _get_version(self) -> Optional[str]:
        """Get Claude CLI version."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
