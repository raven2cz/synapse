"""
Unit tests for ParameterExtractionTask.

Tests the task class in isolation — build_system_prompt, parse_result,
validate_output, get_fallback, SKILL_NAMES.
"""

from unittest.mock import patch

import pytest

from src.avatar.prompts.parameter_extraction import PARAMETER_EXTRACTION_PROMPT
from src.avatar.tasks.base import TaskResult
from src.avatar.tasks.parameter_extraction import ParameterExtractionTask


# =============================================================================
# TestParameterExtractionTaskAttributes
# =============================================================================


class TestParameterExtractionTaskAttributes:
    """Test class-level attributes."""

    def test_task_type(self):
        task = ParameterExtractionTask()
        assert task.task_type == "parameter_extraction"

    def test_skill_names_is_immutable_tuple(self):
        task = ParameterExtractionTask()
        assert task.SKILL_NAMES == ("generation-params",)
        assert isinstance(task.SKILL_NAMES, tuple)

    def test_cache_prefix_matches_task_type(self):
        task = ParameterExtractionTask()
        assert task.get_cache_prefix() == "parameter_extraction"


# =============================================================================
# TestBuildSystemPrompt
# =============================================================================


class TestBuildSystemPrompt:
    """Test build_system_prompt method."""

    def test_includes_v2_prompt(self):
        """Prompt starts with the V2 extraction prompt."""
        task = ParameterExtractionTask()
        prompt = task.build_system_prompt("")
        assert PARAMETER_EXTRACTION_PROMPT in prompt

    def test_empty_skills_no_reference_section(self):
        """Empty skills_content doesn't add Reference Knowledge section."""
        task = ParameterExtractionTask()
        prompt = task.build_system_prompt("")
        assert "Reference Knowledge" not in prompt

    def test_whitespace_only_skills_no_reference(self):
        """Whitespace-only skills_content doesn't add Reference Knowledge."""
        task = ParameterExtractionTask()
        prompt = task.build_system_prompt("   \n  ")
        assert "Reference Knowledge" not in prompt

    def test_skills_content_appended(self):
        """Skills content is appended after the prompt."""
        task = ParameterExtractionTask()
        skills = "# Generation Parameters\n| Param | Range |\n| steps | 20-30 |"
        prompt = task.build_system_prompt(skills)
        assert "Reference Knowledge" in prompt
        assert "Generation Parameters" in prompt
        assert PARAMETER_EXTRACTION_PROMPT in prompt

    def test_separator_between_prompt_and_skills(self):
        """There's a separator between prompt and skills."""
        task = ParameterExtractionTask()
        prompt = task.build_system_prompt("Some skill content")
        assert "---" in prompt


# =============================================================================
# TestParseResult
# =============================================================================


class TestParseResult:
    """Test parse_result method."""

    def test_dict_passes_through(self):
        task = ParameterExtractionTask()
        result = task.parse_result({"steps": 20, "sampler": "Euler"})
        assert result == {"steps": 20, "sampler": "Euler"}

    def test_strips_underscore_keys(self):
        """Internal keys (starting with _) are removed."""
        task = ParameterExtractionTask()
        result = task.parse_result({
            "steps": 20,
            "_internal": "should be removed",
            "_extracted_by": "avatar:gemini",
        })
        assert result == {"steps": 20}
        assert "_internal" not in result
        assert "_extracted_by" not in result

    def test_non_dict_returns_empty(self):
        task = ParameterExtractionTask()
        assert task.parse_result("not a dict") == {}
        assert task.parse_result(42) == {}
        assert task.parse_result(None) == {}
        assert task.parse_result([1, 2]) == {}

    def test_empty_dict_after_strip(self):
        """Dict with only underscore keys becomes empty."""
        task = ParameterExtractionTask()
        result = task.parse_result({"_internal": "only"})
        assert result == {}


# =============================================================================
# TestValidateOutput
# =============================================================================


class TestValidateOutput:
    """Test validate_output method."""

    def test_non_empty_dict_valid(self):
        task = ParameterExtractionTask()
        assert task.validate_output({"steps": 20}) is True

    def test_empty_dict_invalid(self):
        task = ParameterExtractionTask()
        assert task.validate_output({}) is False

    def test_none_invalid(self):
        task = ParameterExtractionTask()
        assert task.validate_output(None) is False

    def test_non_dict_invalid(self):
        task = ParameterExtractionTask()
        assert task.validate_output("string") is False
        assert task.validate_output(42) is False
        assert task.validate_output([1, 2]) is False


# =============================================================================
# TestGetFallback
# =============================================================================


class TestGetFallback:
    """Test get_fallback method."""

    def test_returns_callable(self):
        task = ParameterExtractionTask()
        fb = task.get_fallback()
        assert fb is not None
        assert callable(fb)

    def test_fallback_success(self):
        """Fallback returns TaskResult with rule_based provider."""
        task = ParameterExtractionTask()
        fb = task.get_fallback()

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock.return_value = RuleBasedResult(
                success=True,
                output={"steps": 20, "cfg_scale": 7},
                execution_time_ms=5,
            )
            result = fb("Steps: 20, CFG: 7")

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.provider_id == "rule_based"
        assert result.model == "regexp"
        assert result.output == {"steps": 20, "cfg_scale": 7}

    def test_fallback_failure(self):
        """Fallback returns failure when rule-based fails."""
        task = ParameterExtractionTask()
        fb = task.get_fallback()

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock.return_value = RuleBasedResult(
                success=False,
                error="No patterns matched",
            )
            result = fb("nonsense input")

        assert isinstance(result, TaskResult)
        assert result.success is False
        assert result.error == "No patterns matched"
        assert result.provider_id == "rule_based"

    def test_fallback_strips_underscore_keys(self):
        """Fallback applies parse_result which strips underscore keys."""
        task = ParameterExtractionTask()
        fb = task.get_fallback()

        with patch("src.avatar.providers.rule_based.RuleBasedProvider.execute") as mock:
            from src.avatar.providers.rule_based import RuleBasedResult
            mock.return_value = RuleBasedResult(
                success=True,
                output={"steps": 20, "_internal": "strip me"},
            )
            result = fb("Steps: 20")

        assert "_internal" not in result.output
        assert result.output == {"steps": 20}
