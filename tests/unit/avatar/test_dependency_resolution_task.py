"""
Unit tests for DependencyResolutionTask.

Tests the task class in isolation — build_system_prompt, parse_result,
validate_output, get_fallback, confidence ceiling enforcement.
"""

import pytest

from src.avatar.tasks.dependency_resolution import (
    AI_CONFIDENCE_CEILING,
    DependencyResolutionTask,
)


# =============================================================================
# TestTaskAttributes
# =============================================================================


class TestTaskAttributes:
    def test_task_type(self):
        task = DependencyResolutionTask()
        assert task.task_type == "dependency_resolution"

    def test_skill_names(self):
        task = DependencyResolutionTask()
        assert isinstance(task.SKILL_NAMES, tuple)
        assert len(task.SKILL_NAMES) == 5
        assert "model-resolution" in task.SKILL_NAMES
        assert "dependency-resolution" in task.SKILL_NAMES
        assert "model-types" in task.SKILL_NAMES
        assert "civitai-integration" in task.SKILL_NAMES
        assert "huggingface-integration" in task.SKILL_NAMES

    def test_needs_mcp(self):
        task = DependencyResolutionTask()
        assert task.needs_mcp is True

    def test_timeout(self):
        task = DependencyResolutionTask()
        assert task.timeout_s == 180

    def test_cache_prefix(self):
        task = DependencyResolutionTask()
        assert task.get_cache_prefix() == "dependency_resolution"

    def test_no_fallback(self):
        task = DependencyResolutionTask()
        assert task.get_fallback() is None

    def test_confidence_ceiling_constant(self):
        assert AI_CONFIDENCE_CEILING == 0.89


# =============================================================================
# TestBuildSystemPrompt
# =============================================================================


class TestBuildSystemPrompt:
    def test_returns_skills_content_directly(self):
        """Prompt IS the skills content — no hardcoded additions."""
        task = DependencyResolutionTask()
        skills = "# Model Resolution Task\nYou are a dependency resolver..."
        prompt = task.build_system_prompt(skills)
        assert prompt == skills

    def test_empty_skills_returns_empty(self):
        task = DependencyResolutionTask()
        assert task.build_system_prompt("") == ""

    def test_no_reference_knowledge_header(self):
        """Unlike other tasks, does NOT wrap skills in 'Reference Knowledge'."""
        task = DependencyResolutionTask()
        prompt = task.build_system_prompt("# Content here")
        assert "Reference Knowledge" not in prompt


# =============================================================================
# TestParseResult — happy paths
# =============================================================================


class TestParseResultHappyPath:
    def test_single_civitai_candidate(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Illustrious XL v0.1",
                    "provider": "civitai",
                    "model_id": 795765,
                    "version_id": 889818,
                    "file_id": 795432,
                    "base_model": "Illustrious",
                    "confidence": 0.85,
                    "reasoning": "Strong match based on evidence.",
                }
            ],
            "search_summary": "Searched Civitai for Illustrious.",
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 1
        c = result["candidates"][0]
        assert c["display_name"] == "Illustrious XL v0.1"
        assert c["provider"] == "civitai"
        assert c["model_id"] == 795765
        assert c["confidence"] == 0.85
        assert result["search_summary"] == "Searched Civitai for Illustrious."

    def test_single_huggingface_candidate(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "SDXL Base (HF)",
                    "provider": "huggingface",
                    "repo_id": "stabilityai/stable-diffusion-xl-base-1.0",
                    "filename": "sd_xl_base_1.0.safetensors",
                    "base_model": "SDXL",
                    "confidence": 0.72,
                    "reasoning": "Name match on HF.",
                }
            ],
            "search_summary": "Searched HuggingFace.",
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 1
        c = result["candidates"][0]
        assert c["provider"] == "huggingface"
        assert c["repo_id"] == "stabilityai/stable-diffusion-xl-base-1.0"

    def test_multiple_candidates_sorted_by_confidence(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Low conf",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.50,
                    "reasoning": "Weak.",
                },
                {
                    "display_name": "High conf",
                    "provider": "civitai",
                    "model_id": 2,
                    "confidence": 0.85,
                    "reasoning": "Strong.",
                },
                {
                    "display_name": "Mid conf",
                    "provider": "huggingface",
                    "repo_id": "org/repo",
                    "filename": "model.safetensors",
                    "confidence": 0.72,
                    "reasoning": "Medium.",
                },
            ],
            "search_summary": "Multi-provider search.",
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 3
        confs = [c["confidence"] for c in result["candidates"]]
        assert confs == sorted(confs, reverse=True)

    def test_empty_candidates_valid(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [],
            "search_summary": "No results found.",
        }
        result = task.parse_result(raw)
        assert result["candidates"] == []
        assert result["search_summary"] == "No results found."


