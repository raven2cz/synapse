"""
Unit tests for AI providers.

Tests provider base class, JSON parsing, and mock execution.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.ai.providers.base import AIProvider, ProviderResult, ProviderStatus
from src.ai.providers.ollama import OllamaProvider
from src.ai.providers.gemini import GeminiProvider
from src.ai.providers.claude import ClaudeProvider
from src.ai.providers.rule_based import RuleBasedProvider
from src.ai.providers.registry import ProviderRegistry


class TestProviderBase:
    """Tests for AIProvider base class."""

    def test_parse_json_simple(self):
        """Test parsing plain JSON response."""
        provider = OllamaProvider()
        result = provider.parse_json_response('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_parse_json_with_fences(self):
        """Test parsing JSON wrapped in markdown fences."""
        provider = OllamaProvider()

        # With ```json header
        response = '```json\n{"key": "value"}\n```'
        result = provider.parse_json_response(response)
        assert result == {"key": "value"}

        # With plain ``` header
        response = '```\n{"key": "value"}\n```'
        result = provider.parse_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_with_trailing_fence(self):
        """Test parsing JSON with only trailing fence."""
        provider = OllamaProvider()
        response = '{"key": "value"}\n```'
        result = provider.parse_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_complex(self):
        """Test parsing complex JSON with nested objects."""
        provider = OllamaProvider()
        response = '''```json
{
  "base_model": "SDXL 1.0",
  "steps": {"min": 20, "max": 30},
  "sampler": ["DPM++ 2M", "Euler a"]
}
```'''
        result = provider.parse_json_response(response)
        assert result["base_model"] == "SDXL 1.0"
        assert result["steps"] == {"min": 20, "max": 30}
        assert result["sampler"] == ["DPM++ 2M", "Euler a"]

    def test_parse_json_invalid(self):
        """Test that invalid JSON raises error."""
        provider = OllamaProvider()
        with pytest.raises(json.JSONDecodeError):
            provider.parse_json_response("not valid json")

    def test_parse_json_with_text_before(self):
        """Test parsing JSON with explanatory text before it."""
        provider = OllamaProvider()
        response = '''Here is the extracted JSON data:

{"base_model": "SDXL 1.0", "steps": 25}'''
        result = provider.parse_json_response(response)
        assert result == {"base_model": "SDXL 1.0", "steps": 25}

    def test_parse_json_with_text_after(self):
        """Test parsing JSON with explanatory text after it."""
        provider = OllamaProvider()
        response = '''{"base_model": "SDXL 1.0", "steps": 25}

I hope this helps! Let me know if you need anything else.'''
        result = provider.parse_json_response(response)
        assert result == {"base_model": "SDXL 1.0", "steps": 25}

    def test_parse_json_with_text_before_and_after(self):
        """Test parsing JSON surrounded by explanatory text."""
        provider = OllamaProvider()
        response = '''Based on the description, here are the extracted parameters:

{"base_model": "SDXL 1.0", "steps": 25, "cfg_scale": 7.5}

These parameters were extracted from the model's recommended settings.'''
        result = provider.parse_json_response(response)
        assert result["base_model"] == "SDXL 1.0"
        assert result["steps"] == 25
        assert result["cfg_scale"] == 7.5

    def test_parse_json_nested_with_strings(self):
        """Test parsing JSON with strings containing braces."""
        provider = OllamaProvider()
        response = '''Here is the result:
{
  "prompt": "a girl with {curly} hair",
  "negative": "bad {quality}"
}
That's the extracted data.'''
        result = provider.parse_json_response(response)
        assert result["prompt"] == "a girl with {curly} hair"
        assert result["negative"] == "bad {quality}"

    def test_parse_json_array(self):
        """Test parsing JSON array response."""
        provider = OllamaProvider()
        response = '''The models are:
[{"name": "SDXL"}, {"name": "SD 1.5"}]'''
        result = provider.parse_json_response(response)
        assert len(result) == 2
        assert result[0]["name"] == "SDXL"


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_provider_id(self):
        """Test provider ID is set correctly."""
        provider = OllamaProvider()
        assert provider.provider_id == "ollama"

    def test_default_model(self):
        """Test default model is qwen2.5:14b."""
        provider = OllamaProvider()
        assert provider.model == "qwen2.5:14b"

    def test_custom_model(self):
        """Test custom model can be set."""
        provider = OllamaProvider(model="llama3.1:8b")
        assert provider.model == "llama3.1:8b"

    def test_default_endpoint(self):
        """Test default endpoint is localhost:11434."""
        provider = OllamaProvider()
        assert provider.endpoint == "http://localhost:11434"

    @patch("shutil.which")
    def test_detect_not_installed(self, mock_which):
        """Test detection when ollama is not installed."""
        mock_which.return_value = None

        provider = OllamaProvider()
        status = provider.detect_availability()

        assert status.provider_id == "ollama"
        assert status.available is False
        assert "not found" in status.error.lower()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_server_not_running(self, mock_run, mock_which):
        """Test detection when ollama server is not running."""
        mock_which.return_value = "/usr/bin/ollama"
        mock_run.return_value = MagicMock(returncode=1)

        provider = OllamaProvider()
        status = provider.detect_availability()

        assert status.available is True
        assert status.running is False

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_available_and_running(self, mock_run, mock_which):
        """Test detection when ollama is available and running."""
        mock_which.return_value = "/usr/bin/ollama"
        mock_run.side_effect = [
            # ollama list
            MagicMock(
                returncode=0,
                stdout="NAME\t\tID\t\tSIZE\nqwen2.5:14b\tabc123\t9.0 GB\n"
            ),
            # ollama --version
            MagicMock(returncode=0, stdout="0.1.28"),
        ]

        provider = OllamaProvider()
        status = provider.detect_availability()

        assert status.available is True
        assert status.running is True
        assert "qwen2.5:14b" in status.models

    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        """Test successful execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"cfg_scale": 7, "steps": 25}',
        )

        # Disable auto_start/stop to simplify test
        provider = OllamaProvider(auto_start_server=False, auto_stop_server=False)
        result = provider.execute("test prompt")

        assert result.success is True
        assert result.output == {"cfg_scale": 7, "steps": 25}
        assert result.provider_id == "ollama"

    @patch("subprocess.run")
    def test_execute_timeout(self, mock_run):
        """Test timeout handling."""
        import subprocess

        def mock_run_side_effect(*args, **kwargs):
            # First call is _is_server_running check, return success
            if args[0] == ["ollama", "list"]:
                return subprocess.CompletedProcess(args[0], 0, stdout="NAME\nqwen2.5:14b\n", stderr="")
            # Second call is the actual execution, raise timeout
            raise subprocess.TimeoutExpired("ollama", 60)

        mock_run.side_effect = mock_run_side_effect

        # Disable auto_start to simplify test
        provider = OllamaProvider(auto_start_server=False, auto_stop_server=False)
        result = provider.execute("test prompt", timeout=60)

        assert result.success is False
        assert "timeout" in result.error.lower()


