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
from typing import Any, Dict, List, Optional, Tuple, Union

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

# Known sampler names for dictionary matching (most specific first)
KNOWN_SAMPLERS = [
    # DPM++ variants (most specific first)
    'dpm++ 2m sde karras', 'dpm++ 2m karras', 'dpm++ 2m sde', 'dpm++ 2m',
    'dpm++ 2s a karras', 'dpm++ 2s a', 'dpm++ 2s',
    'dpm++ sde karras', 'dpm++ sde',
    'dpm++ 3m sde karras', 'dpm++ 3m sde',
    # DPM variants
    'dpm2 a karras', 'dpm2 karras', 'dpm2 a', 'dpm2',
    'dpm_2_a', 'dpm_2',
    'dpm fast', 'dpm adaptive',
    # Euler variants
    'euler ancestral', 'euler a', 'euler_a', 'euler',
    # Other samplers
    'heunpp2', 'heun',
    'lms karras', 'lms',
    'ddim', 'ddpm',
    'plms', 'pndm',
    'uni_pc', 'unipc',
    'lcm',
    'deis',
    'restart',
]

# Sampler families/prefixes for "X series" matching
SAMPLER_FAMILIES = {
    'dpm++': 'DPM++ 2M Karras',  # Default recommendation for DPM++ family
    'dpm': 'DPM2 Karras',
    'euler': 'Euler a',
    'heun': 'Heun',
    'lms': 'LMS',
    'ddim': 'DDIM',
    'uni_pc': 'UniPC',
    'unipc': 'UniPC',
}

# Boolean inference keywords - words that indicate true/false for features
BOOLEAN_TRUE_KEYWORDS = [
    'must', 'required', 'recommended', 'suggested', 'always', 'enable',
    'use', 'important', 'necessary', 'essential', 'definitely',
]
BOOLEAN_FALSE_KEYWORDS = [
    'don\'t', 'dont', 'avoid', 'disable', 'skip', 'optional', 'not',
]

# Regex patterns for extracting parameters from description text
# Format: list of (pattern, priority) tuples - higher priority wins
DESCRIPTION_PATTERNS: Dict[str, str] = {
    # CFG: support "cfg 7", "cfg: 7", "cfg=7", "cfg scale: 7", "guidance: 7"
    'cfg_scale': r'(?:cfg|cfg\s*scale|guidance)\s*[:\s=]+\s*(\d+(?:\.\d+)?)',
    # Steps: support "steps 25", "steps: 25", "20-30 steps"
    'steps': r'(?:steps|sampling\s*steps)\s*[:\s=]+\s*(\d+)',
    # Sampler: handled separately via dictionary matching
    'sampler': r'(?:sampler|sampling\s*method)\s*[:\s=]+\s*([a-zA-Z0-9_+\s]+?)(?:[,\n\.\(]|$)',
    # Scheduler
    'scheduler': r'(?:scheduler|schedule)\s*[:\s=]+\s*([a-zA-Z0-9_]+)',
    # Clip skip: support "clip skip 2", "clip=2", "CLIP=2", "clipskip: 2"
    'clip_skip': r'(?:clip\s*skip|clipskip|clip)\s*[:\s=]+\s*(\d+)',
    # Strength
    'strength': r'(?:(?:lora\s*)?strength|weight)\s*[:\s=]+\s*([\d.]+)',
    # Denoise
    'denoise': r'(?:denoise|denoising)\s*[:\s=]+\s*([\d.]+)',
    # Width/Height - handled separately for resolution parsing
    'width': r'(?:width|w)\s*[:\s=]+\s*(\d+)',
    'height': r'(?:height|h)\s*[:\s=]+\s*(\d+)',
    # Seed
    'seed': r'(?:seed)\s*[:\s=]+\s*(-?\d+)',
    # Hires fix - explicit values
    'hires_fix': r'(?:hires\s*[-_]?\s*fix|highres\s*[-_]?\s*fix)\s*[:\s=]+\s*(true|false|yes|no|enabled?|disabled?)',
    # Hires scale: support "2x", "1.5x", "hires scale: 2"
    'hires_scale': r'(?:hires\s*(?:scale|upscale))\s*[:\s=]+\s*([\d.]+)',
    # Hires steps
    'hires_steps': r'(?:hires\s*steps)\s*[:\s=]+\s*(\d+)',
    # Hires denoise
    'hires_denoise': r'(?:hires\s*denoise)\s*[:\s=]+\s*([\d.]+)',
}

