"""
Known stable Civitai CDN URLs for smoke testing.

These UUIDs come from real Civitai models and are used to test
CDN behavior without depending on search/API endpoints.
"""

# Civitai CDN base URL
CDN_BASE = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA"

# ============================================================================
# Juggernaut XL - Model ID 133005
# This is our primary golden path model
# ============================================================================

JUGGERNAUT_MODEL_ID = 133005

# Video preview from the tRPC fixtures (model in trpc-real-models.json)
# This is the video that keeps failing due to CDN redirect issues
JUGGERNAUT_VIDEO_UUID = "1dbfbc3e-ffaf-49aa-83e1-38222a6d9a73"
JUGGERNAUT_VIDEO_FILENAME = "d8037506-b0f1-4a1c-a195-1565330741ca.mp4"

# ============================================================================
# Realistic Vision V6.0 B1 - Model ID 4201
# First model in the tRPC fixtures
# ============================================================================

REALISTIC_VISION_MODEL_ID = 4201
REALISTIC_VISION_IMAGE_UUID = "41ce091f-1006-491f-916d-873a9c80dfde"
REALISTIC_VISION_IMAGE_FILENAME = "Kh1OFnRbDUM.jpg"

# ============================================================================
# Constructed URLs for testing
# ============================================================================

# Image URL (standard)
KNOWN_IMAGE_URL = (
    f"{CDN_BASE}/{REALISTIC_VISION_IMAGE_UUID}"
    f"/width=450/{REALISTIC_VISION_IMAGE_FILENAME}"
)

# Video URL WITHOUT anim=true (will redirect to B2 → 401)
# This is the BROKEN pattern — kept for testing redirect behavior
KNOWN_VIDEO_URL = (
    f"{CDN_BASE}/{JUGGERNAUT_VIDEO_UUID}"
    f"/transcode=true,width=450/{JUGGERNAUT_VIDEO_FILENAME}"
)

# Video URL WITH anim=true (serves directly from Cloudflare → 200)
# This is the CORRECT pattern — discovered from Civitai's own useEdgeUrl()
KNOWN_VIDEO_ANIM_URL = (
    f"{CDN_BASE}/{JUGGERNAUT_VIDEO_UUID}"
    f"/anim=true,transcode=true,width=450/{JUGGERNAUT_VIDEO_FILENAME}"
)

# Video thumbnail (anim=false → 200 direct)
KNOWN_THUMBNAIL_URL = (
    f"{CDN_BASE}/{JUGGERNAUT_VIDEO_UUID}"
    f"/anim=false,transcode=true,width=450/{JUGGERNAUT_VIDEO_FILENAME}"
)

# BAD URL with optimized=true (should fail with 500)
KNOWN_BAD_OPTIMIZED_URL = (
    f"{CDN_BASE}/{REALISTIC_VISION_IMAGE_UUID}"
    f"/width=450,optimized=true/{REALISTIC_VISION_IMAGE_FILENAME}"
)

# GOOD URL without optimized=true (same content, should succeed)
KNOWN_GOOD_URL = (
    f"{CDN_BASE}/{REALISTIC_VISION_IMAGE_UUID}"
    f"/width=450/{REALISTIC_VISION_IMAGE_FILENAME}"
)

# ============================================================================
# Allowed proxy domains
# ============================================================================

ALLOWED_DOMAINS = [
    "image.civitai.com",
    "images.civitai.com",
    "cdn.civitai.com",
]

# ============================================================================
# Image magic bytes for content validation
# ============================================================================

MAGIC_BYTES = {
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG",
    "webp": b"RIFF",
    "gif": b"GIF8",
}
