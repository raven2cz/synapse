"""
Media Detection Utility

Detects whether a URL points to an image or video file.
Handles Civitai's quirk of serving videos with .jpeg extensions.

Detection strategy (in order):
1. URL extension check (.mp4, .webm, .gif, .mov)
2. URL pattern check (known video CDN patterns)
3. Content-Type header check (HEAD request)
4. Fallback to 'unknown' for frontend to handle
"""

import re
import logging
from typing import Optional, Tuple, Literal
from urllib.parse import urlparse, parse_qs
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
    Detect media type by URL file extension.
    
    Args:
        url: The URL to check
        
    Returns:
        MediaType.VIDEO, MediaType.IMAGE, or MediaType.UNKNOWN
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
        MediaType.VIDEO or MediaType.UNKNOWN (never IMAGE)
    """
    if not url:
        return MediaType.UNKNOWN
    
    for regex in _VIDEO_URL_REGEXES:
        if regex.search(url):
            return MediaType.VIDEO
    
    return MediaType.UNKNOWN


def detect_by_content_type(
    url: str, 
    timeout: float = 5.0,
    api_key: Optional[str] = None,
) -> Tuple[MediaType, Optional[str]]:
    """
    Detect media type by making a HEAD request to check Content-Type.
    
    This is the most reliable method but requires a network request.
    
    Args:
        url: The URL to check
        timeout: Request timeout in seconds
        api_key: Optional API key for authenticated requests (Civitai)
        
    Returns:
        Tuple of (MediaType, mime_type_string or None)
    """
    if not HAS_REQUESTS:
        logger.warning("requests library not available, cannot check Content-Type")
        return MediaType.UNKNOWN, None
    
    if not url:
        return MediaType.UNKNOWN, None
    
    try:
        headers = {
            'User-Agent': 'Synapse/2.2 (Media Detection)',
        }
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        response = requests.head(
            url, 
            timeout=timeout, 
            allow_redirects=True,
            headers=headers,
        )
        
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Extract MIME type (ignore charset etc.)
        mime_type = content_type.split(';')[0].strip()
        
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
                # We can't know if it's animated without downloading
                # Return as unknown so frontend can handle it
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
        # Even if type is unknown, if we got mime_type, we might want to return it? 
        # But let's fall through to other methods if HEAD was inconclusive (e.g. timeout or unknown mime)

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


def get_video_thumbnail_url(video_url: str) -> Optional[str]:
    """
    Try to derive a thumbnail URL from a video URL.
    
    Some CDNs provide thumbnail URLs in predictable formats.
    
    Args:
        video_url: The video URL
        
    Returns:
        Thumbnail URL if derivable, None otherwise
    """
    if not video_url:
        return None
    
    # Civitai: Replace /video/ with /image/ or append thumbnail param
    if 'civitai.com' in video_url:
        # Try common patterns
        if '/video/' in video_url:
            return video_url.replace('/video/', '/image/')
        # Some Civitai URLs support ?thumbnail=true
        if '?' in video_url:
            return video_url + '&thumbnail=true'
        return video_url + '?thumbnail=true'
    
    return None


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
    'get_url_extension',
    'VIDEO_EXTENSIONS',
    'IMAGE_EXTENSIONS',
    'VIDEO_MIME_TYPES',
    'IMAGE_MIME_TYPES',
]
