"""
URL construction helpers — Python port of civitaiTransformers.ts logic.

These functions build the SAME URLs that the frontend builds,
allowing cross-language verification.

CRITICAL: None of these include `optimized=true`.
"""

from urllib.parse import quote, urlparse

CDN_BASE = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA"


def build_image_url(uuid: str, filename: str, width: int = 450) -> str:
    """Build a Civitai CDN image URL from UUID and filename."""
    return f"{CDN_BASE}/{uuid}/width={width}/{filename}"


def build_video_url(uuid: str, filename: str, width: int = 450) -> str:
    """Build a Civitai CDN video URL from UUID and filename.

    CRITICAL: Must include anim=true for Cloudflare to serve video directly.
    Without anim=true, CDN redirects to B2 storage which returns 401.
    Discovery: Civitai's own useEdgeUrl() defaults anim=true for video type.
    """
    # Ensure .mp4 extension
    name = filename
    if not name.lower().endswith(".mp4"):
        dot_idx = name.rfind(".")
        if dot_idx >= 0:
            name = name[:dot_idx] + ".mp4"
        else:
            name = name + ".mp4"
    return f"{CDN_BASE}/{uuid}/anim=true,transcode=true,width={width}/{name}"


def build_thumbnail_url(uuid: str, filename: str, width: int = 450) -> str:
    """Build a Civitai CDN thumbnail URL (anim=false for static frame)."""
    return f"{CDN_BASE}/{uuid}/anim=false,transcode=true,width={width}/{filename}"


def to_proxy_url(url: str, base: str = "/api/browse/image-proxy") -> str:
    """Convert a Civitai CDN URL to use the image proxy."""
    if not url:
        return url

    # Already proxied — don't double-wrap
    if "/api/browse/image-proxy" in url:
        return url

    # Only proxy Civitai CDN URLs
    civitai_domains = ("image.civitai.com", "images.civitai.com", "cdn.civitai.com")
    parsed = urlparse(url)
    if parsed.netloc not in civitai_domains:
        return url

    return f"{base}?url={quote(url, safe='')}"


def is_civitai_cdn_url(url: str) -> bool:
    """Check if URL is a Civitai CDN URL."""
    civitai_domains = ("image.civitai.com", "images.civitai.com", "cdn.civitai.com")
    parsed = urlparse(url)
    return parsed.netloc in civitai_domains


def detect_media_type(url: str) -> str:
    """
    Detect media type from URL.
    Must match both frontend (civitaiTransformers.ts) and backend (media_detection.py).
    Returns 'video', 'image', or 'unknown'.
    """
    if not url:
        return "unknown"

    lower = url.lower()

    # Extension check
    import re
    if re.search(r"\.(mp4|webm|mov|avi|mkv)(\?|$)", lower):
        return "video"

    # Civitai transcode=true without anim=false → video
    if "transcode=true" in lower and "anim=false" not in lower:
        return "video"

    # Path pattern
    if "/videos/" in lower:
        return "video"

    # type=video query param
    if "type=video" in lower:
        return "video"

    return "image"
