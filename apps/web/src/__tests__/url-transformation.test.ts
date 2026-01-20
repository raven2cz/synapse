/**
 * Tests for Civitai URL Transformation
 *
 * These tests verify that URL transformation functions:
 * - Preserve the original URL structure
 * - Don't truncate UUIDs or paths
 * - Correctly add/modify parameters
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// URL Transformation Functions (copied from MediaPreview.tsx for testing)
// ============================================================================

/**
 * Transform Civitai URL to get static thumbnail (first frame).
 * Uses anim=false parameter which returns actual JPEG/WebP.
 */
function getCivitaiThumbnailUrl(url: string, width: number = 450): string {
  if (!url || !url.includes('civitai.com')) {
    return url
  }

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
 * Transform Civitai URL to get optimized video (MP4).
 * Uses transcode=true parameter and .mp4 extension.
 */
function getCivitaiVideoUrl(url: string, width: number = 450): string {
  if (!url || !url.includes('civitai.com')) {
    return url
  }

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

    // Ensure .mp4 extension on filename
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

// ============================================================================
// URL Integrity Tests
// ============================================================================

describe('Civitai URL Transformation', () => {
  // Test URLs with realistic Civitai patterns
  const FULL_URL_WITH_PARAMS = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/width=450/image.jpeg'
  const FULL_URL_NO_PARAMS = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/image.jpeg'
  const VIDEO_URL = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/9bf9d1f8-3a8b-5d5e-9f8a-234567890abc/anim=true,transcode=true/video.jpeg'

  describe('getCivitaiThumbnailUrl', () => {
    it('should preserve full URL structure with existing params', () => {
      const result = getCivitaiThumbnailUrl(FULL_URL_WITH_PARAMS)

      // URL should still contain the full UUID
      expect(result).toContain('8af8c0e7-2f7a-4c4d-8e7f-1234567890ab')

      // Should have anim=false parameter
      expect(result).toContain('anim=false')

      // Should not truncate the URL
      expect(result.length).toBeGreaterThan(80)
    })

    it('should preserve full URL structure without existing params', () => {
      const result = getCivitaiThumbnailUrl(FULL_URL_NO_PARAMS)

      // URL should still contain the full UUID
      expect(result).toContain('8af8c0e7-2f7a-4c4d-8e7f-1234567890ab')

      // Should have anim=false parameter
      expect(result).toContain('anim=false')
    })

    it('should return empty string for empty input', () => {
      expect(getCivitaiThumbnailUrl('')).toBe('')
    })

    it('should return non-Civitai URLs unchanged', () => {
      const otherUrl = 'https://example.com/image.jpg'
      expect(getCivitaiThumbnailUrl(otherUrl)).toBe(otherUrl)
    })
  })

  describe('getCivitaiVideoUrl', () => {
    it('should preserve full URL structure', () => {
      const result = getCivitaiVideoUrl(VIDEO_URL)

      // URL should still contain the full UUID
      expect(result).toContain('9bf9d1f8-3a8b-5d5e-9f8a-234567890abc')

      // Should have transcode=true parameter
      expect(result).toContain('transcode=true')

      // Should end with .mp4
      expect(result).toMatch(/\.mp4$/)
    })

    it('should add params to URL without existing params', () => {
      const result = getCivitaiVideoUrl(FULL_URL_NO_PARAMS)

      // Should contain transcode param
      expect(result).toContain('transcode=true')

      // Should preserve UUID
      expect(result).toContain('8af8c0e7-2f7a-4c4d-8e7f-1234567890ab')
    })
  })

  describe('URL Truncation Prevention', () => {
    it('should NOT truncate UUID to single character', () => {
      const inputUrl = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/image.jpeg'

      const thumbnailResult = getCivitaiThumbnailUrl(inputUrl)
      const videoResult = getCivitaiVideoUrl(inputUrl)

      // Neither result should match the truncated pattern
      expect(thumbnailResult).not.toMatch(/xG1nkqKTMzGDvpLrqFT7WA\/8[^a-f0-9-]/)
      expect(videoResult).not.toMatch(/xG1nkqKTMzGDvpLrqFT7WA\/8[^a-f0-9-]/)

      // Both should contain the full UUID
      expect(thumbnailResult).toContain('8af8c0e7-2f7a-4c4d-8e7f-1234567890ab')
      expect(videoResult).toContain('8af8c0e7-2f7a-4c4d-8e7f-1234567890ab')
    })

    it('should handle URLs with various UUID formats', () => {
      const testUrls = [
        'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/00000000-0000-0000-0000-000000000000/image.jpeg',
        'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/image.jpeg',
        'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/12345678-1234-1234-1234-123456789012/image.jpeg',
      ]

      testUrls.forEach(url => {
        const result = getCivitaiThumbnailUrl(url)
        // Extract UUID from original
        const uuidMatch = url.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i)
        if (uuidMatch) {
          expect(result).toContain(uuidMatch[1])
        }
      })
    })
  })

  describe('Edge Cases', () => {
    it('should handle malformed URLs gracefully', () => {
      const malformedUrl = 'not-a-url-civitai.com'
      // Should not throw
      expect(() => getCivitaiThumbnailUrl(malformedUrl)).not.toThrow()
    })

    it('should handle URLs with query parameters', () => {
      const urlWithQuery = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/uuid/image.jpeg?existing=param'
      const result = getCivitaiThumbnailUrl(urlWithQuery)

      // Should still work
      expect(result).toContain('anim=false')
    })

    it('should handle short paths', () => {
      const shortUrl = 'https://image.civitai.com/short'
      const result = getCivitaiThumbnailUrl(shortUrl)

      // Should not crash, might return original or modified
      expect(typeof result).toBe('string')
    })
  })
})

// ============================================================================
// Regression Tests for Bug: Truncated URLs
// ============================================================================

describe('Regression: Truncated URL Bug', () => {
  /**
   * Bug: URLs were being displayed as truncated, e.g.:
   * https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8
   *
   * Instead of full:
   * https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/width=450/image.jpeg
   */

  it('should never produce URLs shorter than input for valid Civitai URLs', () => {
    const validUrl = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/image.jpeg'

    const thumbnailResult = getCivitaiThumbnailUrl(validUrl)
    const videoResult = getCivitaiVideoUrl(validUrl)

    // Transformed URLs should be longer (adding params) not shorter
    expect(thumbnailResult.length).toBeGreaterThanOrEqual(validUrl.length)
    expect(videoResult.length).toBeGreaterThanOrEqual(validUrl.length)
  })

  it('should preserve all path segments', () => {
    const url = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/image.jpeg'

    const result = getCivitaiThumbnailUrl(url)

    // Count path segments - should have same or more
    const originalSegments = url.split('/').length
    const resultSegments = result.split('/').length

    expect(resultSegments).toBeGreaterThanOrEqual(originalSegments)
  })
})
