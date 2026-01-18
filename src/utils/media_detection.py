"""
Media Detection Utility

Detects whether a URL points to an image or video file.
Handles Civitai's quirk of serving videos with .jpeg extensions.

Detection strategy (in order):
1. URL extension check (.mp4, .webm, .gif, .mov)
2. URL pattern check (known video CDN patterns)
3. Content-Type header check (HEAD request)
4. Fallback to 'unknown' for frontend to handle

Civitai URL Transformations:
- Thumbnail (static): anim=false,transcode=true,width=450,optimized=true
- Video (animated):   transcode=true,width=450,optimized=true
"""

import re
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from enum import Enum
from dataclasses import dataclass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """Type of media content."""
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


# Video file extensions (lowercase)
VIDEO_EXTENSIONS = {
    '.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v',
    '.gif',  # Animated GIFs treated as video for playback
    '.webp',  # Can be animated
}

# Image file extensions (lowercase)
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif',
    '.svg', '.ico', '.heic', '.heif', '.avif',
}

# Video MIME types
VIDEO_MIME_TYPES = {
    'video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo',
    'video/x-matroska', 'video/ogg', 'video/mpeg',
}

# Image MIME types  
IMAGE_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/bmp', 'image/tiff',
    'image/svg+xml', 'image/x-icon', 'image/heic', 'image/heif',
    'image/avif',
}

# Known video URL patterns (regex)
VIDEO_URL_PATTERNS = [
    # Civitai video patterns
    r'civitai\.com.*video',
    r'civitai\.com.*\.mp4',
    r'civitai\.com.*\.webm',
    # Civitai transcode pattern (indicates video)
    r'civitai\.com.*transcode=true',
    # Generic video hosting
    r'\.mp4(\?|$)',
    r'\.webm(\?|$)',
    r'\.mov(\?|$)',
]

# Compiled regex patterns for performance
_VIDEO_URL_REGEXES = [re.compile(p, re.IGNORECASE) for p in VIDEO_URL_PATTERNS]


@dataclass
class MediaInfo:
    """Information about a media file."""
    type: MediaType
    mime_type: Optional[str] = None
    duration: Optional[float] = None  # seconds
    has_audio: Optional[bool] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    thumbnail_url: Optional[str] = None
    detection_method: Optional[str] = None  # How type was determined
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        return {k: v.value if isinstance(v, Enum) else v 
                for k, v in self.__dict__.items() if v is not None}