# =============================================================================
# TestParseResult — confidence ceiling
# =============================================================================


class TestParseResultConfidenceCeiling:
    def test_confidence_capped_at_ceiling(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Overconfident",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.95,
                    "reasoning": "AI hallucinated high confidence.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert result["candidates"][0]["confidence"] == AI_CONFIDENCE_CEILING

    def test_confidence_exactly_at_ceiling_unchanged(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "At ceiling",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.89,
                    "reasoning": "At ceiling.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert result["candidates"][0]["confidence"] == 0.89

    def test_confidence_below_ceiling_unchanged(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Normal",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.65,
                    "reasoning": "Normal.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert result["candidates"][0]["confidence"] == 0.65

    def test_confidence_1_0_capped(self):
        """AI returning 1.0 confidence gets capped."""
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Full confidence",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 1.0,
                    "reasoning": "Impossible confidence.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert result["candidates"][0]["confidence"] == AI_CONFIDENCE_CEILING

    def test_integer_confidence_converted(self):
        """Integer confidence gets converted to float."""
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Integer",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 1,
                    "reasoning": "Int.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert result["candidates"][0]["confidence"] == AI_CONFIDENCE_CEILING
        assert isinstance(result["candidates"][0]["confidence"], float)


# =============================================================================
# TestParseResult — malformed input
# =============================================================================


class TestParseResultMalformed:
    def test_non_dict_input(self):
        task = DependencyResolutionTask()
        result = task.parse_result("not a dict")
        assert result["candidates"] == []

    def test_missing_candidates_key(self):
        task = DependencyResolutionTask()
        result = task.parse_result({"search_summary": "found nothing"})
        assert result["candidates"] == []

    def test_candidates_not_a_list(self):
        task = DependencyResolutionTask()
        result = task.parse_result({"candidates": "wrong"})
        assert result["candidates"] == []

    def test_non_dict_candidates_filtered(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                "not a dict",
                42,
                None,
                {
                    "display_name": "Valid",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.70,
                    "reasoning": "Good.",
                },
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["display_name"] == "Valid"

    def test_non_numeric_confidence_treated_as_zero(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Bad conf",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": "high",
                    "reasoning": "Bad.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert result["candidates"][0]["confidence"] == 0.0

    def test_missing_search_summary_defaults_empty(self):
        task = DependencyResolutionTask()
        raw = {"candidates": []}
        result = task.parse_result(raw)
        assert result["search_summary"] == ""


# =============================================================================
# TestParseResult — field validation
# =============================================================================


class TestParseResultFieldValidation:
    def test_civitai_missing_model_id_rejected(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "No model_id",
                    "provider": "civitai",
                    # missing model_id
                    "confidence": 0.80,
                    "reasoning": "Missing field.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 0

    def test_huggingface_missing_repo_id_rejected(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "No repo_id",
                    "provider": "huggingface",
                    # missing repo_id
                    "filename": "model.safetensors",
                    "confidence": 0.70,
                    "reasoning": "Missing.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 0

    def test_huggingface_missing_filename_rejected(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "No filename",
                    "provider": "huggingface",
                    "repo_id": "org/repo",
                    # missing filename
                    "confidence": 0.70,
                    "reasoning": "Missing.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 0

    def test_unknown_provider_only_needs_common_fields(self):
        """Unknown provider just needs display_name, provider, confidence, reasoning."""
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Some model",
                    "provider": "other",
                    "confidence": 0.50,
                    "reasoning": "Unknown source.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 1

    def test_missing_display_name_rejected_for_any_provider(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    # missing display_name
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.80,
                    "reasoning": "No name.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 0

    def test_missing_reasoning_rejected(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "No reasoning",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.80,
                    # missing reasoning
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 0

    def test_valid_civitai_with_all_fields_accepted(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Full Civitai",
                    "provider": "civitai",
                    "model_id": 123,
                    "version_id": 456,
                    "file_id": 789,
                    "base_model": "SDXL",
                    "confidence": 0.85,
                    "reasoning": "All fields present.",
                }
            ],
        }
        result = task.parse_result(raw)
        assert len(result["candidates"]) == 1
        c = result["candidates"][0]
        assert c["version_id"] == 456
        assert c["file_id"] == 789
        assert c["base_model"] == "SDXL"


# =============================================================================
# TestValidateOutput
# =============================================================================


class TestValidateOutput:
    def test_valid_with_candidates(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {
                    "display_name": "Model",
                    "confidence": 0.80,
                }
            ],
        }
        assert task.validate_output(output) is True

    def test_valid_empty_candidates(self):
        """Empty candidates is valid — means no match found."""
        task = DependencyResolutionTask()
        output = {"candidates": [], "search_summary": "Nothing found."}
        assert task.validate_output(output) is True

    def test_invalid_non_dict(self):
        task = DependencyResolutionTask()
        assert task.validate_output("string") is False
        assert task.validate_output(42) is False
        assert task.validate_output(None) is False
        assert task.validate_output([]) is False

    def test_invalid_missing_candidates_key(self):
        task = DependencyResolutionTask()
        assert task.validate_output({"search_summary": "x"}) is False

    def test_invalid_candidates_not_list(self):
        task = DependencyResolutionTask()
        assert task.validate_output({"candidates": "wrong"}) is False

    def test_invalid_candidate_not_dict(self):
        task = DependencyResolutionTask()
        assert task.validate_output({"candidates": ["string"]}) is False

    def test_invalid_confidence_above_ceiling(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {"display_name": "X", "confidence": 0.95}
            ],
        }
        assert task.validate_output(output) is False

    def test_invalid_negative_confidence(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {"display_name": "X", "confidence": -0.1}
            ],
        }
        assert task.validate_output(output) is False

    def test_invalid_non_numeric_confidence(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {"display_name": "X", "confidence": "high"}
            ],
        }
        assert task.validate_output(output) is False

    def test_invalid_missing_display_name(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {"confidence": 0.80}
            ],
        }
        assert task.validate_output(output) is False

    def test_valid_at_ceiling(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {"display_name": "X", "confidence": 0.89}
            ],
        }
        assert task.validate_output(output) is True

    def test_valid_at_zero(self):
        task = DependencyResolutionTask()
        output = {
            "candidates": [
                {"display_name": "X", "confidence": 0.0}
            ],
        }
        assert task.validate_output(output) is True


# =============================================================================
# TestParseResultIdempotent
# =============================================================================


class TestParseResultIdempotent:
    def test_parse_result_idempotent(self):
        """parse_result(parse_result(x)) == parse_result(x)."""
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "RealVisXL V4.0",
                    "provider": "civitai",
                    "model_id": 139562,
                    "version_id": 789012,
                    "file_id": 456789,
                    "base_model": "SDXL",
                    "confidence": 0.89,
                    "reasoning": "Strong match.",
                },
                {
                    "display_name": "RealVisXL (HF)",
                    "provider": "huggingface",
                    "repo_id": "SG161222/RealVisXL_V4.0",
                    "filename": "RealVisXL_V4.0.safetensors",
                    "confidence": 0.75,
                    "reasoning": "HF match.",
                },
            ],
            "search_summary": "Multi-provider search.",
        }
        first = task.parse_result(raw)
        second = task.parse_result(first)
        assert first == second
