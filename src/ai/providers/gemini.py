"""
Gemini CLI Provider

Google Gemini AI via the gemini CLI tool.
Recommended model: gemini-3-pro-preview (requires Preview features enabled in /settings)

Note: Gemini 3 models require "-preview" suffix until GA release.
"""

import json
import logging
import shutil
import subprocess
from typing import List, Optional

from .base import AIProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """
    Gemini CLI provider for Google AI.

    Uses the `gemini -p` command for execution.
    Unlimited usage with Pro subscription, but slower (Ø 21s).

    Note: Gemini 3 models are in preview and require "-preview" suffix.
    """

    provider_id = "gemini"

    # Known Gemini models
    # Note: Gemini 3 requires "-preview" suffix until GA
    KNOWN_MODELS = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]

    def __init__(self, model: str = "gemini-3-pro-preview", endpoint: Optional[str] = None):
        """
        Initialize Gemini provider.

        Args:
            model: Model to use (default: gemini-3-pro-preview)
            endpoint: Not used for Gemini CLI
        """
        super().__init__(model=model, endpoint=endpoint)

    def detect_availability(self) -> ProviderStatus:
        """
        Check if Gemini CLI is installed.

        Returns:
            ProviderStatus with availability information
        """
        # Check if gemini CLI is installed
        if not shutil.which("gemini"):
            return ProviderStatus(
                provider_id=self.provider_id,
                available=False,
                running=False,
                error="Gemini CLI not found. Install from: https://github.com/google-gemini/gemini-cli",
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
        Execute prompt using Gemini CLI.

        Args:
            prompt: The prompt to execute
            timeout: Maximum execution time in seconds

        Returns:
            ProviderResult with parsed JSON output
        """

        def _execute():
            logger.info(
                f"[ai-service] Task: executing, Provider: gemini ({self.model})"
            )

            try:
                # Gemini CLI: gemini --model <model> -p "<prompt>"
                result = subprocess.run(
                    ["gemini", "--model", self.model, "-p", prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "Unknown error"
                    return ProviderResult(
                        success=False,
                        error=f"Gemini returned error: {error_msg}",
                        provider_id=self.provider_id,
                        model=self.model,
                    )

                raw_response = result.stdout.strip()
                logger.debug(f"[ai-service] Raw response length: {len(raw_response)}")

                # Parse JSON response (Gemini often wraps in markdown fences)
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
                    f"[ai-service] WARNING: Provider gemini failed: timeout after {timeout}s"
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
        List available Gemini models.

        Gemini CLI doesn't have a list command, so return known models.

        Returns:
            List of known Gemini models
        """
        return self.KNOWN_MODELS

    def _get_version(self) -> Optional[str]:
        """Get Gemini CLI version."""
        try:
            result = subprocess.run(
                ["gemini", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
