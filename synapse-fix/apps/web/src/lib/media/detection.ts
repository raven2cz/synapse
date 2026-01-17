/**
 * Media Type Detection
 *
 * Utilities for detecting media type (image/video) from URLs.
 * Uses multi-layer detection: extension → URL pattern → fallback.
 *
 * @author Synapse Team
 */

// ============================================================================
// Types
// ============================================================================

export type MediaType = 'image' | 'video' | 'unknown'

export interface MediaInfo {
  type: MediaType
  detectionMethod?: 'extension' | 'url_pattern' | 'mime_type' | 'fallback' | 'no_url'
}

// ============================================================================
// Constants
// ============================================================================

const VIDEO_EXTENSIONS = new Set([
  '.mp4',
  '.webm',
  '.mov',
  '.avi',
  '.mkv',
  '.m4v',
  '.gif', // Animated GIFs treated as video-like
])

const IMAGE_EXTENSIONS = new Set([
  '.jpg',
  '.jpeg',
  '.png',
  '.bmp',
  '.tiff',
  '.tif',
  '.svg',
  '.ico',
  '.heic',
  '.heif',
  '.avif',
  '.webp',
])

// Known video CDN patterns
const VIDEO_URL_PATTERNS = [
  /\/video\//i,
  /\.mp4/i,
  /\.webm/i,
  /type=video/i,
  /format=video/i,
]

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Extract file extension from URL (lowercase, with dot)
 */
function getUrlExtension(url: string): string {
  try {
    const pathname = new URL(url).pathname
    const lastDot = pathname.lastIndexOf('.')
    if (lastDot === -1 || lastDot === pathname.length - 1) return ''
    return pathname.slice(lastDot).toLowerCase().split('?')[0]
  } catch {
    // Fallback for malformed URLs
    const match = url.match(/\.([a-zA-Z0-9]+)(?:\?|$)/)
    return match ? `.${match[1].toLowerCase()}` : ''
  }
}

/**
 * Detect media type by file extension
 */
function detectByExtension(url: string): MediaType {
  const ext = getUrlExtension(url)
  if (!ext) return 'unknown'

  if (VIDEO_EXTENSIONS.has(ext)) return 'video'
  if (IMAGE_EXTENSIONS.has(ext)) return 'image'

  return 'unknown'
}

/**
 * Detect media type by URL patterns
 */
function detectByUrlPattern(url: string): MediaType {
  const urlLower = url.toLowerCase()

  for (const pattern of VIDEO_URL_PATTERNS) {
    if (pattern.test(urlLower)) {
      return 'video'
    }
  }

  // Civitai-specific: videos sometimes served as .jpeg
  if (urlLower.includes('civitai.com') && urlLower.includes('type=video')) {
    return 'video'
  }

  return 'unknown'
}

// ============================================================================
// Main Detection Function
// ============================================================================

/**
 * Detect media type from URL using multi-layer detection.
 *
 * Detection order:
 * 1. Extension check (fast, reliable for standard URLs)
 * 2. URL pattern check (handles CDN quirks)
 * 3. Fallback to 'unknown'
 *
 * @param url - The URL to analyze
 * @returns MediaInfo with detected type and method
 *
 * @example
 * const info = detectMediaType('https://example.com/video.mp4')
 * // { type: 'video', detectionMethod: 'extension' }
 */
export function detectMediaType(url: string): MediaInfo {
  if (!url) {
    return { type: 'unknown', detectionMethod: 'no_url' }
  }

  // Strategy 1: Extension check
  const extType = detectByExtension(url)
  if (extType !== 'unknown') {
    return { type: extType, detectionMethod: 'extension' }
  }

  // Strategy 2: URL pattern check
  const patternType = detectByUrlPattern(url)
  if (patternType !== 'unknown') {
    return { type: patternType, detectionMethod: 'url_pattern' }
  }

  // Fallback: assume image (most common case)
  return { type: 'image', detectionMethod: 'fallback' }
}

/**
 * Quick check if URL is likely a video.
 */
export function isVideoUrl(url: string): boolean {
  return detectMediaType(url).type === 'video'
}

/**
 * Check if URL might be animated (GIF, WebP).
 */
export function isLikelyAnimated(url: string): boolean {
  const ext = getUrlExtension(url)
  return ext === '.gif' || ext === '.webp'
}

/**
 * Try to derive thumbnail URL from video URL.
 * Works for some CDNs that support thumbnail generation.
 */
export function getVideoThumbnailUrl(videoUrl: string): string | null {
  if (!videoUrl) return null

  // Civitai: Try common patterns
  if (videoUrl.includes('civitai.com')) {
    // Replace /video/ with /image/ if present
    if (videoUrl.includes('/video/')) {
      return videoUrl.replace('/video/', '/image/')
    }
    // Add thumbnail parameter
    const separator = videoUrl.includes('?') ? '&' : '?'
    return `${videoUrl}${separator}thumbnail=true`
  }

  return null
}

/**
 * Check if browser can play a specific video format.
 */
export function canPlayVideoType(mimeType: string): boolean {
  if (typeof document === 'undefined') return false
  const video = document.createElement('video')
  return video.canPlayType(mimeType) !== ''
}

export default detectMediaType
