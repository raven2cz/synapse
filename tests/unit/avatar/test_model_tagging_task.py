"""
Unit tests for ModelTaggingTask.

Tests the task class in isolation — build_system_prompt, parse_result,
validate_output, get_fallback, keyword extraction.
"""

import pytest

from src.avatar.tasks.base import TaskResult
from src.avatar.tasks.model_tagging import (
    TAGGING_PROMPT,
    ModelTaggingTask,
    _extract_tags_by_keywords,
)


# =============================================================================
# TestModelTaggingTaskAttributes
# =============================================================================


class TestModelTaggingTaskAttributes:
    def test_task_type(self):
        task = ModelTaggingTask()
        assert task.task_type == "model_tagging"

    def test_skill_names(self):
        task = ModelTaggingTask()
        assert isinstance(task.SKILL_NAMES, tuple)
        assert "generation-params" in task.SKILL_NAMES

    def test_cache_prefix(self):
        task = ModelTaggingTask()
        assert task.get_cache_prefix() == "model_tagging"


# =============================================================================
# TestBuildSystemPrompt
# =============================================================================


class TestBuildSystemPrompt:
    def test_includes_tagging_prompt(self):
        task = ModelTaggingTask()
        prompt = task.build_system_prompt("")
        assert TAGGING_PROMPT in prompt

    def test_empty_skills_no_reference(self):
        task = ModelTaggingTask()
        prompt = task.build_system_prompt("")
        assert "Reference Knowledge" not in prompt

    def test_skills_appended(self):
        task = ModelTaggingTask()
        prompt = task.build_system_prompt("# Some skill content")
        assert "Reference Knowledge" in prompt
        assert "Some skill content" in prompt


# =============================================================================
# TestParseResult
# =============================================================================


class TestParseResult:
    def test_full_valid_input(self):
        task = ModelTaggingTask()
        result = task.parse_result({
            "category": "Anime",
            "content_types": ["Character", "Portrait"],
            "tags": ["lora", "sdxl"],
            "trigger_words": ["anime girl"],
            "base_model_hint": "SDXL",
        })
        assert result["category"] == "anime"
        assert result["content_types"] == ["character", "portrait"]
        assert result["tags"] == ["lora", "sdxl"]
        assert result["trigger_words"] == ["anime girl"]
        assert result["base_model_hint"] == "SDXL"

    def test_unknown_category_becomes_other(self):
        task = ModelTaggingTask()
        result = task.parse_result({"category": "unknown_style"})
        assert result["category"] == "other"

    def test_category_case_insensitive(self):
        task = ModelTaggingTask()
        for variant in ["ANIME", "Anime", "anime", " anime "]:
            result = task.parse_result({"category": variant})
            assert result["category"] == "anime"

    def test_non_dict_returns_empty(self):
        task = ModelTaggingTask()
        assert task.parse_result("string") == {}
        assert task.parse_result(42) == {}
        assert task.parse_result(None) == {}
        assert task.parse_result([]) == {}

    def test_tags_as_comma_string(self):
        task = ModelTaggingTask()
        result = task.parse_result({"tags": "anime, lora, sdxl"})
        assert result["tags"] == ["anime", "lora", "sdxl"]

    def test_content_types_as_string(self):
        task = ModelTaggingTask()
        result = task.parse_result({"content_types": "character"})
        assert result["content_types"] == ["character"]

    def test_trigger_words_as_comma_string(self):
        task = ModelTaggingTask()
        result = task.parse_result({"trigger_words": "word1, word2"})
        assert result["trigger_words"] == ["word1", "word2"]

    def test_empty_strings_filtered(self):
        task = ModelTaggingTask()
        result = task.parse_result({
            "tags": ["valid", "", "  ", "also valid"],
            "content_types": ["", "character"],
        })
        assert result["tags"] == ["valid", "also valid"]
        assert result["content_types"] == ["character"]

    def test_non_string_list_items_filtered(self):
        task = ModelTaggingTask()
        result = task.parse_result({
            "tags": ["valid", 42, None, "also valid"],
        })
        assert result["tags"] == ["valid", "also valid"]

    def test_empty_base_model_hint_omitted(self):
        task = ModelTaggingTask()
        result = task.parse_result({"category": "anime", "base_model_hint": ""})
        assert "base_model_hint" not in result

    def test_idempotent(self):
        """parse_result(parse_result(x)) == parse_result(x)."""
        task = ModelTaggingTask()
        raw = {
            "category": "Anime",
            "content_types": ["Character"],
            "tags": ["lora"],
            "trigger_words": ["girl"],
            "base_model_hint": "SDXL",
        }
        first = task.parse_result(raw)
        second = task.parse_result(first)
        assert first == second