def get_url_extension(url: str) -> Optional[str]:
    """
    Extract file extension from URL, ignoring query params.
    
    Args:
        url: The URL to parse
        
    Returns:
        Lowercase extension with dot (e.g., '.mp4') or None
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url)
        path = parsed.path
        
        # Find last dot in path
        if '.' in path:
            ext = '.' + path.rsplit('.', 1)[-1].lower()
            # Sanity check - extensions shouldn't be too long
            if len(ext) <= 6:
                return ext
    except Exception:
        pass
    
    return None


def detect_by_extension(url: str) -> MediaType:
    """
    Detect media type by file extension in URL.
    
    Args:
        url: The URL to check
        
    Returns:
        MediaType enum value
    """
    ext = get_url_extension(url)
    
    if ext in VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    elif ext in IMAGE_EXTENSIONS:
        return MediaType.IMAGE
    
    return MediaType.UNKNOWN


def detect_by_url_pattern(url: str) -> MediaType:
    """
    Detect media type by known URL patterns.
    
    Args:
        url: The URL to check
        
    Returns:
        MediaType enum value (VIDEO or UNKNOWN, never IMAGE)
    """
    if not url:
        return MediaType.UNKNOWN
    
    for pattern in _VIDEO_URL_REGEXES:
        if pattern.search(url):
            return MediaType.VIDEO
    
    return MediaType.UNKNOWN


def detect_by_content_type(
    url: str,
    timeout: float = 5.0,
    api_key: Optional[str] = None,
) -> Tuple[MediaType, Optional[str]]:
    """
    Detect media type via HEAD request Content-Type header.
    
    Args:
        url: The URL to check
        timeout: Request timeout in seconds
        api_key: Optional API key for authenticated requests
        
    Returns:
        Tuple of (MediaType, mime_type string or None)
    """
    if not HAS_REQUESTS:
        return MediaType.UNKNOWN, None
    
    try:
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        response = requests.head(url, timeout=timeout, headers=headers, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '')
        
        if not content_type:
            return MediaType.UNKNOWN, None
        
        # Parse MIME type (ignore charset and other params)
        mime_type = content_type.split(';')[0].strip().lower()
        
        if mime_type in VIDEO_MIME_TYPES:
            return MediaType.VIDEO, mime_type
        elif mime_type in IMAGE_MIME_TYPES:
            return MediaType.IMAGE, mime_type
        
        # Check for video/* or image/* prefix
        if mime_type.startswith('video/'):
            return MediaType.VIDEO, mime_type
        elif mime_type.startswith('image/'):
            # Special case: image/gif and image/webp can be animated
            if mime_type in ('image/gif', 'image/webp'):
                return MediaType.UNKNOWN, mime_type
            return MediaType.IMAGE, mime_type
        
        return MediaType.UNKNOWN, mime_type
        
    except requests.exceptions.Timeout:
        logger.debug(f"Timeout checking Content-Type for {url}")
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error checking Content-Type for {url}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error checking Content-Type for {url}: {e}")
    
    return MediaType.UNKNOWN, None


def detect_media_type(
    url: str,
    use_head_request: bool = False,
    api_key: Optional[str] = None,
    timeout: float = 5.0,
) -> MediaInfo:
    """
    Detect the type of media at a URL.
    
    Uses a multi-layer detection strategy:
    1. Check URL extension (fast, no network)
    2. Check URL patterns (fast, no network)
    3. Optionally check Content-Type via HEAD request (accurate, slow)
    
    Args:
        url: The URL to check
        use_head_request: Whether to make HEAD request for Content-Type
        api_key: Optional API key for authenticated HEAD requests
        timeout: Timeout for HEAD request
        
    Returns:
        MediaInfo with detected type and metadata
    """
    if not url:
        return MediaInfo(type=MediaType.UNKNOWN, detection_method="no_url")
    
    # Strategy 1: HEAD request (if enabled) - Prioritize accuracy if requested
    if use_head_request:
        content_type, mime_type = detect_by_content_type(url, timeout, api_key)
        if content_type != MediaType.UNKNOWN:
            return MediaInfo(
                type=content_type,
                mime_type=mime_type,
                detection_method="content_type",
            )

    # Strategy 2: Extension check
    ext_type = detect_by_extension(url)
    if ext_type != MediaType.UNKNOWN:
        return MediaInfo(
            type=ext_type,
            detection_method="extension",
        )

    # Strategy 3: URL pattern check
    pattern_type = detect_by_url_pattern(url)
    if pattern_type != MediaType.UNKNOWN:
        return MediaInfo(
            type=pattern_type,
            detection_method="url_pattern",
        )

    # Fallback: unknown
    return MediaInfo(
        type=MediaType.UNKNOWN,
        detection_method="fallback",
    )


def is_video_url(url: str) -> bool:
    """
    Quick check if URL is likely a video.
    
    This is a fast check without network requests.
    Use detect_media_type() for more accurate detection.
    
    Args:
        url: The URL to check
        
    Returns:
        True if URL appears to be a video
    """
    info = detect_media_type(url, use_head_request=False)
    return info.type == MediaType.VIDEO


def is_likely_animated(url: str) -> bool:
    """
    Check if URL might be an animated image (GIF, WebP).
    
    Args:
        url: The URL to check
        
    Returns:
        True if URL might be animated
    """
    ext = get_url_extension(url)
    return ext in {'.gif', '.webp'}


def transform_civitai_url(url: str, params: dict) -> str:
    """
    Transform a Civitai image URL with new parameters.
    
    Civitai uses a specific URL format:
    https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/{uuid}/{params}/{filename}
    
    Args:
        url: Original Civitai URL
        params: Dict of params like {'anim': 'false', 'transcode': 'true', 'width': '450'}
        
    Returns:
        Transformed URL
    """
    if not url or 'civitai.com' not in url:
        return url
    
    try:
        # Parse URL
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        
        # Find the params segment (contains = signs like width=450)
        # Format: /{uuid}/{params}/{filename}
        for i, part in enumerate(path_parts):
            if '=' in part or part.startswith('width'):
                # Replace params segment
                param_str = ','.join(f"{k}={v}" for k, v in params.items())
                path_parts[i] = param_str
                break
        else:
            # No params found, insert before filename
            if len(path_parts) >= 2:
                param_str = ','.join(f"{k}={v}" for k, v in params.items())
                path_parts.insert(-1, param_str)
        
        new_path = '/'.join(path_parts)
        return urlunparse((parsed.scheme, parsed.netloc, new_path, '', '', ''))
        
    except Exception as e:
        logger.debug(f"Failed to transform Civitai URL {url}: {e}")
        return url


def get_video_thumbnail_url(video_url: str, width: int = 450) -> Optional[str]:
    """
    Get a static thumbnail URL from a video URL.
    
    For Civitai, uses anim=false parameter to get static frame.
    
    Args:
        video_url: The video URL
        width: Desired thumbnail width
        
    Returns:
        Thumbnail URL if derivable, None otherwise
    """
    if not video_url:
        return None
    
    # Civitai: Use anim=false to get static thumbnail
    if 'civitai.com' in video_url or 'image.civitai.com' in video_url:
        return transform_civitai_url(video_url, {
            'anim': 'false',
            'transcode': 'true', 
            'width': str(width),
            'optimized': 'true',
        })
    
    return None


def get_optimized_video_url(url: str, width: int = 450) -> str:
    """
    Get an optimized video URL with transcoding.
    
    For Civitai, uses transcode=true to get WebP/MP4 optimized version.
    
    Args:
        url: The original URL
        width: Desired video width
        
    Returns:
        Optimized video URL
    """
    if not url:
        return url
    
    # Civitai: Use transcode=true for optimized video
    if 'civitai.com' in url or 'image.civitai.com' in url:
        return transform_civitai_url(url, {
            'transcode': 'true',
            'width': str(width),
            'optimized': 'true',
        })
    
    return url


# Export commonly used items
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
    'get_optimized_video_url',
    'transform_civitai_url',
    'get_url_extension',
    'VIDEO_EXTENSIONS',
    'IMAGE_EXTENSIONS',
    'VIDEO_MIME_TYPES',
    'IMAGE_MIME_TYPES',
]
