"""
Parameter Extraction Utilities

Provides functions for extracting and normalizing generation parameters
from various sources (descriptions, image metadata, etc.).

Key Features:
- Regex-based parameter extraction from Civitai descriptions
- Parameter key normalization (camelCase → snake_case)
- Type conversion for parameter values
- Aggregation of parameters from multiple sources

Author: Synapse Team
License: MIT
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Enums & Data Classes
# =============================================================================

class ParameterSourceType(Enum):
    """Source from which parameters were extracted."""
    DESCRIPTION = "description"
    IMAGE = "image"
    AGGREGATED = "aggregated"
    MANUAL = "manual"


@dataclass
class ExtractionResult:
    """
    Result of parameter extraction.

    Attributes:
        parameters: Extracted parameter key-value pairs
        source: Where parameters were extracted from
        confidence: Confidence level (0.0-1.0) for aggregated results
        raw_matches: Original regex matches for debugging
    """
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: ParameterSourceType = ParameterSourceType.MANUAL
    confidence: float = 1.0
    raw_matches: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# Constants
# =============================================================================

# Key name aliases - maps various formats to canonical snake_case
PARAM_KEY_ALIASES: Dict[str, str] = {
    # CFG Scale variants
    'cfg': 'cfg_scale',
    'cfgscale': 'cfg_scale',
    'cfg_scale': 'cfg_scale',
    'cfgScale': 'cfg_scale',
    'guidance': 'cfg_scale',
    'guidance_scale': 'cfg_scale',

    # Clip Skip variants
    'clipskip': 'clip_skip',
    'clip_skip': 'clip_skip',
    'clipSkip': 'clip_skip',
    'clip': 'clip_skip',

    # Steps variants
    'steps': 'steps',
    'num_steps': 'steps',
    'numSteps': 'steps',
    'sampling_steps': 'steps',

    # Sampler variants
    'sampler': 'sampler',
    'sampler_name': 'sampler',
    'samplerName': 'sampler',
    'sampling_method': 'sampler',

    # Scheduler variants
    'scheduler': 'scheduler',
    'schedule': 'scheduler',
    'schedule_type': 'scheduler',

    # Seed variants
    'seed': 'seed',
    'noise_seed': 'seed',

    # Denoise/Strength variants
    'denoise': 'denoise',
    'denoising': 'denoise',
    'denoising_strength': 'denoise',
    'strength': 'strength',
    'lora_strength': 'strength',
    'loraStrength': 'strength',

    # Resolution variants
    'width': 'width',
    'w': 'width',
    'height': 'height',
    'h': 'height',
    'size': 'size',

    # HiRes variants
    'hires_fix': 'hires_fix',
    'hiresFix': 'hires_fix',
    'hiresfix': 'hires_fix',
    'highres_fix': 'hires_fix',
    'hires_upscaler': 'hires_upscaler',
    'hiresUpscaler': 'hires_upscaler',
    'hires_upscale': 'hires_scale',
    'hiresUpscale': 'hires_scale',
    'hires_scale': 'hires_scale',
    'hires_steps': 'hires_steps',
    'hiresSteps': 'hires_steps',
    'hires_denoise': 'hires_denoise',
    'hiresDenoise': 'hires_denoise',

    # VAE variants
    'vae': 'vae',
    'vae_name': 'vae',
    'vaeName': 'vae',

    # Model variants
    'model': 'base_model',
    'model_name': 'base_model',
    'modelName': 'base_model',
    'base_model': 'base_model',
    'checkpoint': 'base_model',
}

# Parameters that should be numeric (int or float)
NUMERIC_PARAMS = {
    'cfg_scale', 'clip_skip', 'steps', 'seed', 'denoise', 'strength',
    'width', 'height', 'hires_scale', 'hires_steps', 'hires_denoise',
}

# Parameters that should be integers
INTEGER_PARAMS = {
    'clip_skip', 'steps', 'seed', 'width', 'height', 'hires_steps',
}

# Parameters that should be booleans
BOOLEAN_PARAMS = {
    'hires_fix',
}

# Regex patterns for extracting parameters from description text
DESCRIPTION_PATTERNS: Dict[str, str] = {
    'cfg_scale': r'(?:cfg|cfg\s*scale|guidance)[:\s=]+(\d+(?:\.\d+)?)',
    'steps': r'(?:steps|sampling\s*steps)[:\s=]+(\d+)',
    'sampler': r'(?:sampler|sampling\s*method)[:\s=]+([a-zA-Z0-9_\s]+?)(?:[,\n\.]|$)',
    'scheduler': r'(?:scheduler|schedule)[:\s=]+([a-zA-Z0-9_]+)',
    'clip_skip': r'(?:clip\s*skip|clipskip)[:\s=]+(\d+)',
    'strength': r'(?:(?:lora\s*)?strength|weight)[:\s=]+([\d.]+)',
    'denoise': r'(?:denoise|denoising)[:\s=]+([\d.]+)',
    'width': r'(?:width|w)[:\s=]+(\d+)',
    'height': r'(?:height|h)[:\s=]+(\d+)',
    'seed': r'(?:seed)[:\s=]+(-?\d+)',
    'hires_fix': r'(?:hires\s*fix|highres)[:\s=]+(true|false|yes|no|enabled?|disabled?)',
    'hires_scale': r'(?:hires\s*(?:scale|upscale))[:\s=]+([\d.]+)',
    'hires_steps': r'(?:hires\s*steps)[:\s=]+(\d+)',
    'hires_denoise': r'(?:hires\s*denoise)[:\s=]+([\d.]+)',
}

# Patterns that indicate a "recommended settings" section in description
RECOMMENDED_SECTION_PATTERNS = [
    r'recommended\s*(?:settings?|params?|parameters?)?[:\s]*',
    r'(?:use|try)\s*with[:\s]*',
    r'suggested\s*(?:settings?|params?)?[:\s]*',
    r'best\s*(?:settings?|results?)[:\s]*',
]


# =============================================================================
# Normalization Functions
# =============================================================================

def normalize_param_key(key: str) -> str:
    """
    Normalize parameter key to canonical snake_case format.

    Args:
        key: Parameter key in any format (camelCase, kebab-case, etc.)

    Returns:
        Normalized snake_case key

    Example:
        >>> normalize_param_key('cfgScale')
        'cfg_scale'
        >>> normalize_param_key('clip-skip')
        'clip_skip'
    """
    if not key:
        return key

    # Check direct alias match first
    lower_key = key.lower().replace('-', '_').replace(' ', '_')
    if lower_key in PARAM_KEY_ALIASES:
        return PARAM_KEY_ALIASES[lower_key]

    # Check original key
    if key in PARAM_KEY_ALIASES:
        return PARAM_KEY_ALIASES[key]

    # Convert camelCase to snake_case
    # Insert underscore before uppercase letters
    snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', key)
    snake = snake.lower().replace('-', '_').replace(' ', '_')

    # Check if converted key has alias
    if snake in PARAM_KEY_ALIASES:
        return PARAM_KEY_ALIASES[snake]

    return snake


def convert_param_value(key: str, value: Any) -> Any:
    """
    Convert parameter value to appropriate type.

    Args:
        key: Normalized parameter key
        value: Raw value (usually string)

    Returns:
        Value converted to appropriate type (int, float, bool, str)

    Example:
        >>> convert_param_value('steps', '25')
        25
        >>> convert_param_value('cfg_scale', '7.5')
        7.5
        >>> convert_param_value('hires_fix', 'true')
        True
    """
    if value is None:
        return None

    # Already correct type
    if isinstance(value, (int, float, bool)) and not isinstance(value, str):
        return value

    # Convert string values
    str_value = str(value).strip().lower()

    # Boolean conversion
    if key in BOOLEAN_PARAMS:
        return str_value in ('true', 'yes', 'enabled', 'enable', '1', 'on')

    # Integer conversion
    if key in INTEGER_PARAMS:
        try:
            return int(float(str_value))
        except (ValueError, TypeError):
            return None

    # Float conversion for other numeric params
    if key in NUMERIC_PARAMS:
        try:
            return float(str_value)
        except (ValueError, TypeError):
            return None

    # String - preserve original case for non-numeric params
    return str(value).strip() if value else None


def normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize all parameter keys and convert values.

    Args:
        params: Dictionary with parameter key-value pairs

    Returns:
        Dictionary with normalized keys and converted values

    Example:
        >>> normalize_params({'cfgScale': '7', 'clipSkip': '2'})
        {'cfg_scale': 7.0, 'clip_skip': 2}
    """
    result = {}
    for key, value in params.items():
        normalized_key = normalize_param_key(key)
        converted_value = convert_param_value(normalized_key, value)
        if converted_value is not None:
            result[normalized_key] = converted_value
    return result