# Extended patterns for harder-to-match formats
EXTENDED_PATTERNS: Dict[str, List[Tuple[str, int]]] = {
    # CFG with range and "best" extraction: "CFG: 5-7 (7 is best)" → 7
    'cfg_scale': [
        (r'(?:cfg|cfg\s*scale|guidance)\s*[:\s=]+\s*\d+(?:\.\d+)?\s*[-–]\s*(\d+(?:\.\d+)?)\s*\([^)]*best', 10),  # Range with "best" at end
        (r'(?:cfg|cfg\s*scale|guidance)\s*[:\s=]+\s*(\d+(?:\.\d+)?)\s*(?:is\s*)?best', 9),  # "7 is best"
        (r'(\d+(?:\.\d+)?)\s*(?:is\s*)?best[^)]*(?:cfg|cfg\s*scale)', 8),  # "7 is best for CFG"
    ],
    # Steps with range
    'steps': [
        (r'(?:steps|sampling\s*steps)\s*[:\s=]+\s*\d+\s*[-–]\s*(\d+)', 5),  # Range, take higher
    ],
    # Clip with "CLIP=N" format (capital)
    'clip_skip': [
        (r'CLIP\s*=\s*(\d+)', 10),  # CLIP=2 format (capital)
    ],
    # Hires scale with "Nx" multiplier format
    'hires_scale': [
        (r'(?:hires|highres)[-_\s]*(?:fix)?[:\s]*(\d+(?:\.\d+)?)\s*[xX]', 10),  # "hires: 2x" or "Highres-Fix: 2x"
        (r'(\d+(?:\.\d+)?)\s*[xX]\s*(?:upscale|hires|highres)', 8),  # "2x upscale"
    ],
}

# Resolution patterns: "512x768", "512,768", "resolution: 512x768"
RESOLUTION_PATTERNS = [
    r'(?:resolution|res|size)\s*[:\s=]+\s*(\d+)\s*[x,×]\s*(\d+)',  # "resolution: 512x768"
    r'(?:suggest(?:ed)?|recommend(?:ed)?)\s*resolution\s*[:\s=]*\s*(\d+)\s*[,x×]\s*(\d+)',  # "suggested resolution: 512,768"
    r'(\d{3,4})\s*[x×]\s*(\d{3,4})',  # "512x768" standalone
]

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

def _extract_with_extended_patterns(
    text: str,
    param_key: str,
    parameters: Dict[str, Any],
    raw_matches: Dict[str, str],
) -> bool:
    """
    Try extended patterns with priority for a parameter.

    Returns True if a match was found (should skip basic pattern).
    """
    if param_key not in EXTENDED_PATTERNS:
        return False

    best_match = None
    best_priority = -1

    for pattern, priority in EXTENDED_PATTERNS[param_key]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and priority > best_priority:
            best_match = match
            best_priority = priority

    if best_match:
        raw_value = best_match.group(1).strip()
        raw_matches[param_key] = raw_value
        converted = convert_param_value(param_key, raw_value)
        if converted is not None:
            parameters[param_key] = converted
            logger.debug(f"Extracted {param_key}={converted} via extended pattern (priority={best_priority})")
            return True

    return False


def _extract_sampler_from_dictionary(
    text: str,
    parameters: Dict[str, Any],
    raw_matches: Dict[str, str],
) -> bool:
    """
    Extract sampler using dictionary matching for known sampler names.

    Handles:
    1. Exact sampler name matching ("DPM++ 2M Karras")
    2. Family/series matching ("DPM++ series" → DPM++ 2M Karras)

    Returns True if a sampler was found.
    """
    text_lower = text.lower()

    # Phase 1: Try exact sampler name matching (longest first)
    for sampler in KNOWN_SAMPLERS:  # Already sorted by specificity
        if sampler.lower() in text_lower:
            # Verify it's in a sampler context (near "sampler" word or after separator)
            sampler_pattern = rf'(?:sampler|sampling)[:\s=]*[^.]*?{re.escape(sampler)}'
            context_match = re.search(sampler_pattern, text, re.IGNORECASE)
            if context_match:
                parameters['sampler'] = sampler
                raw_matches['sampler'] = sampler
                logger.debug(f"Extracted sampler={sampler} via exact dictionary matching")
                return True

    # Phase 2: Try family/series matching ("DPM++ series" → default for that family)
    for family_prefix, default_sampler in SAMPLER_FAMILIES.items():
        # Look for patterns like "DPM++ series", "DPM++ family", "use DPM++"
        family_patterns = [
            rf'{re.escape(family_prefix)}\s*(?:series|family|samplers?)',  # "DPM++ series"
            rf'(?:sampler|sampling)[:\s=]*[^.]*?{re.escape(family_prefix)}(?:\s|,|$)',  # "sampler: DPM++"
            rf'(?:use|try|recommend)\s+{re.escape(family_prefix)}',  # "use DPM++"
        ]

        for pattern in family_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                parameters['sampler'] = default_sampler
                raw_matches['sampler'] = f"{family_prefix} (family → {default_sampler})"
                logger.debug(f"Extracted sampler={default_sampler} via family matching ({family_prefix})")
                return True

    return False


