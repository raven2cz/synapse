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
 */
export function getUrlExtension(url: string): string | null {
  if (!url) return null

  try {
    const urlObj = new URL(url)
    const path = urlObj.pathname

    if (path.includes('.')) {
      const ext = '.' + path.split('.').pop()?.toLowerCase()
      if (ext && ext.length <= 6) {
        return ext
      }
    }
  } catch {
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
 */
export function detectFromApiResponse(data: {
  type?: string
  url?: string
}): MediaType {
  if (data.type === 'video' || data.type === 'image') {
    return data.type
  }

  if (data.url) {
    return detectMediaType(data.url).type
  }

  return 'unknown'
}

/**
 * Main detection function - detects media type from URL.
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

  // Fallback: unknown
  return {
    type: 'unknown',
    detectionMethod: 'fallback',
  }
}

/**
 * Quick check if URL is likely a video.
 */
export function isVideoUrl(url: string): boolean {
  return detectMediaType(url).type === 'video'
}

/**
 * Check if URL might be an animated image (GIF, WebP).
 */
export function isLikelyAnimated(url: string): boolean {
  const ext = getUrlExtension(url)
  return ext === '.gif' || ext === '.webp'
}

/**
 * Try to derive a thumbnail URL from a video URL.
 */
export function getVideoThumbnailUrl(videoUrl: string): string | null {
  if (!videoUrl) return null

  if (videoUrl.includes('civitai.com')) {
    if (videoUrl.includes('/video/')) {
      return videoUrl.replace('/video/', '/image/')
    }
    const separator = videoUrl.includes('?') ? '&' : '?'
    return `${videoUrl}${separator}thumbnail=true`
  }

  return null
}

/**
 * Check if browser can play a specific video format.
 */
export function canPlayVideoType(mimeType: string): boolean {
  const video = document.createElement('video')
  return video.canPlayType(mimeType) !== ''
}

/**
 * Get the best playable video URL from options.
 */
export function getBestVideoUrl(urls: { url: string; mimeType?: string }[]): string | null {
  const preferredOrder = ['video/mp4', 'video/webm', 'video/ogg']

  for (const preferred of preferredOrder) {
    const match = urls.find(u => u.mimeType === preferred && canPlayVideoType(preferred))
    if (match) return match.url
  }

  // Fallback to first URL
  return urls[0]?.url || null
}

/**
 * Probe media type via network request (async).
 * Uses HEAD request to check Content-Type.
 */
export async function probeMediaType(url: string): Promise<MediaInfo> {
  try {
    const response = await fetch(url, { method: 'HEAD' })
    const contentType = response.headers.get('content-type')

    if (contentType) {
      if (contentType.startsWith('video/')) {
        return { type: 'video', mimeType: contentType, detectionMethod: 'head_request' }
      } else if (contentType.startsWith('image/')) {
        return { type: 'image', mimeType: contentType, detectionMethod: 'head_request' }
      }
    }
  } catch {
    // Network error, fallback to extension detection
  }

  return detectMediaType(url)
}