# =============================================================================
# Extraction Functions
# =============================================================================

def extract_from_description(description: str) -> ExtractionResult:
    """
    Extract generation parameters from Civitai model description.

    Parses description text looking for common parameter patterns like:
    - "Recommended: CFG 7, Steps 25"
    - "Settings: sampler: euler, clip skip: 2"
    - "Use with: strength 0.8"

    Args:
        description: Model description text (may contain HTML)

    Returns:
        ExtractionResult with found parameters

    Example:
        >>> result = extract_from_description("Use with CFG 7, Steps 25, Clip Skip 2")
        >>> result.parameters
        {'cfg_scale': 7.0, 'steps': 25, 'clip_skip': 2}
    """
    if not description:
        return ExtractionResult(source=ParameterSourceType.DESCRIPTION)

    # Strip HTML tags for cleaner matching
    clean_text = re.sub(r'<[^>]+>', ' ', description)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    parameters = {}
    raw_matches = {}

    # Look for parameters in the text
    for param_key, pattern in DESCRIPTION_PATTERNS.items():
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            raw_value = match.group(1).strip()
            raw_matches[param_key] = raw_value

            converted = convert_param_value(param_key, raw_value)
            if converted is not None:
                parameters[param_key] = converted
                logger.debug(f"Extracted {param_key}={converted} from description")

    return ExtractionResult(
        parameters=parameters,
        source=ParameterSourceType.DESCRIPTION,
        confidence=1.0 if parameters else 0.0,
        raw_matches=raw_matches,
    )


