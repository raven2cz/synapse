"""
Synapse Utils Package

Utility functions and helpers for the Synapse application.
"""

from .media_detection import (
    MediaType,
    MediaInfo,
    detect_media_type,
    is_video_url,
    is_image_url,
    get_optimized_video_url,
    get_video_thumbnail_url,
    get_civitai_static_url,
    get_civitai_video_url,
    extract_extension,
    normalize_video_extension,
    format_file_size,
)

from .parameter_extractor import (
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

__all__ = [
    # Enums & Classes
    'MediaType',
    'MediaInfo',
    'ParameterSourceType',
    'ExtractionResult',

    # Detection functions
    'detect_media_type',
    'is_video_url',
    'is_image_url',

    # URL transformation
    'get_optimized_video_url',
    'get_video_thumbnail_url',
    'get_civitai_static_url',
    'get_civitai_video_url',

    # Utilities
    'extract_extension',
    'normalize_video_extension',
    'format_file_size',

    # Parameter extraction
    'normalize_param_key',
    'convert_param_value',
    'normalize_params',
    'extract_from_description',
    'extract_from_image_meta',
    'aggregate_from_previews',
    'is_generation_param',
    'get_applicable_params',
    'PARAM_KEY_ALIASES',
]
