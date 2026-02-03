"""
Unit tests for AI service.
"""

import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.ai.service import AIService
from src.ai.settings import AIServicesSettings, ProviderConfig, TaskPriorityConfig
from src.ai.tasks import ParameterExtractionTask
from src.ai.providers.base import ProviderResult


class TestAIServicesSettings:
    """Tests for AIServicesSettings."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = AIServicesSettings.get_defaults()

        assert settings.enabled is True
        assert "ollama" in settings.providers
        assert "gemini" in settings.providers
        assert "claude" in settings.providers

        # Ollama should be enabled by default
        assert settings.providers["ollama"].enabled is True

        # Claude should be disabled by default (to save quota)
        assert settings.providers["claude"].enabled is False

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        original = AIServicesSettings.get_defaults()
        data = original.to_dict()
        restored = AIServicesSettings.from_dict(data)

        assert restored.enabled == original.enabled
        assert len(restored.providers) == len(original.providers)
        assert restored.cli_timeout_seconds == original.cli_timeout_seconds

    def test_get_provider_order(self):
        """Test getting provider order for a task."""
        settings = AIServicesSettings.get_defaults()

        order = settings.get_provider_order("parameter_extraction")
        assert order == ["ollama", "gemini", "claude"]

    def test_get_provider_order_unknown_task(self):
        """Test fallback order for unknown task."""
        settings = AIServicesSettings.get_defaults()

        order = settings.get_provider_order("unknown_task")
        # Should return default order
        assert len(order) > 0

    def test_get_enabled_providers(self):
        """Test getting only enabled providers."""
        settings = AIServicesSettings.get_defaults()
        enabled = settings.get_enabled_providers()

        # Ollama and Gemini enabled by default, Claude disabled
        assert any(p.provider_id == "ollama" for p in enabled)
        assert any(p.provider_id == "gemini" for p in enabled)
        assert not any(p.provider_id == "claude" for p in enabled)


class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_default_values(self):
        """Test default values."""
        config = ProviderConfig(provider_id="test")

        assert config.enabled is False
        assert config.model == ""
        assert config.available_models == []
        assert config.endpoint is None

    def test_to_dict(self):
        """Test serialization."""
        config = ProviderConfig(
            provider_id="ollama",
            enabled=True,
            model="qwen2.5:14b",
        )

        data = config.to_dict()
        assert data["provider_id"] == "ollama"
        assert data["enabled"] is True
        assert data["model"] == "qwen2.5:14b"


class TestTaskPriorityConfig:
    """Tests for TaskPriorityConfig."""

    def test_default_values(self):
        """Test default values."""
        config = TaskPriorityConfig(task_type="test")

        assert config.provider_order == []
        assert config.custom_timeout is None
        assert config.custom_prompt is None

    def test_with_values(self):
        """Test with custom values."""
        config = TaskPriorityConfig(
            task_type="parameter_extraction",
            provider_order=["ollama", "gemini"],
            custom_timeout=120,
        )

        assert config.task_type == "parameter_extraction"
        assert config.provider_order == ["ollama", "gemini"]
        assert config.custom_timeout == 120


class TestParameterExtractionTask:
    """Tests for ParameterExtractionTask."""

    def test_task_type(self):
        """Test task type is set correctly."""
        task = ParameterExtractionTask()
        assert task.task_type == "parameter_extraction"

    def test_build_prompt(self):
        """Test prompt building includes description."""
        task = ParameterExtractionTask()
        description = "Test model with CFG 7 and 25 steps"

        prompt = task.build_prompt(description)

        # Prompt should contain the description
        assert description in prompt
        # Prompt should contain extraction instructions
        assert "extract" in prompt.lower()
        assert "json" in prompt.lower()

    def test_parse_result(self):
        """Test result parsing."""
        task = ParameterExtractionTask()

        raw = {
            "cfg_scale": 7,
            "steps": 25,
            "_internal": "should be removed",
        }

        result = task.parse_result(raw)

        assert result["cfg_scale"] == 7
        assert result["steps"] == 25
        assert "_internal" not in result

    def test_validate_output_valid(self):
        """Test validation of valid output."""
        task = ParameterExtractionTask()

        assert task.validate_output({"key": "value"}) is True

    def test_validate_output_invalid(self):
        """Test validation of invalid output."""
        task = ParameterExtractionTask()

        assert task.validate_output(None) is False
        assert task.validate_output({}) is False

    def test_get_raw_input(self):
        """Test raw input for rule-based fallback."""
        task = ParameterExtractionTask()
        description = "Test description"

        raw = task.get_raw_input(description)
        assert raw == description


class TestAIService:
    """Tests for AIService."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def service_with_temp_cache(self, temp_cache_dir):
        """Create a service with temp cache."""
        settings = AIServicesSettings.get_defaults()
        settings.cache_directory = temp_cache_dir
        return AIService(settings)

    def test_init_with_defaults(self):
        """Test initialization with default settings."""
        service = AIService()

        assert service.settings is not None
        assert service.cache is not None

    def test_init_with_custom_settings(self, temp_cache_dir):
        """Test initialization with custom settings."""
        settings = AIServicesSettings()
        settings.cache_directory = temp_cache_dir
        settings.cli_timeout_seconds = 120

        service = AIService(settings)

        assert service.settings.cli_timeout_seconds == 120

    @patch("src.ai.providers.registry.ProviderRegistry.get")
    def test_execute_task_success(self, mock_get, service_with_temp_cache):
        """Test successful task execution."""
        # Mock provider
        mock_provider = MagicMock()
        mock_provider.execute.return_value = ProviderResult(
            success=True,
            output={"cfg_scale": 7, "steps": 25},
            provider_id="ollama",
            model="qwen2.5:14b",
            execution_time_ms=1500,
        )
        mock_get.return_value = mock_provider

        task = ParameterExtractionTask()
        result = service_with_temp_cache.execute_task(
            task, "test description", use_cache=False
        )

        assert result.success is True
        assert result.output["cfg_scale"] == 7
        assert result.output["steps"] == 25
        assert result.provider_id == "ollama"

    def test_execute_task_disabled(self, temp_cache_dir):
        """Test execution when AI is disabled."""
        settings = AIServicesSettings.get_defaults()
        settings.enabled = False
        settings.cache_directory = temp_cache_dir
        service = AIService(settings)

        task = ParameterExtractionTask()

        with patch("src.ai.providers.registry.ProviderRegistry.get") as mock_get:
            mock_provider = MagicMock()
            mock_provider.execute.return_value = ProviderResult(
                success=True,
                output={"fallback": True},
                provider_id="rule_based",
                model="regexp",
            )
            mock_get.return_value = mock_provider

            result = service.execute_task(task, "test", use_cache=False)

            # Should use rule-based fallback
            assert result.provider_id == "rule_based"

    def test_cache_hit(self, service_with_temp_cache):
        """Test cache hit prevents provider execution."""
        # Populate cache
        service_with_temp_cache.cache.set(
            content="test description",
            result={"cached": True},
            provider_id="ollama",
            model="qwen2.5:14b",
            execution_time_ms=1000,
        )

        task = ParameterExtractionTask()

        with patch("src.ai.providers.registry.ProviderRegistry.get") as mock_get:
            result = service_with_temp_cache.execute_task(
                task, "test description", use_cache=True
            )

            # Should not call provider
            mock_get.assert_not_called()

            assert result.success is True
            assert result.cached is True
            assert result.output["cached"] is True

    def test_extract_parameters_convenience(self, service_with_temp_cache):
        """Test extract_parameters convenience method."""
        with patch.object(service_with_temp_cache, "execute_task") as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                output={"cfg_scale": 7},
            )

            result = service_with_temp_cache.extract_parameters(
                "test description", use_cache=False
            )

            mock_execute.assert_called_once()
            # Should be called with ParameterExtractionTask
            call_args = mock_execute.call_args
            assert isinstance(call_args[0][0], ParameterExtractionTask)
