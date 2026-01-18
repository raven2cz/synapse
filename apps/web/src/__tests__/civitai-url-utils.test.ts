/**
 * Tests for Civitai URL Transformation Utilities
 *
 * These utilities are used in MediaPreview and FullscreenMediaViewer
 * to transform Civitai CDN URLs for optimal video/image loading.
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// URL Transformation Functions (extracted for testing)
// ============================================================================

type VideoQuality = 'sd' | 'hd' | 'fhd'

const QUALITY_WIDTHS: Record<VideoQuality, number> = {
  sd: 450,
  hd: 720,
  fhd: 1080,
}

/**
 * Transform Civitai URL to get static thumbnail (first frame).
 */
function getCivitaiThumbnailUrl(url: string, width: number = 450): string {
  if (!url || !url.includes('civitai.com')) return url

  try {
    const urlObj = new URL(url)
    const pathParts = urlObj.pathname.split('/')

    let paramsIndex = -1
    for (let i = 0; i < pathParts.length; i++) {
      if (pathParts[i].includes('=') || pathParts[i].startsWith('width')) {
        paramsIndex = i
        break
      }
    }

    const newParams = `anim=false,transcode=true,width=${width},optimized=true`

    if (paramsIndex >= 0) {
      pathParts[paramsIndex] = newParams
    } else if (pathParts.length >= 3) {
      pathParts.splice(-1, 0, newParams)
    }

    urlObj.pathname = pathParts.join('/')
    return urlObj.toString()
  } catch {
    return url
  }
}

/**
 * Transform Civitai URL to get video with specified quality.
 */
function getCivitaiVideoUrl(url: string, quality: VideoQuality = 'sd'): string {
  if (!url || !url.includes('civitai.com')) return url

  const width = QUALITY_WIDTHS[quality]

  try {
    const urlObj = new URL(url)
    const pathParts = urlObj.pathname.split('/')

    let paramsIndex = -1
    for (let i = 0; i < pathParts.length; i++) {
      if (pathParts[i].includes('=') || pathParts[i].startsWith('width')) {
        paramsIndex = i
        break
      }
    }

    const newParams = `transcode=true,width=${width},optimized=true`

    if (paramsIndex >= 0) {
      pathParts[paramsIndex] = newParams
    } else if (pathParts.length >= 3) {
      pathParts.splice(-1, 0, newParams)
    }

    // Ensure .mp4 extension
    const lastIndex = pathParts.length - 1
    if (lastIndex >= 0) {
      const filename = pathParts[lastIndex]
      const baseName = filename.replace(/\.[^.]+$/, '')
      pathParts[lastIndex] = `${baseName}.mp4`
    }

    urlObj.pathname = pathParts.join('/')
    return urlObj.toString()
  } catch {
    return url
  }
}

/**
 * Detect if URL is likely a video.
 */
function isLikelyVideo(url: string): boolean {
  if (!url) return false
  const lowerUrl = url.toLowerCase()
  if (/\.(mp4|webm|mov|avi|mkv|gif)(\?|$)/i.test(url)) return true
  if (lowerUrl.includes('civitai.com') && lowerUrl.includes('transcode=true') && !lowerUrl.includes('anim=false')) return true
  return false
}

// ============================================================================
// Tests
// ============================================================================

describe('getCivitaiThumbnailUrl', () => {
  it('should return original URL for non-Civitai URLs', () => {
    const url = 'https://example.com/image.jpg'
    expect(getCivitaiThumbnailUrl(url)).toBe(url)
  })

  it('should return original URL for empty string', () => {
    expect(getCivitaiThumbnailUrl('')).toBe('')
  })

  it('should add anim=false parameter for Civitai URLs', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=1080/image.jpeg'
    const result = getCivitaiThumbnailUrl(url)
    expect(result).toContain('anim=false')
    expect(result).toContain('transcode=true')
    expect(result).toContain('width=450')
  })

  it('should respect custom width parameter', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=1080/image.jpeg'
    const result = getCivitaiThumbnailUrl(url, 300)
    expect(result).toContain('width=300')
  })

  it('should replace existing params segment', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/transcode=true,width=1080/video.mp4'
    const result = getCivitaiThumbnailUrl(url)
    expect(result).not.toContain('width=1080')
    expect(result).toContain('width=450')
    expect(result).toContain('anim=false')
  })

  it('should handle URLs without params segment', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/image.jpeg'
    const result = getCivitaiThumbnailUrl(url)
    expect(result).toContain('anim=false')
  })
})

