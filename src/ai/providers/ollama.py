"""
Ollama Provider

Local GPU-accelerated AI inference using Ollama CLI.
Recommended model: qwen2.5:14b (~9 GB VRAM)

Automatically manages ollama serve lifecycle:
- Starts server before extraction if not running
- Stops server after extraction to free VRAM
"""

import atexit
import json
import logging
import shutil
import subprocess
import time
from typing import List, Optional

from .base import AIProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)

# Global server process reference for cleanup
_server_process: Optional[subprocess.Popen] = None
_server_started_by_us: bool = False


def _cleanup_server():
    """Cleanup function to stop ollama serve on exit."""
    global _server_process, _server_started_by_us
    if _server_process and _server_started_by_us:
        logger.info("[ai-service] Stopping ollama serve (cleanup)")
        try:
            _server_process.terminate()
            _server_process.wait(timeout=5)
        except Exception:
            _server_process.kill()
        _server_process = None
        _server_started_by_us = False


# Register cleanup on interpreter exit
atexit.register(_cleanup_server)


class OllamaProvider(AIProvider):
    """
    Ollama provider for local AI inference.

    Uses the `ollama run` command for execution.
    Fastest provider (Ø 2.9s) but requires GPU and running ollama server.

    Automatically manages server lifecycle:
    - Starts `ollama serve` if not running
    - Stops server after execution to free VRAM (configurable)
    """

    provider_id = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        endpoint: Optional[str] = "http://localhost:11434",
        auto_start_server: bool = True,
        auto_stop_server: bool = True,
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Model to use (default: qwen2.5:14b)
            endpoint: Ollama server endpoint (default: localhost:11434)
            auto_start_server: Automatically start ollama serve if not running
            auto_stop_server: Stop server after execution to free VRAM
        """
        super().__init__(model=model, endpoint=endpoint)
        self.auto_start_server = auto_start_server
        self.auto_stop_server = auto_stop_server

    def detect_availability(self) -> ProviderStatus:
        """
        Check if Ollama CLI is installed and server is running.

        Returns:
            ProviderStatus with availability and model list
        """
        # Check if ollama CLI is installed
        if not shutil.which("ollama"):
            return ProviderStatus(
                provider_id=self.provider_id,
                available=False,
                running=False,
                error="Ollama CLI not found. Install with: yay -S ollama-cuda",
            )

        # Check if server is running by listing models
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return ProviderStatus(
                    provider_id=self.provider_id,
                    available=True,
                    running=False,
                    error="Ollama server not running. Start with: ollama serve",
                )

            # Parse model list
            models = self._parse_model_list(result.stdout)

            # Get version
            version = self._get_version()

            return ProviderStatus(
                provider_id=self.provider_id,
                available=True,
                running=True,
                version=version,
                models=models,
            )

        except subprocess.TimeoutExpired:
            return ProviderStatus(
                provider_id=self.provider_id,
                available=True,
                running=False,
                error="Ollama server not responding (timeout)",
            )
        except Exception as e:
            return ProviderStatus(
                provider_id=self.provider_id,
                available=True,
                running=False,
                error=f"Error checking Ollama: {e}",
            )

    def _is_server_running(self) -> bool:
        """Check if ollama server is responding."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
            logger.debug(f"[ai-service] ollama list failed: {result.stderr.strip()}")
            return False
        except subprocess.TimeoutExpired:
            logger.debug("[ai-service] ollama list timeout - server not responding")
            return False
        except Exception as e:
            logger.debug(f"[ai-service] ollama list error: {e}")
            return False

    def _start_server(self) -> bool:
        """
        Start ollama serve in background.

        Returns:
            True if server started successfully
        """
        global _server_process, _server_started_by_us

        if self._is_server_running():
            logger.debug("[ai-service] Ollama server already running")
            return True

        logger.info("[ai-service] Starting ollama serve...")

        try:
            # Start ollama serve in background
            _server_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process group
            )
            _server_started_by_us = True

            # Wait for server to be ready (max 30 seconds)
            for _ in range(30):
                time.sleep(1)
                if self._is_server_running():
                    logger.info("[ai-service] Ollama server started successfully")
                    return True

            logger.warning("[ai-service] Ollama server failed to start within 30s")
            self._stop_server()
            return False

        except Exception as e:
            logger.error(f"[ai-service] Failed to start ollama serve: {e}")
            return False

    def _stop_server(self) -> None:
        """Stop ollama serve if we started it."""
        global _server_process, _server_started_by_us

        if not _server_started_by_us or not _server_process:
            return

        logger.info("[ai-service] Stopping ollama serve (freeing VRAM)")

        try:
            _server_process.terminate()
            _server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("[ai-service] Ollama server didn't stop gracefully, killing")
            _server_process.kill()
            _server_process.wait()
        except Exception as e:
            logger.error(f"[ai-service] Error stopping ollama serve: {e}")

        _server_process = None
        _server_started_by_us = False

    def execute(self, prompt: str, timeout: int = 60) -> ProviderResult:
        """
        Execute prompt using Ollama.

        Automatically starts ollama serve if not running (and auto_start_server=True).
        Stops server after execution if auto_stop_server=True (to free VRAM).

        Args:
            prompt: The prompt to execute
            timeout: Maximum execution time in seconds

        Returns:
            ProviderResult with parsed JSON output
        """
        # Auto-start server if needed
        if self.auto_start_server and not self._is_server_running():
            if not self._start_server():
                return ProviderResult(
                    success=False,
                    error="Failed to start ollama serve",
                    provider_id=self.provider_id,
                    model=self.model,
                )

        def _execute():
            logger.info(
                f"[ai-service] Task: executing, Provider: ollama ({self.model})"
            )

            # Check if model is available (warn if not, but still try)
            available_models = self.list_models()
            if self.model not in available_models:
                logger.warning(
                    f"[ai-service] Model '{self.model}' not in available models: "
                    f"{available_models}. Ollama may need to download it first."
                )

            try:
                # Use stdin for prompt to avoid command line length limits
                # Long prompts as arguments can cause timeouts or issues
                logger.debug(f"[ai-service] Running: ollama run {self.model} (prompt via stdin)")
                result = subprocess.run(
                    ["ollama", "run", self.model],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "unknown error"
                    logger.error(f"[ai-service] Ollama error (rc={result.returncode}): {error_msg}")
                    return ProviderResult(
                        success=False,
                        error=f"Ollama returned error: {error_msg}",
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
                    f"[ai-service] Ollama timeout after {timeout}s for model '{self.model}'"
                )
                return ProviderResult(
                    success=False,
                    error=f"Timeout after {timeout}s",
                    provider_id=self.provider_id,
                    model=self.model,
                )
            except Exception as e:
                logger.error(f"[ai-service] Ollama unexpected error: {e}")
                return ProviderResult(
                    success=False,
                    error=f"Unexpected error: {e}",
                    provider_id=self.provider_id,
                    model=self.model,
                )

        result = self._timed_execute(_execute)

        # Auto-stop server after execution to free VRAM
        if self.auto_stop_server and _server_started_by_us:
            self._stop_server()

        return result

    def list_models(self) -> List[str]:
        """
        List available Ollama models.

        Returns:
            List of installed model names
        """
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return self._parse_model_list(result.stdout)
        except Exception:
            pass

        return []

    def _parse_model_list(self, output: str) -> List[str]:
        """
        Parse ollama list output to extract model names.

        Output format:
        NAME                    ID              SIZE      MODIFIED
        qwen2.5:14b             abc123...       9.0 GB    2 days ago

        Args:
            output: Raw output from ollama list

        Returns:
            List of model names
        """
        models = []
        lines = output.strip().split("\n")

        # Skip header line
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])

        return models

    def _get_version(self) -> Optional[str]:
        """Get Ollama version."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Output: "ollama version is 0.1.xx"
                return result.stdout.strip().replace("ollama version is ", "")
        except Exception:
            pass
        return None
