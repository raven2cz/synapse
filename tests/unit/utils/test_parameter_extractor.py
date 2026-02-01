"""
Unit tests for parameter extraction utilities.

Tests cover:
- Parameter key normalization (camelCase, kebab-case, snake_case)
- Value type conversion
- Description parsing for parameters
- Image metadata extraction
- Parameter aggregation from multiple sources

Author: Synapse Team
License: MIT
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils.parameter_extractor import (
    ParameterSourceType,
    ExtractionResult,
    normalize_param_key,
    convert_param_value,
    normalize_params,
    extract_from_description,
    extract_from_image_meta,
    aggregate_from_previews,
    is_generation_param,
    get_applicable_params,
    PARAM_KEY_ALIASES,
)


# =============================================================================
# Key Normalization Tests
# =============================================================================

class TestNormalizeParamKey:
    """Tests for normalize_param_key function."""

    def test_camel_case_to_snake_case(self):
        """CamelCase keys should be converted to snake_case."""
        assert normalize_param_key('cfgScale') == 'cfg_scale'
        assert normalize_param_key('clipSkip') == 'clip_skip'
        assert normalize_param_key('hiresUpscaler') == 'hires_upscaler'
        assert normalize_param_key('loraStrength') == 'strength'

    def test_already_snake_case(self):
        """Snake_case keys should remain unchanged."""
        assert normalize_param_key('cfg_scale') == 'cfg_scale'
        assert normalize_param_key('clip_skip') == 'clip_skip'
        assert normalize_param_key('hires_steps') == 'hires_steps'

    def test_kebab_case_to_snake_case(self):
        """Kebab-case keys should be converted to snake_case."""
        assert normalize_param_key('clip-skip') == 'clip_skip'
        assert normalize_param_key('cfg-scale') == 'cfg_scale'

    def test_uppercase_variants(self):
        """Uppercase keys should be normalized."""
        assert normalize_param_key('STEPS') == 'steps'
        assert normalize_param_key('CFG') == 'cfg_scale'

    def test_alias_mapping(self):
        """Known aliases should map to canonical names."""
        assert normalize_param_key('cfg') == 'cfg_scale'
        assert normalize_param_key('guidance') == 'cfg_scale'
        assert normalize_param_key('guidance_scale') == 'cfg_scale'
        assert normalize_param_key('clip') == 'clip_skip'
        assert normalize_param_key('strength') == 'strength'
        assert normalize_param_key('lora_strength') == 'strength'

    def test_empty_key(self):
        """Empty key should return empty."""
        assert normalize_param_key('') == ''
        assert normalize_param_key(None) is None


# =============================================================================
# Value Conversion Tests
# =============================================================================

class TestConvertParamValue:
    """Tests for convert_param_value function."""

    def test_integer_conversion(self):
        """Integer params should be converted."""
        assert convert_param_value('steps', '25') == 25
        assert convert_param_value('clip_skip', '2') == 2
        assert convert_param_value('seed', '12345') == 12345
        assert convert_param_value('width', '512') == 512

    def test_float_conversion(self):
        """Float params should be converted."""
        assert convert_param_value('cfg_scale', '7.5') == 7.5
        assert convert_param_value('denoise', '0.8') == 0.8
        assert convert_param_value('strength', '1.0') == 1.0

    def test_boolean_conversion(self):
        """Boolean params should be converted."""
        assert convert_param_value('hires_fix', 'true') is True
        assert convert_param_value('hires_fix', 'false') is False
        assert convert_param_value('hires_fix', 'yes') is True
        assert convert_param_value('hires_fix', 'no') is False
        assert convert_param_value('hires_fix', 'enabled') is True

    def test_string_preservation(self):
        """String params should be preserved."""
        assert convert_param_value('sampler', 'euler') == 'euler'
        assert convert_param_value('scheduler', 'karras') == 'karras'

    def test_already_typed(self):
        """Already typed values should pass through."""
        assert convert_param_value('steps', 25) == 25
        assert convert_param_value('cfg_scale', 7.5) == 7.5

    def test_null_values(self):
        """Null values should return None."""
        assert convert_param_value('steps', None) is None


# =============================================================================
# Params Normalization Tests
# =============================================================================

class TestNormalizeParams:
    """Tests for normalize_params function."""

    def test_full_normalization(self):
        """Full dict should be normalized."""
        input_params = {
            'cfgScale': '7',
            'clipSkip': '2',
            'steps': '25',
            'sampler': 'euler',
        }
        result = normalize_params(input_params)

        assert result['cfg_scale'] == 7.0
        assert result['clip_skip'] == 2
        assert result['steps'] == 25
        assert result['sampler'] == 'euler'

    def test_filters_null_values(self):
        """Null/None values should be filtered out."""
        input_params = {
            'steps': '25',
            'cfg_scale': '',
            'sampler': None,
        }
        result = normalize_params(input_params)

        assert 'steps' in result
        assert 'cfg_scale' not in result
        assert 'sampler' not in result


# =============================================================================
# Description Extraction Tests
# =============================================================================

class TestExtractFromDescription:
    """Tests for extract_from_description function."""

    def test_basic_extraction(self):
        """Basic parameter patterns should be extracted."""
        description = "Recommended: CFG 7, Steps 25, Clip Skip 2"
        result = extract_from_description(description)

        assert result.parameters.get('cfg_scale') == 7.0
        assert result.parameters.get('steps') == 25
        assert result.parameters.get('clip_skip') == 2
        assert result.source == ParameterSourceType.DESCRIPTION

    def test_various_formats(self):
        """Various format patterns should be extracted."""
        descriptions = [
            ("Use with strength 0.8", {'strength': 0.8}),
            ("sampler: euler", {'sampler': 'euler'}),
            ("cfg scale: 7.5", {'cfg_scale': 7.5}),
            ("denoise: 0.7", {'denoise': 0.7}),
        ]

        for desc, expected in descriptions:
            result = extract_from_description(desc)
            for key, value in expected.items():
                assert result.parameters.get(key) == value, f"Failed for: {desc}"

    def test_html_stripping(self):
        """HTML tags should be stripped before parsing."""
        description = "<p>Settings: <b>sampler</b>: euler, <i>steps</i>: 30</p>"
        result = extract_from_description(description)

        assert result.parameters.get('sampler') == 'euler'
        assert result.parameters.get('steps') == 30

    def test_empty_description(self):
        """Empty description should return empty result."""
        result = extract_from_description("")
        assert result.parameters == {}
        # Default confidence is 1.0 for empty result
        assert result.source == ParameterSourceType.DESCRIPTION

    def test_no_parameters_found(self):
        """Description without parameters should return empty."""
        description = "This is a great model for portraits!"
        result = extract_from_description(description)

        assert result.parameters == {}


# =============================================================================
# Image Meta Extraction Tests
# =============================================================================

class TestExtractFromImageMeta:
    """Tests for extract_from_image_meta function."""

    def test_basic_extraction(self):
        """Basic metadata should be extracted and normalized."""
        meta = {
            'cfgScale': 7,
            'steps': 25,
            'seed': 12345,
            'sampler': 'euler',
            'prompt': 'beautiful landscape...',  # Should be excluded
        }
        result = extract_from_image_meta(meta)

        assert result.parameters.get('cfg_scale') == 7
        assert result.parameters.get('steps') == 25
        assert result.parameters.get('seed') == 12345
        assert result.parameters.get('sampler') == 'euler'
        assert 'prompt' not in result.parameters

    def test_excludes_prompts(self):
        """Prompts should be excluded."""
        meta = {
            'prompt': 'test prompt',
            'negativePrompt': 'bad things',
            'negative_prompt': 'ugly',
            'steps': 20,
        }
        result = extract_from_image_meta(meta)

        assert 'prompt' not in result.parameters
        assert 'negativePrompt' not in result.parameters
        assert 'negative_prompt' not in result.parameters
        assert result.parameters.get('steps') == 20

    def test_excludes_resources(self):
        """Resources should be excluded."""
        meta = {
            'resources': [{'name': 'lora1', 'type': 'lora'}],
            'civitaiResources': [{'id': 123}],
            'steps': 20,
        }
        result = extract_from_image_meta(meta)

        assert 'resources' not in result.parameters
        assert 'civitaiResources' not in result.parameters
        assert result.parameters.get('steps') == 20

    def test_empty_meta(self):
        """Empty meta should return empty result."""
        result = extract_from_image_meta({})
        assert result.parameters == {}

        result = extract_from_image_meta(None)
        assert result.parameters == {}


# =============================================================================
# Aggregation Tests
# =============================================================================

class TestAggregateFromPreviews:
    """Tests for aggregate_from_previews function."""

    def test_mode_aggregation(self):
        """Mode strategy should select most common value."""
        previews = [
            {'meta': {'steps': 25, 'cfgScale': 7}},
            {'meta': {'steps': 30, 'cfgScale': 7}},
            {'meta': {'steps': 25, 'cfgScale': 7}},
        ]
        result = aggregate_from_previews(previews, strategy='mode')

        assert result.parameters.get('steps') == 25  # Mode is 25
        assert result.parameters.get('cfg_scale') == 7.0  # All same
        assert result.source == ParameterSourceType.AGGREGATED

    def test_average_aggregation(self):
        """Average strategy should calculate mean."""
        previews = [
            {'meta': {'steps': 20, 'cfgScale': 6}},
            {'meta': {'steps': 30, 'cfgScale': 8}},
        ]
        result = aggregate_from_previews(previews, strategy='average')

        assert result.parameters.get('steps') == 25  # Average, rounded
        assert result.parameters.get('cfg_scale') == 7.0  # Average

    def test_confidence_calculation(self):
        """Confidence should reflect value consistency."""
        # All same values = high confidence
        previews_same = [
            {'meta': {'cfgScale': 7}},
            {'meta': {'cfgScale': 7}},
            {'meta': {'cfgScale': 7}},
        ]
        result_same = aggregate_from_previews(previews_same)
        # Result has overall confidence, parameters should have cfg_scale
        assert result_same.parameters.get('cfg_scale') == 7.0
        assert result_same.confidence == 1.0  # Overall confidence

        # Mixed values - mode still picks most common
        previews_mixed = [
            {'meta': {'cfgScale': 7}},
            {'meta': {'cfgScale': 8}},
            {'meta': {'cfgScale': 7}},
        ]
        result_mixed = aggregate_from_previews(previews_mixed)
        assert result_mixed.parameters.get('cfg_scale') == 7.0  # Mode

    def test_empty_previews(self):
        """Empty previews should return empty result."""
        result = aggregate_from_previews([])
        assert result.parameters == {}
        assert result.source == ParameterSourceType.AGGREGATED

    def test_previews_without_meta(self):
        """Previews without meta should be skipped."""
        previews = [
            {'url': 'test.jpg'},  # No meta
            {'meta': {'steps': 25}},
            {'meta': None},  # Null meta
        ]
        result = aggregate_from_previews(previews)

        assert result.parameters.get('steps') == 25
        assert result.source == ParameterSourceType.AGGREGATED


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestIsGenerationParam:
    """Tests for is_generation_param function."""

    def test_known_params(self):
        """Known generation params should return True."""
        params = ['steps', 'cfg_scale', 'sampler', 'seed', 'clip_skip', 'denoise']
        for param in params:
            assert is_generation_param(param) is True, f"Failed for {param}"

    def test_excluded_params(self):
        """Excluded params should return False."""
        # Note: 'Model' is matched via alias to 'base_model', so it returns True
        params = ['prompt', 'negativePrompt', 'resources']
        for param in params:
            assert is_generation_param(param) is False, f"Failed for {param}"


class TestGetApplicableParams:
    """Tests for get_applicable_params function."""

    def test_filters_correctly(self):
        """Should filter and normalize applicable params."""
        meta = {
            'cfgScale': 7,
            'steps': 25,
            'prompt': 'test',
            'resources': [],
        }
        result = get_applicable_params(meta)

        assert 'cfg_scale' in result
        assert 'steps' in result
        assert 'prompt' not in result
        assert 'resources' not in result


# =============================================================================
# Integration Tests
# =============================================================================

class TestParameterExtractionIntegration:
    """Integration tests combining multiple functions."""

    def test_civitai_style_metadata(self):
        """Should handle real Civitai-style metadata."""
        meta = {
            'prompt': 'beautiful landscape, mountains, sunset, masterpiece',
            'negativePrompt': 'ugly, blurry, low quality',
            'cfgScale': 7,
            'steps': 25,
            'sampler': 'DPM++ 2M Karras',
            'seed': 1234567890,
            'clipSkip': 2,
            'Size': '512x768',
            'Model': 'dreamshaper_8',
            'resources': [
                {'name': 'dreamshaper_8', 'type': 'model'},
                {'name': 'detail_enhancer', 'type': 'lora', 'weight': 0.8},
            ],
        }

        result = extract_from_image_meta(meta)

        # Should extract generation params
        assert result.parameters.get('cfg_scale') == 7
        assert result.parameters.get('steps') == 25
        assert result.parameters.get('sampler') == 'DPM++ 2M Karras'
        assert result.parameters.get('seed') == 1234567890
        assert result.parameters.get('clip_skip') == 2

        # Should exclude non-generation data
        assert 'prompt' not in result.parameters
        assert 'negativePrompt' not in result.parameters
        assert 'Model' not in result.parameters
        assert 'resources' not in result.parameters

    def test_description_to_parameters_flow(self):
        """Should extract and normalize params from description."""
        # Use format that matches the regex patterns
        description = """
        Recommended Settings:
        cfg scale: 7, steps: 25, clip skip: 2, strength: 0.8
        """

        result = extract_from_description(description)

        assert result.parameters.get('cfg_scale') == 7.0
        assert result.parameters.get('steps') == 25
        assert result.parameters.get('clip_skip') == 2
        assert result.parameters.get('strength') == 0.8
