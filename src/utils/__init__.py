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

__all__ = [
    # Enums & Classes
    'MediaType',
    'MediaInfo',
    
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
]