def extract_from_image_meta(meta: Dict[str, Any]) -> ExtractionResult:
    """
    Extract and normalize generation parameters from image metadata.

    Image metadata from Civitai contains generation parameters used
    to create that specific image. This function filters and normalizes
    those parameters.

    Args:
        meta: Image metadata dictionary from Civitai API

    Returns:
        ExtractionResult with normalized parameters

    Example:
        >>> meta = {'cfgScale': 7, 'steps': 25, 'prompt': 'beautiful...'}
        >>> result = extract_from_image_meta(meta)
        >>> result.parameters
        {'cfg_scale': 7.0, 'steps': 25}  # prompt excluded
    """
    if not meta:
        return ExtractionResult(source=ParameterSourceType.IMAGE)

    # Keys to exclude (not generation parameters)
    EXCLUDE_KEYS = {
        'prompt', 'negativePrompt', 'negative_prompt',
        'resources', 'civitaiResources',
        'hash', 'hashes',
        'Model', 'model', 'model_name',  # We handle base_model separately
    }

    # Filter and normalize
    parameters = {}
    for key, value in meta.items():
        if key in EXCLUDE_KEYS:
            continue
        if value is None or value == '':
            continue

        normalized_key = normalize_param_key(key)
        converted_value = convert_param_value(normalized_key, value)

        if converted_value is not None:
            parameters[normalized_key] = converted_value

    return ExtractionResult(
        parameters=parameters,
        source=ParameterSourceType.IMAGE,
        confidence=1.0,
    )


