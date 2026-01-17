"""Synapse utility modules."""

from .media_detection import (
    MediaType,
    MediaInfo,
    detect_media_type,
    detect_by_extension,
    detect_by_url_pattern,
    detect_by_content_type,
    is_video_url,
    is_likely_animated,
    get_video_thumbnail_url,
)

__all__ = [
    'MediaType',
    'MediaInfo',
    'detect_media_type',
    'detect_by_extension',
    'detect_by_url_pattern',
    'detect_by_content_type',
    'is_video_url',
    'is_likely_animated',
    'get_video_thumbnail_url',
]