# =============================================================================
# TestValidateOutput
# =============================================================================


class TestValidateOutput:
    def test_with_category_valid(self):
        task = ModelTaggingTask()
        assert task.validate_output({"category": "anime"}) is True

    def test_with_tags_valid(self):
        task = ModelTaggingTask()
        assert task.validate_output({"tags": ["lora"]}) is True

    def test_with_content_types_valid(self):
        task = ModelTaggingTask()
        assert task.validate_output({"content_types": ["character"]}) is True

    def test_empty_dict_invalid(self):
        task = ModelTaggingTask()
        assert task.validate_output({}) is False

    def test_none_invalid(self):
        task = ModelTaggingTask()
        assert task.validate_output(None) is False

    def test_non_dict_invalid(self):
        task = ModelTaggingTask()
        assert task.validate_output("string") is False


# =============================================================================
# TestGetFallback
# =============================================================================


class TestGetFallback:
    def test_returns_callable(self):
        task = ModelTaggingTask()
        fb = task.get_fallback()
        assert fb is not None
        assert callable(fb)

    def test_fallback_extracts_anime(self):
        task = ModelTaggingTask()
        fb = task.get_fallback()
        result = fb("Anime style SDXL LoRA")
        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.output["category"] == "anime"
        assert result.provider_id == "rule_based"

    def test_fallback_extracts_trigger_words(self):
        task = ModelTaggingTask()
        fb = task.get_fallback()
        result = fb("Trigger words: anime girl, detailed eyes")
        assert result.success is True
        assert "anime girl" in result.output["trigger_words"]
        assert "detailed eyes" in result.output["trigger_words"]

    def test_fallback_no_keywords_fails(self):
        task = ModelTaggingTask()
        fb = task.get_fallback()
        result = fb("xyz 123 no keywords here at all")
        assert result.success is False


# =============================================================================
# TestKeywordExtraction (standalone function)
# =============================================================================


class TestKeywordExtraction:
    def test_anime_detection(self):
        tags = _extract_tags_by_keywords("This is an anime style model")
        assert tags["category"] == "anime"

    def test_photorealistic_detection(self):
        tags = _extract_tags_by_keywords("Photorealistic portrait model")
        assert tags["category"] == "photorealistic"
        assert "portrait" in tags["content_types"]

    def test_trigger_word_extraction(self):
        tags = _extract_tags_by_keywords(
            "Trigger words: anime girl, detailed eyes, 4k"
        )
        assert "anime girl" in tags["trigger_words"]
        assert "detailed eyes" in tags["trigger_words"]

    def test_trigger_word_colon_format(self):
        tags = _extract_tags_by_keywords("trigger: my_activation_word")
        assert "my_activation_word" in tags["trigger_words"]

    def test_multiple_content_types(self):
        tags = _extract_tags_by_keywords(
            "Full body character portrait model for landscapes"
        )
        assert "character" in tags["content_types"]
        assert "portrait" in tags["content_types"]
        assert "landscape" in tags["content_types"]
        assert "full-body" in tags["content_types"]

    def test_no_keywords_returns_empty(self):
        tags = _extract_tags_by_keywords("xyz 123 nothing relevant")
        assert "category" not in tags
        assert "content_types" not in tags

    def test_nsfw_detection(self):
        tags = _extract_tags_by_keywords("NSFW adult content model")
        assert "nsfw" in tags["content_types"]

    def test_3d_category(self):
        tags = _extract_tags_by_keywords("3D render model for Blender")
        assert tags["category"] == "3d"

    def test_concept_art_category(self):
        tags = _extract_tags_by_keywords("Concept art style illustrations")
        assert tags["category"] == "concept-art"