class TestGeminiProvider:
    """Tests for Gemini CLI provider."""

    def test_provider_id(self):
        """Test provider ID is set correctly."""
        provider = GeminiProvider()
        assert provider.provider_id == "gemini"

    def test_default_model(self):
        """Test default model is gemini-3-pro-preview."""
        provider = GeminiProvider()
        assert provider.model == "gemini-3-pro-preview"

    def test_known_models(self):
        """Test known models list."""
        provider = GeminiProvider()
        models = provider.list_models()
        assert "gemini-3-pro-preview" in models
        assert "gemini-3-flash-preview" in models
        assert "gemini-2.5-pro" in models

    @patch("shutil.which")
    def test_detect_not_installed(self, mock_which):
        """Test detection when gemini is not installed."""
        mock_which.return_value = None

        provider = GeminiProvider()
        status = provider.detect_availability()

        assert status.provider_id == "gemini"
        assert status.available is False

    @patch("shutil.which")
    def test_detect_installed(self, mock_which):
        """Test detection when gemini is installed."""
        mock_which.return_value = "/usr/bin/gemini"

        provider = GeminiProvider()
        status = provider.detect_availability()

        assert status.available is True
        assert status.running is True  # CLI doesn't need server


class TestClaudeProvider:
    """Tests for Claude Code provider."""

    def test_provider_id(self):
        """Test provider ID is set correctly."""
        provider = ClaudeProvider()
        assert provider.provider_id == "claude"

    def test_default_model(self):
        """Test default model is claude-sonnet-4."""
        provider = ClaudeProvider()
        assert provider.model == "claude-sonnet-4-20250514"

    def test_known_models(self):
        """Test known models list."""
        provider = ClaudeProvider()
        models = provider.list_models()
        assert "claude-sonnet-4-20250514" in models
        assert "claude-haiku-4-5-20251001" in models
        assert "claude-opus-4-5-20251101" in models


class TestRuleBasedProvider:
    """Tests for rule-based fallback provider."""

    def test_provider_id(self):
        """Test provider ID is set correctly."""
        provider = RuleBasedProvider()
        assert provider.provider_id == "rule_based"

    def test_always_available(self):
        """Test rule-based is always available."""
        provider = RuleBasedProvider()
        status = provider.detect_availability()

        assert status.available is True
        assert status.running is True
        assert status.models == ["regexp"]


class TestProviderRegistry:
    """Tests for provider registry."""

    def test_list_builtin_providers(self):
        """Test listing built-in providers."""
        providers = ProviderRegistry.list_providers()

        assert "ollama" in providers
        assert "gemini" in providers
        assert "claude" in providers
        assert "rule_based" in providers

    def test_get_provider(self):
        """Test getting a provider instance."""
        provider = ProviderRegistry.get("ollama", model="test-model")

        assert provider is not None
        assert isinstance(provider, OllamaProvider)
        assert provider.model == "test-model"

    def test_get_unknown_provider(self):
        """Test getting unknown provider returns None."""
        provider = ProviderRegistry.get("unknown_provider")
        assert provider is None

    def test_register_custom_provider(self):
        """Test registering a custom provider."""

        class CustomProvider(AIProvider):
            provider_id = "custom"

            def detect_availability(self):
                return ProviderStatus(
                    provider_id=self.provider_id,
                    available=True,
                    running=True,
                )

            def execute(self, prompt, timeout=60):
                return ProviderResult(success=True, output={})

            def list_models(self):
                return ["custom-model"]

        ProviderRegistry.register("custom", CustomProvider)

        assert "custom" in ProviderRegistry.list_providers()

        provider = ProviderRegistry.get("custom")
        assert provider is not None
        assert provider.provider_id == "custom"

        # Cleanup
        ProviderRegistry.unregister("custom")
        assert "custom" not in ProviderRegistry.list_providers()
