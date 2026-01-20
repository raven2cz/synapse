"""
Media Detection Utilities

Provides functions for detecting media types and transforming URLs
for optimal video/image handling with Civitai and other providers.

Key Features:
- URL-based media type detection (no network requests needed)
- Civitai video URL optimization for quality control
- Static thumbnail extraction from video URLs
- Content-Type based detection for edge cases

Author: Synapse Team
License: MIT
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums & Data Classes
# =============================================================================

class MediaType(Enum):
    """Enumeration of supported media types."""
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


@dataclass
class MediaInfo:
    """
    Result of media type detection.
    
    Attributes:
        type: Detected media type
        extension: File extension (without dot)
        is_animated: Whether content is animated (GIF, video)
        source: How the type was determined ('extension', 'pattern', 'content-type')
    """
    type: MediaType
    extension: Optional[str] = None
    is_animated: bool = False
    source: str = "extension"


# =============================================================================
# Constants
# =============================================================================

# Known video extensions
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v', '.ogv'}

# Known image extensions  
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.avif'}

# Animated image extensions
ANIMATED_EXTENSIONS = {'.gif', '.webp', '.apng'}

# URL patterns that indicate video content
VIDEO_URL_PATTERNS = [
    r'/videos?/',           # Path contains /video/ or /videos/
    r'\.mp4',               # Has .mp4 anywhere
    r'\.webm',              # Has .webm anywhere
    r'transcode=true',      # Civitai video transcoding
    r'type=video',          # Explicit video type
]

# Civitai CDN domain patterns
CIVITAI_DOMAINS = [
    'image.civitai.com',
    'images.civitai.com',
    'cdn.civitai.com',
]


# =============================================================================
# Detection Functions
# =============================================================================

def detect_media_type(
    url: str,
    use_head_request: bool = False,
    content_type: Optional[str] = None,
) -> MediaInfo:
    """
    Detect media type from URL without making network requests.
    
    Uses multiple detection strategies in order:
    1. Explicit content-type if provided
    2. URL extension analysis
    3. URL pattern matching (for Civitai quirks)
    4. Default to image for ambiguous cases
    
    Civitai Quirks Handled:
    - Videos sometimes served with .jpeg extension
    - Animated content detection via URL patterns
    - CDN URL structure analysis
    
    Args:
        url: Media URL to analyze
        use_head_request: Whether to make HEAD request (not implemented, reserved)
        content_type: Optional Content-Type header value
        
    Returns:
        MediaInfo with detected type and metadata
        
    Example:
        >>> info = detect_media_type("https://image.civitai.com/video.mp4")
        >>> info.type
        MediaType.VIDEO
        
        >>> info = detect_media_type("https://image.civitai.com/fake.jpeg")
        >>> # Could be image OR video - Civitai serves videos as .jpeg
    """
    if not url:
        return MediaInfo(type=MediaType.UNKNOWN, source="empty")
    
    # Strategy 1: Use provided content-type
    if content_type:
        lower_ct = content_type.lower()
        if 'video/' in lower_ct:
            return MediaInfo(type=MediaType.VIDEO, source="content-type")
        if 'image/' in lower_ct:
            is_animated = 'gif' in lower_ct or 'webp' in lower_ct
            return MediaInfo(type=MediaType.IMAGE, is_animated=is_animated, source="content-type")
    
    # Parse URL
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    
    # Strategy 2: Check URL patterns (before extension for Civitai quirks)
    for pattern in VIDEO_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return MediaInfo(type=MediaType.VIDEO, source="pattern")
    
    # Strategy 3: Extension-based detection
    # Remove query string for extension check
    clean_path = path.split('?')[0]
    ext = Path(clean_path).suffix.lower()
    
    if ext in VIDEO_EXTENSIONS:
        return MediaInfo(type=MediaType.VIDEO, extension=ext[1:], source="extension")
    
    if ext in IMAGE_EXTENSIONS:
        is_animated = ext in ANIMATED_EXTENSIONS
        return MediaInfo(type=MediaType.IMAGE, extension=ext[1:], is_animated=is_animated, source="extension")
    
    # Strategy 4: Civitai-specific heuristics
    # Civitai sometimes serves videos with image extensions
    is_civitai = any(domain in parsed.netloc for domain in CIVITAI_DOMAINS)
    
    if is_civitai:
        # Check for animation indicators in query params
        if 'anim=' in query or 'transcode=' in query:
            # If anim=false, it's requesting static image
            if 'anim=false' in query:
                return MediaInfo(type=MediaType.IMAGE, source="civitai-anim-false")
            # transcode=true indicates video processing
            if 'transcode=true' in query:
                return MediaInfo(type=MediaType.VIDEO, source="civitai-transcode")
    
    # Default: assume image for web content
    return MediaInfo(type=MediaType.IMAGE, source="default")


def is_video_url(url: str) -> bool:
    """
    Quick check if URL is likely a video.
    
    Convenience function wrapping detect_media_type.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL appears to be video content
    """
    info = detect_media_type(url)
    return info.type == MediaType.VIDEO


def is_image_url(url: str) -> bool:
    """
    Quick check if URL is likely an image.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL appears to be image content
    """
    info = detect_media_type(url)
    return info.type == MediaType.IMAGE


# =============================================================================
# URL Transformation Functions
# =============================================================================

def get_optimized_video_url(
    url: str,
    width: int = 1080,
    format: str = 'mp4',
) -> str:
    """
    Transform video URL for optimal playback quality.
    
    For Civitai URLs, adds transcoding parameters for consistent
    MP4 output at specified quality. Non-Civitai URLs returned unchanged.
    
    Quality Levels:
    - 450: Low quality, fast loading (mobile/preview)
    - 720: HD quality (default for hover preview)
    - 1080: Full HD quality (fullscreen viewing)
    
    Args:
        url: Original video URL
        width: Target width in pixels (450, 720, 1080)
        format: Output format (currently only 'mp4' supported)
        
    Returns:
        Optimized URL with quality parameters
        
    Example:
        >>> get_optimized_video_url("https://image.civitai.com/video.mp4", 720)
        'https://image.civitai.com/video.mp4?transcode=true&width=720'
    """
    if not url:
        return url
    
    # Parse URL
    parsed = urlparse(url)
    
    # Check if Civitai URL
    is_civitai = any(domain in parsed.netloc for domain in CIVITAI_DOMAINS)
    
    if not is_civitai:
        # Return non-Civitai URLs unchanged
        return url
    
    # Parse existing query params
    params = parse_qs(parsed.query)
    
    # Add/update transcoding parameters
    params['transcode'] = ['true']
    params['width'] = [str(width)]
    
    # Rebuild URL
    new_query = urlencode(params, doseq=True)
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return new_url


def get_video_thumbnail_url(
    url: str,
    width: int = 450,
) -> str:
    """
    Get static thumbnail URL from video URL.

    For Civitai URLs, modifies PATH parameters (not query params) to request
    a static image frame instead of animated/video content.

    Civitai URL format uses path-based parameters:
    https://image.civitai.com/.../UUID/anim=true,transcode=true,width=450/filename.jpeg

    Args:
        url: Video URL
        width: Thumbnail width (optional scaling)

    Returns:
        URL for static thumbnail image

    Example:
        >>> get_video_thumbnail_url("https://image.civitai.com/.../UUID/transcode=true/video.jpeg")
        'https://image.civitai.com/.../UUID/anim=false,transcode=true,width=450,optimized=true/video.jpeg'
    """
    if not url:
        return url

    # Parse URL
    parsed = urlparse(url)

    # Check if Civitai URL
    is_civitai = any(domain in parsed.netloc for domain in CIVITAI_DOMAINS)

    if not is_civitai:
        # Non-Civitai: try to find thumbnail by convention
        # Common pattern: video.mp4 -> video.jpg
        path = parsed.path
        for vid_ext in VIDEO_EXTENSIONS:
            if path.lower().endswith(vid_ext):
                # Try common thumbnail extensions
                return url.replace(vid_ext, '.jpg')
        return url

    # Civitai: modify PATH-based parameters (not query params!)
    # URL format: /xG1nkqKTMzGDvpLrqFT7WA/UUID/params/filename.jpeg
    path_parts = parsed.path.split('/')

    # Find path segment containing params (contains '=' like 'anim=true,transcode=true')
    param_idx = -1
    for i, part in enumerate(path_parts):
        if '=' in part or part.startswith('width'):
            param_idx = i
            break

    # Build new params string for static thumbnail
    new_params = f"anim=false,transcode=true,width={width},optimized=true"

    if param_idx >= 0:
        # Replace existing params
        path_parts[param_idx] = new_params
    elif len(path_parts) >= 3:
        # Insert params before filename
        path_parts.insert(-1, new_params)

    new_path = '/'.join(path_parts)

    # For Civitai, all params are in path - clear query string
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        new_path,
        '',  # No URL params
        '',  # Clear query string - Civitai uses path-based params
        ''   # No fragment
    ))

    return new_url


def get_civitai_static_url(url: str) -> str:
    """
    Alias for get_video_thumbnail_url with Civitai focus.

    Modifies Civitai URL path to ensure static content (anim=false).
    Useful for preventing auto-play of animated content.

    Args:
        url: Any Civitai media URL

    Returns:
        URL with anim=false in path parameters
    """
    # Delegate to the main function which handles path-based params correctly
    return get_video_thumbnail_url(url, width=450)


def get_civitai_video_url(url: str, quality: int = 1080) -> str:
    """
    Alias for get_optimized_video_url with Civitai focus.
    
    Args:
        url: Civitai media URL
        quality: Video width (450, 720, 1080)
        
    Returns:
        URL with transcode=true and width parameters
    """
    return get_optimized_video_url(url, width=quality)


# =============================================================================
# Utility Functions
# =============================================================================

def extract_extension(url: str) -> Optional[str]:
    """
    Extract file extension from URL.
    
    Args:
        url: URL to parse
        
    Returns:
        Extension without dot (e.g., 'mp4') or None
    """
    if not url:
        return None
    
    # Remove query string
    clean = url.split('?')[0]
    
    # Get suffix
    ext = Path(clean).suffix.lower()
    
    return ext[1:] if ext else None


def normalize_video_extension(url: str) -> str:
    """
    Ensure URL ends with proper video extension.
    
    Civitai sometimes serves videos as .jpeg - this fixes the extension
    for local storage.
    
    Args:
        url: Original URL
        
    Returns:
        URL with .mp4 extension (for Civitai) or unchanged
    """
    if not url:
        return url
    
    # Only process Civitai URLs
    if 'civitai.com' not in url:
        return url
    
    # Check if already has video extension
    for ext in VIDEO_EXTENSIONS:
        if url.lower().endswith(ext) or f"{ext}?" in url.lower():
            return url
    
    # Check if this is actually a video (by pattern)
    info = detect_media_type(url)
    if info.type != MediaType.VIDEO:
        return url
    
    # Replace extension
    for img_ext in ['.jpeg', '.jpg', '.png', '.webp']:
        if url.lower().endswith(img_ext):
            return url[:-len(img_ext)] + '.mp4'
        if f"{img_ext}?" in url.lower():
            return url.replace(img_ext, '.mp4')
    
    return url


# =============================================================================
# Testing Helpers
# =============================================================================

def _test_detection():
    """Run basic detection tests (for development)."""
    test_cases = [
        # Standard extensions
        ("https://example.com/image.jpg", MediaType.IMAGE),
        ("https://example.com/video.mp4", MediaType.VIDEO),
        ("https://example.com/animation.gif", MediaType.IMAGE),  # GIF is image
        
        # Civitai URLs
        ("https://image.civitai.com/preview.jpeg", MediaType.IMAGE),
        ("https://image.civitai.com/preview.mp4", MediaType.VIDEO),
        ("https://image.civitai.com/preview.jpeg?transcode=true", MediaType.VIDEO),
        ("https://image.civitai.com/preview.mp4?anim=false", MediaType.IMAGE),
        
        # Edge cases
        ("", MediaType.UNKNOWN),
        ("https://example.com/noextension", MediaType.IMAGE),  # Default
    ]
    
    for url, expected in test_cases:
        result = detect_media_type(url)
        status = "✓" if result.type == expected else "✗"
        print(f"{status} {url[:50]:50} -> {result.type.value} (expected {expected.value})")


if __name__ == "__main__":
    _test_detection()
