/**
 * Media Detection Utility
 *
 * Client-side detection of media types (video vs image).
 * Mirrors the backend detection logic for consistency.
 */

import {
  VIDEO_EXTENSIONS,
  IMAGE_EXTENSIONS,
} from './constants'

/** Media type enum */
export type MediaType = 'image' | 'video' | 'unknown'

/** Information about detected media */
export interface MediaInfo {
  type: MediaType
  mimeType?: string
  duration?: number
  hasAudio?: boolean
  width?: number
  height?: number
  thumbnailUrl?: string
  detectionMethod?: string
}

/** Video URL patterns (regex) */
const VIDEO_URL_PATTERNS = [
  /civitai\.com.*video/i,
  /civitai\.com.*\.mp4/i,
  /civitai\.com.*\.webm/i,
  /\.mp4(\?|$)/i,
  /\.webm(\?|$)/i,
  /\.mov(\?|$)/i,
]

/**
 * Extract file extension from URL, ignoring query params.
 *
 * @param url - The URL to parse
 * @returns Lowercase extension with dot (e.g., '.mp4') or null
 */
export function getUrlExtension(url: string): string | null {
  if (!url) return null

  try {
    const urlObj = new URL(url)
    const path = urlObj.pathname

    if (path.includes('.')) {
      const ext = '.' + path.split('.').pop()?.toLowerCase()
      // Sanity check - extensions shouldn't be too long
      if (ext && ext.length <= 6) {
        return ext
      }
    }
  } catch {
    // Invalid URL, try simple parsing
    const cleanUrl = url.split('?')[0]
    if (cleanUrl.includes('.')) {
      const ext = '.' + cleanUrl.split('.').pop()?.toLowerCase()
      if (ext && ext.length <= 6) {
        return ext
      }
    }
  }

  return null
}

/**
 * Detect media type by URL file extension.
 *
 * @param url - The URL to check
 * @returns MediaType
 */
export function detectByExtension(url: string): MediaType {
  const ext = getUrlExtension(url)

  if (ext && VIDEO_EXTENSIONS.has(ext)) {
    return 'video'
  } else if (ext && IMAGE_EXTENSIONS.has(ext)) {
    return 'image'
  }

  return 'unknown'
}

/**
 * Detect media type by known URL patterns.
 *
 * @param url - The URL to check
 * @returns MediaType (video or unknown, never image)
 */
export function detectByUrlPattern(url: string): MediaType {
  if (!url) return 'unknown'

  for (const pattern of VIDEO_URL_PATTERNS) {
    if (pattern.test(url)) {
      return 'video'
    }
  }

  return 'unknown'
}

/**
 * Detect media type from API response data.
 *
 * Uses the 'type' field if provided by backend.
 *
 * @param data - API response with optional type field
 * @returns MediaType
 */
export function detectFromApiResponse(data: {
  type?: string
  url?: string
}): MediaType {
  // If backend already detected type, use it
  if (data.type === 'video' || data.type === 'image') {
    return data.type
  }

  // Otherwise detect from URL
  if (data.url) {
    return detectMediaType(data.url).type
  }

  return 'unknown'
}

/**
 * Main detection function - detects media type from URL.
 *
 * Uses multi-layer detection:
 * 1. Extension check (fast)
 * 2. URL pattern check (fast)
 * 3. Returns unknown for frontend to handle
 *
 * Note: Unlike backend, we don't do HEAD requests from frontend
 * to avoid CORS issues. Backend should detect and include type in API response.
 *
 * @param url - The URL to check
 * @returns MediaInfo with detected type
 */
export function detectMediaType(url: string): MediaInfo {
  if (!url) {
    return { type: 'unknown', detectionMethod: 'no_url' }
  }

  // Strategy 1: Extension check
  const extType = detectByExtension(url)
  if (extType !== 'unknown') {
    return {
      type: extType,
      detectionMethod: 'extension',
    }
  }

  // Strategy 2: URL pattern check
  const patternType = detectByUrlPattern(url)
  if (patternType !== 'unknown') {
    return {
      type: patternType,
      detectionMethod: 'url_pattern',
    }
  }

  // Fallback: unknown (frontend will try to load and handle errors)
  return {
    type: 'unknown',
    detectionMethod: 'fallback',
  }
}

/**
 * Quick check if URL is likely a video.
 *
 * @param url - The URL to check
 * @returns True if URL appears to be a video
 */
export function isVideoUrl(url: string): boolean {
  return detectMediaType(url).type === 'video'
}

/**
 * Check if URL might be an animated image (GIF, WebP).
 *
 * @param url - The URL to check
 * @returns True if URL might be animated
 */
export function isLikelyAnimated(url: string): boolean {
  const ext = getUrlExtension(url)
  return ext === '.gif' || ext === '.webp'
}

/**
 * Try to derive a thumbnail URL from a video URL.
 *
 * @param videoUrl - The video URL
 * @returns Thumbnail URL if derivable, null otherwise
 */
export function getVideoThumbnailUrl(videoUrl: string): string | null {
  if (!videoUrl) return null

  // Civitai: Try common patterns
  if (videoUrl.includes('civitai.com')) {
    if (videoUrl.includes('/video/')) {
      return videoUrl.replace('/video/', '/image/')
    }
    // Some Civitai URLs support ?thumbnail=true
    const separator = videoUrl.includes('?') ? '&' : '?'
    return `${videoUrl}${separator}thumbnail=true`
  }

  return null
}

/**
 * Check if browser can play a specific video format.
 *
 * @param mimeType - The MIME type to check
 * @returns True if browser supports this format
 */
export function canPlayVideoType(mimeType: string): boolean {
  if (typeof document === 'undefined') return false

  const video = document.createElement('video')
  return video.canPlayType(mimeType) !== ''
}

/**
 * Get the best supported video format for a URL.
 * Useful when multiple formats are available.
 *
 * @param urls - Object mapping format to URL
 * @returns Best URL or null
 */
export function getBestVideoUrl(urls: {
  mp4?: string
  webm?: string
  ogg?: string
}): string | null {
  // Prefer WebM (better compression) if supported
  if (urls.webm && canPlayVideoType('video/webm')) {
    return urls.webm
  }

  // Fall back to MP4 (most compatible)
  if (urls.mp4 && canPlayVideoType('video/mp4')) {
    return urls.mp4
  }

  // Last resort: OGG
  if (urls.ogg && canPlayVideoType('video/ogg')) {
    return urls.ogg
  }

  return null
}

/**
 * Probe a URL to check if it's actually a video by attempting to load it.
 * This is async and makes a network request.
 *
 * @param url - The URL to probe
 * @param timeout - Timeout in milliseconds
 * @returns Promise<MediaType>
 */
export async function probeMediaType(
  url: string,
  timeout = 5000
): Promise<MediaType> {
  return new Promise((resolve) => {
    // Try as video first
    const video = document.createElement('video')
    video.preload = 'metadata'

    const timer = setTimeout(() => {
      cleanup()
      resolve('unknown')
    }, timeout)

    const cleanup = () => {
      clearTimeout(timer)
      video.removeEventListener('loadedmetadata', onVideoLoad)
      video.removeEventListener('error', onVideoError)
      video.src = ''
    }

    const onVideoLoad = () => {
      cleanup()
      resolve('video')
    }

    const onVideoError = () => {
      cleanup()
      // Video failed, probably an image
      resolve('image')
    }

    video.addEventListener('loadedmetadata', onVideoLoad)
    video.addEventListener('error', onVideoError)
    video.src = url
  })
}