def aggregate_from_previews(
    previews: List[Dict[str, Any]],
    strategy: str = 'mode',
) -> ExtractionResult:
    """
    Aggregate parameters from multiple preview images.

    Useful for finding "typical" parameters used with a model
    across multiple example images.

    Args:
        previews: List of preview objects with 'meta' field
        strategy: Aggregation strategy ('mode' for most common, 'average' for mean)

    Returns:
        ExtractionResult with aggregated parameters and confidence scores

    Example:
        >>> previews = [
        ...     {'meta': {'steps': 25, 'cfgScale': 7}},
        ...     {'meta': {'steps': 30, 'cfgScale': 7}},
        ...     {'meta': {'steps': 25, 'cfgScale': 7}},
        ... ]
        >>> result = aggregate_from_previews(previews)
        >>> result.parameters
        {'steps': 25, 'cfg_scale': 7.0}  # mode values
    """
    if not previews:
        return ExtractionResult(source=ParameterSourceType.AGGREGATED)

    # Collect all values for each parameter
    param_values: Dict[str, List[Any]] = {}

    for preview in previews:
        meta = preview.get('meta', {})
        if not meta:
            continue

        extraction = extract_from_image_meta(meta)
        for key, value in extraction.parameters.items():
            if key not in param_values:
                param_values[key] = []
            param_values[key].append(value)

    if not param_values:
        return ExtractionResult(source=ParameterSourceType.AGGREGATED)

    # Aggregate values
    parameters = {}
    confidences = {}

    for key, values in param_values.items():
        if not values:
            continue

        if strategy == 'average' and key in NUMERIC_PARAMS:
            # Calculate average for numeric params
            try:
                avg = sum(float(v) for v in values) / len(values)
                if key in INTEGER_PARAMS:
                    parameters[key] = round(avg)
                else:
                    parameters[key] = round(avg, 2)
                # Confidence based on variance
                variance = sum((float(v) - avg) ** 2 for v in values) / len(values)
                confidences[key] = max(0, 1 - (variance / (avg + 1)))
            except (ValueError, TypeError, ZeroDivisionError):
                continue
        else:
            # Use mode (most common value)
            from collections import Counter
            counter = Counter(values)
            most_common_value, most_common_count = counter.most_common(1)[0]
            parameters[key] = most_common_value
            # Confidence = ratio of most common to total
            confidences[key] = most_common_count / len(values)

    # Overall confidence is average of individual confidences
    overall_confidence = sum(confidences.values()) / len(confidences) if confidences else 0

    return ExtractionResult(
        parameters=parameters,
        source=ParameterSourceType.AGGREGATED,
        confidence=overall_confidence,
    )


# =============================================================================
# Utility Functions
# =============================================================================

def is_generation_param(key: str) -> bool:
    """
    Check if a key is a known generation parameter.

    Args:
        key: Parameter key to check

    Returns:
        True if key is a generation parameter
    """
    normalized = normalize_param_key(key)
    return (
        normalized in PARAM_KEY_ALIASES.values() or
        normalized in NUMERIC_PARAMS or
        normalized in BOOLEAN_PARAMS
    )


def get_applicable_params(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter metadata to only include applicable generation parameters.

    Excludes prompts, resources, and other non-applicable data.

    Args:
        meta: Full metadata dictionary

    Returns:
        Filtered dictionary with only generation parameters
    """
    result = extract_from_image_meta(meta)
    return result.parameters


# =============================================================================
# Testing Helpers
# =============================================================================

def _test_extraction():
    """Run basic extraction tests (for development)."""
    test_descriptions = [
        "Recommended: CFG 7, Steps 25, Clip Skip 2",
        "Use with strength 0.8 and sampler euler",
        "Best results with cfg_scale: 7.5, steps: 30",
        "<p>Settings: sampler: dpmpp_2m, scheduler: karras</p>",
        "No parameters mentioned here",
    ]

    print("Description extraction tests:")
    for desc in test_descriptions:
        result = extract_from_description(desc)
        print(f"  Input: {desc[:50]}...")
        print(f"  Found: {result.parameters}")
        print()

    print("\nKey normalization tests:")
    test_keys = ['cfgScale', 'clip-skip', 'hiresUpscaler', 'STEPS', 'loraStrength']
    for key in test_keys:
        normalized = normalize_param_key(key)
        print(f"  {key:20} -> {normalized}")


if __name__ == "__main__":
    _test_extraction()