describe('getCivitaiVideoUrl', () => {
  it('should return original URL for non-Civitai URLs', () => {
    const url = 'https://example.com/video.mp4'
    expect(getCivitaiVideoUrl(url)).toBe(url)
  })

  it('should return original URL for empty string', () => {
    expect(getCivitaiVideoUrl('')).toBe('')
  })

  it('should use SD quality (450) by default', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=1080/video.webm'
    const result = getCivitaiVideoUrl(url, 'sd')
    expect(result).toContain('width=450')
  })

  it('should use HD quality (720) when specified', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=1080/video.webm'
    const result = getCivitaiVideoUrl(url, 'hd')
    expect(result).toContain('width=720')
  })

  it('should use FHD quality (1080) when specified', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=450/video.webm'
    const result = getCivitaiVideoUrl(url, 'fhd')
    expect(result).toContain('width=1080')
  })

  it('should ensure .mp4 extension', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=1080/video.webm'
    const result = getCivitaiVideoUrl(url)
    expect(result).toMatch(/\.mp4$/)
    expect(result).not.toContain('.webm')
  })

  it('should add transcode=true parameter', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/video.webm'
    const result = getCivitaiVideoUrl(url)
    expect(result).toContain('transcode=true')
  })

  it('should NOT include anim=false (that would make it a static image)', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/video.webm'
    const result = getCivitaiVideoUrl(url)
    expect(result).not.toContain('anim=false')
  })
})

describe('isLikelyVideo', () => {
  it('should return false for empty string', () => {
    expect(isLikelyVideo('')).toBe(false)
  })

  it('should detect .mp4 files', () => {
    expect(isLikelyVideo('https://example.com/video.mp4')).toBe(true)
  })

  it('should detect .webm files', () => {
    expect(isLikelyVideo('https://example.com/video.webm')).toBe(true)
  })

  it('should detect .mov files', () => {
    expect(isLikelyVideo('https://example.com/video.mov')).toBe(true)
  })

  it('should detect .gif files', () => {
    expect(isLikelyVideo('https://example.com/animation.gif')).toBe(true)
  })

  it('should detect Civitai transcode URLs as video', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/transcode=true,width=450/file.jpeg'
    expect(isLikelyVideo(url)).toBe(true)
  })

  it('should NOT detect Civitai anim=false URLs as video (they are thumbnails)', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/anim=false,transcode=true,width=450/file.jpeg'
    expect(isLikelyVideo(url)).toBe(false)
  })

  it('should NOT detect regular images as video', () => {
    expect(isLikelyVideo('https://example.com/image.jpg')).toBe(false)
    expect(isLikelyVideo('https://example.com/image.png')).toBe(false)
    expect(isLikelyVideo('https://example.com/image.webp')).toBe(false)
  })

  it('should handle URLs with query parameters', () => {
    expect(isLikelyVideo('https://example.com/video.mp4?token=abc')).toBe(true)
    expect(isLikelyVideo('https://example.com/image.jpg?token=abc')).toBe(false)
  })
})

describe('Quality Constants', () => {
  it('should have correct width values', () => {
    expect(QUALITY_WIDTHS.sd).toBe(450)
    expect(QUALITY_WIDTHS.hd).toBe(720)
    expect(QUALITY_WIDTHS.fhd).toBe(1080)
  })
})

describe('URL Edge Cases', () => {
  it('should handle malformed URLs gracefully', () => {
    const malformed = 'not-a-valid-url'
    expect(getCivitaiThumbnailUrl(malformed)).toBe(malformed)
    expect(getCivitaiVideoUrl(malformed)).toBe(malformed)
  })

  it('should handle URLs with special characters', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid-123/width=450/file%20with%20spaces.mp4'
    const result = getCivitaiVideoUrl(url)
    expect(result).toContain('civitai.com')
    expect(result).toContain('.mp4')
  })

  it('should preserve URL hostname and protocol', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/width=1080/video.webm'
    const result = getCivitaiVideoUrl(url)
    expect(result).toMatch(/^https:\/\/image\.civitai\.com/)
  })
})