def _extract_resolution(
    text: str,
    parameters: Dict[str, Any],
    raw_matches: Dict[str, str],
) -> bool:
    """
    Extract width and height from resolution patterns.

    Returns True if resolution was found.
    """
    for pattern in RESOLUTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                width = int(match.group(1))
                height = int(match.group(2))
                # Sanity check - reasonable SD resolutions
                if 256 <= width <= 4096 and 256 <= height <= 4096:
                    parameters['width'] = width
                    parameters['height'] = height
                    raw_matches['resolution'] = f"{width}x{height}"
                    logger.debug(f"Extracted resolution={width}x{height}")
                    return True
            except (ValueError, IndexError):
                continue

    return False


def _infer_boolean_from_context(
    text: str,
    param_key: str,
    search_terms: List[str],
) -> Optional[bool]:
    """
    Infer boolean value from context keywords.

    Looks for patterns like "hires fix is A Must" → True
    or "don't use hires" → False
    """
    text_lower = text.lower()

    # Build search pattern - look for the param term near boolean keywords
    for term in search_terms:
        term_lower = term.lower()
        if term_lower not in text_lower:
            continue

        # Find position of term
        pos = text_lower.find(term_lower)
        # Get surrounding context (50 chars before and after)
        start = max(0, pos - 50)
        end = min(len(text_lower), pos + len(term_lower) + 50)
        context = text_lower[start:end]

        # Check for positive keywords in context
        for keyword in BOOLEAN_TRUE_KEYWORDS:
            if keyword in context:
                logger.debug(f"Inferred {param_key}=True from context keyword '{keyword}'")
                return True

        # Check for negative keywords
        for keyword in BOOLEAN_FALSE_KEYWORDS:
            if keyword in context:
                logger.debug(f"Inferred {param_key}=False from context keyword '{keyword}'")
                return False

    return None


def extract_from_description(description: str) -> ExtractionResult:
    """
    Extract generation parameters from Civitai model description.

    Uses multiple extraction strategies:
    1. Extended patterns with priority (for ranges, "best" values)
    2. Basic regex patterns
    3. Dictionary matching for samplers
    4. Resolution parsing (WxH formats)
    5. Boolean inference from context keywords

    Parses description text looking for common parameter patterns like:
    - "Recommended: CFG 7, Steps 25"
    - "Settings: sampler: euler, clip skip: 2"
    - "Use with: strength 0.8"
    - "CFG: 5-7 (7 is best)" → extracts 7
    - "Highres-Fix is A Must!" → hires_fix=True

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

    parameters: Dict[str, Any] = {}
    raw_matches: Dict[str, str] = {}

    # Phase 1: Try extended patterns with priority (handles ranges, "best" values)
    for param_key in EXTENDED_PATTERNS.keys():
        _extract_with_extended_patterns(clean_text, param_key, parameters, raw_matches)

    # Phase 2: Basic pattern matching for params not yet extracted
    for param_key, pattern in DESCRIPTION_PATTERNS.items():
        if param_key in parameters:
            continue  # Already extracted via extended patterns

        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            raw_value = match.group(1).strip()
            raw_matches[param_key] = raw_value

            converted = convert_param_value(param_key, raw_value)
            if converted is not None:
                parameters[param_key] = converted
                logger.debug(f"Extracted {param_key}={converted} from basic pattern")

    # Phase 3: Sampler dictionary matching (if not found via regex)
    if 'sampler' not in parameters:
        _extract_sampler_from_dictionary(clean_text, parameters, raw_matches)

    # Phase 4: Resolution parsing (if width/height not found)
    if 'width' not in parameters and 'height' not in parameters:
        _extract_resolution(clean_text, parameters, raw_matches)

    # Phase 5: Boolean inference from context (for hires_fix etc.)
    if 'hires_fix' not in parameters:
        inferred = _infer_boolean_from_context(
            clean_text,
            'hires_fix',
            ['hires', 'highres', 'hires fix', 'hires-fix', 'highres fix'],
        )
        if inferred is not None:
            parameters['hires_fix'] = inferred
            raw_matches['hires_fix'] = 'inferred:' + str(inferred)

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
