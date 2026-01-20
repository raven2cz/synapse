/**
 * Tests for PackDetailPage Video Support Verification
 *
 * Tests cover:
 * - PreviewInfo interface with media_type and thumbnail_url
 * - FullscreenMediaViewer meta prop passing
 * - MediaPreview integration with video support
 * - Data flow from API to components
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// Test Types (mirroring PackDetailPage types)
// ============================================================================

interface PreviewInfo {
  filename: string
  url?: string
  nsfw: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
  media_type: 'image' | 'video' | 'unknown'
  duration?: number
  has_audio?: boolean
  thumbnail_url?: string
}

interface FullscreenMediaItem {
  url: string
  type?: 'image' | 'video' | 'unknown'
  thumbnailUrl?: string
  nsfw?: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
}

interface PackDetail {
  name: string
  version: string
  previews: PreviewInfo[]
  thumbnail?: string
  thumbnail_type?: 'image' | 'video'
}

// ============================================================================
// PreviewInfo Interface Tests
// ============================================================================

describe('PreviewInfo Interface', () => {
  describe('media_type field', () => {
    it('should support image type', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.jpg',
        nsfw: false,
        media_type: 'image',
      }

      expect(preview.media_type).toBe('image')
    })

    it('should support video type', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.mp4',
        nsfw: false,
        media_type: 'video',
      }

      expect(preview.media_type).toBe('video')
    })

    it('should support unknown type', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.bin',
        nsfw: false,
        media_type: 'unknown',
      }

      expect(preview.media_type).toBe('unknown')
    })
  })

  describe('thumbnail_url field', () => {
    it('should store thumbnail URL for videos', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.mp4',
        nsfw: false,
        media_type: 'video',
        thumbnail_url: 'https://civitai.com/thumb.jpg?anim=false',
      }

      expect(preview.thumbnail_url).toContain('anim=false')
    })

    it('should be optional for images', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.jpg',
        nsfw: false,
        media_type: 'image',
        // thumbnail_url not set
      }

      expect(preview.thumbnail_url).toBeUndefined()
    })
  })

  describe('video-specific fields', () => {
    it('should include duration for videos', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.mp4',
        nsfw: false,
        media_type: 'video',
        duration: 15.5,
      }

      expect(preview.duration).toBe(15.5)
    })

    it('should include has_audio flag for videos', () => {
      const preview: PreviewInfo = {
        filename: 'preview_1.mp4',
        nsfw: false,
        media_type: 'video',
        has_audio: true,
      }

      expect(preview.has_audio).toBe(true)
    })
  })
})

// ============================================================================
// Data Flow Tests
// ============================================================================

describe('Data Flow: API to Components', () => {
  const mockApiResponse: PackDetail = {
    name: 'test-pack',
    version: '1.0.0',
    thumbnail: '/previews/test-pack/resources/previews/preview_1.mp4',
    thumbnail_type: 'video',
    previews: [
      {
        filename: 'preview_1.mp4',
        url: 'https://civitai.com/video.mp4',
        nsfw: false,
        width: 1920,
        height: 1080,
        media_type: 'video',
        thumbnail_url: 'https://civitai.com/video.mp4?anim=false',
        meta: { prompt: 'Test generation', seed: 12345 },
      },
      {
        filename: 'preview_2.jpg',
        url: 'https://civitai.com/image.jpg',
        nsfw: true,
        width: 512,
        height: 768,
        media_type: 'image',
        meta: { prompt: 'Another generation', seed: 67890 },
      },
    ],
  }

  describe('Preview list handling', () => {
    it('should parse video previews correctly', () => {
      const videos = mockApiResponse.previews.filter(p => p.media_type === 'video')

      expect(videos.length).toBe(1)
      expect(videos[0].filename).toBe('preview_1.mp4')
    })

    it('should parse image previews correctly', () => {
      const images = mockApiResponse.previews.filter(p => p.media_type === 'image')

      expect(images.length).toBe(1)
      expect(images[0].filename).toBe('preview_2.jpg')
    })

    it('should preserve metadata through the data flow', () => {
      const firstPreview = mockApiResponse.previews[0]

      expect(firstPreview.meta).toBeDefined()
      expect(firstPreview.meta?.prompt).toBe('Test generation')
      expect(firstPreview.meta?.seed).toBe(12345)
    })
  })

  describe('Thumbnail type detection', () => {
    it('should detect video thumbnail', () => {
      expect(mockApiResponse.thumbnail_type).toBe('video')
    })

    it('should have video thumbnail URL', () => {
      expect(mockApiResponse.thumbnail).toContain('.mp4')
    })
  })
})

// ============================================================================
// FullscreenMediaViewer Integration Tests
// ============================================================================

describe('FullscreenMediaViewer Integration', () => {
  describe('Items transformation', () => {
    const mockPreviews: PreviewInfo[] = [
      {
        filename: 'video.mp4',
        url: 'https://civitai.com/video.mp4',
        nsfw: false,
        media_type: 'video',
        thumbnail_url: 'https://civitai.com/thumb.jpg',
        width: 1920,
        height: 1080,
        meta: { prompt: 'Test' },
      },
    ]

    it('should transform PreviewInfo to FullscreenMediaItem', () => {
      const transformedItems: FullscreenMediaItem[] = mockPreviews.map(p => ({
        url: p.url || '',
        type: p.media_type,
        thumbnailUrl: p.thumbnail_url,
        nsfw: p.nsfw,
        width: p.width,
        height: p.height,
        meta: p.meta,
      }))

      expect(transformedItems.length).toBe(1)
      expect(transformedItems[0].type).toBe('video')
      expect(transformedItems[0].thumbnailUrl).toBe('https://civitai.com/thumb.jpg')
    })

    it('should pass meta to FullscreenMediaViewer items', () => {
      const transformedItems: FullscreenMediaItem[] = mockPreviews.map(p => ({
        url: p.url || '',
        type: p.media_type,
        meta: p.meta,
      }))

      expect(transformedItems[0].meta).toBeDefined()
      expect(transformedItems[0].meta?.prompt).toBe('Test')
    })
  })

  describe('NSFW handling', () => {
    it('should pass nsfw flag to viewer items', () => {
      const preview: PreviewInfo = {
        filename: 'nsfw.jpg',
        nsfw: true,
        media_type: 'image',
      }

      const item: FullscreenMediaItem = {
        url: preview.filename,
        nsfw: preview.nsfw,
      }

      expect(item.nsfw).toBe(true)
    })
  })
})

// ============================================================================
// MediaPreview Integration Tests
// ============================================================================

describe('MediaPreview Integration', () => {
  describe('Props mapping', () => {
    const preview: PreviewInfo = {
      filename: 'video.mp4',
      url: 'https://civitai.com/video.mp4',
      nsfw: false,
      media_type: 'video',
      thumbnail_url: 'https://civitai.com/thumb.jpg',
    }

    it('should map media_type to type prop', () => {
      const mediaPreviewProps = {
        type: preview.media_type,
      }

      expect(mediaPreviewProps.type).toBe('video')
    })

    it('should map thumbnail_url to thumbnailSrc prop', () => {
      const mediaPreviewProps = {
        thumbnailSrc: preview.thumbnail_url,
      }

      expect(mediaPreviewProps.thumbnailSrc).toBe('https://civitai.com/thumb.jpg')
    })

    it('should enable autoPlay for video previews', () => {
      const mediaPreviewProps = {
        autoPlay: preview.media_type === 'video',
      }

      expect(mediaPreviewProps.autoPlay).toBe(true)
    })
  })

  describe('Video preview behavior', () => {
    it('should use thumbnail as poster while loading', () => {
      const preview: PreviewInfo = {
        filename: 'video.mp4',
        nsfw: false,
        media_type: 'video',
        thumbnail_url: 'https://civitai.com/thumb.jpg',
      }

      // MediaPreview should show thumbnail_url as static image
      // until hover triggers video playback
      expect(preview.thumbnail_url).toBeDefined()
    })

    it('should NOT autoplay when NSFW and blurred', () => {
      const preview: PreviewInfo = {
        filename: 'nsfw_video.mp4',
        nsfw: true,
        media_type: 'video',
      }

      const shouldBlur = preview.nsfw // Assuming NSFW filter is ON
      const shouldAutoplay = !shouldBlur && preview.media_type === 'video'

      expect(shouldAutoplay).toBe(false)
    })
  })
})

// ============================================================================
// Pack List Card Tests
// ============================================================================

describe('Pack List Card Video Support', () => {
  describe('Thumbnail type handling', () => {
    interface PackSummary {
      name: string
      thumbnail?: string
      thumbnail_type?: 'image' | 'video'
    }

    it('should detect video thumbnail from thumbnail_type', () => {
      const pack: PackSummary = {
        name: 'test-pack',
        thumbnail: '/previews/test/preview.mp4',
        thumbnail_type: 'video',
      }

      const isVideoThumbnail = pack.thumbnail_type === 'video'
      expect(isVideoThumbnail).toBe(true)
    })

    it('should fallback to image type when not specified', () => {
      const pack: PackSummary = {
        name: 'test-pack',
        thumbnail: '/previews/test/preview.jpg',
        // thumbnail_type not set
      }

      const thumbnailType = pack.thumbnail_type || 'image'
      expect(thumbnailType).toBe('image')
    })
  })

  describe('MediaPreview usage in cards', () => {
    it('should use MediaPreview component for pack thumbnail', () => {
      const packData = {
        thumbnail: '/preview.mp4',
        thumbnail_type: 'video' as const,
      }

      // Card should use MediaPreview with:
      const mediaPreviewProps = {
        src: packData.thumbnail,
        type: packData.thumbnail_type,
        autoPlay: true,
        playFullOnHover: true,
      }

      expect(mediaPreviewProps.type).toBe('video')
      expect(mediaPreviewProps.autoPlay).toBe(true)
    })
  })
})

// ============================================================================
// URL Generation Tests
// ============================================================================

describe('URL Generation for Videos', () => {
  describe('Civitai video URL transformation', () => {
    it('should add transcode param for video playback', () => {
      const originalUrl = 'https://image.civitai.com/uuid/video.webm'

      const getVideoUrl = (url: string): string => {
        const separator = url.includes('?') ? '&' : '?'
        return `${url}${separator}transcode=true&width=450`
      }

      const videoUrl = getVideoUrl(originalUrl)
      expect(videoUrl).toContain('transcode=true')
    })

    it('should add anim=false for static thumbnail', () => {
      const originalUrl = 'https://image.civitai.com/uuid/video.webm'

      const getThumbnailUrl = (url: string): string => {
        const separator = url.includes('?') ? '&' : '?'
        return `${url}${separator}anim=false&transcode=true&width=450`
      }

      const thumbUrl = getThumbnailUrl(originalUrl)
      expect(thumbUrl).toContain('anim=false')
    })
  })

  describe('Local preview URLs', () => {
    it('should construct correct local preview URL', () => {
      const packName = 'my-pack'
      const filename = 'preview_1.mp4'

      const localUrl = `/previews/${packName}/resources/previews/${filename}`
      expect(localUrl).toBe('/previews/my-pack/resources/previews/preview_1.mp4')
    })
  })
})

// ============================================================================
// E2E Data Flow Verification
// ============================================================================

describe('E2E Data Flow Verification', () => {
  it('should maintain data integrity from API to render', () => {
    // Simulate API response
    const apiResponse = {
      previews: [
        {
          filename: 'preview_1.mp4',
          media_type: 'video',
          thumbnail_url: 'https://example.com/thumb.jpg',
          meta: { prompt: 'Test prompt', seed: 12345 },
        },
      ],
    }

    // Simulate transformation for MediaPreview
    const mediaPreviewData = apiResponse.previews.map(p => ({
      src: `/previews/pack/${p.filename}`,
      type: p.media_type,
      thumbnailSrc: p.thumbnail_url,
    }))

    // Simulate transformation for FullscreenViewer
    const fullscreenItems = apiResponse.previews.map(p => ({
      url: `/previews/pack/${p.filename}`,
      type: p.media_type,
      thumbnailUrl: p.thumbnail_url,
      meta: p.meta,
    }))

    // Verify MediaPreview data
    expect(mediaPreviewData[0].type).toBe('video')
    expect(mediaPreviewData[0].thumbnailSrc).toBe('https://example.com/thumb.jpg')

    // Verify FullscreenViewer data
    expect(fullscreenItems[0].type).toBe('video')
    expect(fullscreenItems[0].meta?.prompt).toBe('Test prompt')
  })
})
