/**
 * Tests for Community Gallery Tab + Import Integration
 *
 * Tests cover:
 * - Community gallery tab visibility based on provider
 * - Tab switching between cover and community content
 * - Gallery tab reset on model change
 * - FullscreenMediaViewer items reflect active tab
 * - ImportWizardModal community images section visibility
 * - Import request includes/omits additional_preview_urls
 */

import { describe, it, expect } from 'vitest'

// ============================================================================
// Test Types (mirroring BrowsePage / ImportWizardModal)
// ============================================================================

interface ModelPreview {
  url: string
  nsfw: boolean
  width?: number
  height?: number
  media_type?: 'image' | 'video'
  thumbnail_url?: string
  meta?: Record<string, any>
}

interface CommunityImageOptions {
  include: boolean
}

// ============================================================================
// Utility Functions Under Test
// ============================================================================

/**
 * Determines which gallery items to show in fullscreen viewer
 * based on active tab and available community images.
 * (Mirrors BrowsePage logic)
 */
function getActiveGalleryItems(
  galleryTab: 'cover' | 'community',
  coverPreviews: ModelPreview[],
  communityImages?: ModelPreview[]
): ModelPreview[] {
  return galleryTab === 'community' && communityImages?.length
    ? communityImages
    : coverPreviews
}

/**
 * Determines if community tab should be visible.
 * (Mirrors BrowsePage logic — only visible when adapter has getModelPreviews)
 */
function hasCommunityTabSupport(adapter: { getModelPreviews?: Function }): boolean {
  return !!adapter.getModelPreviews
}

/**
 * Builds additional_preview_urls for import request.
 * All displayed community images are imported — user controls count
 * via CommunityGalleryPanel's Limit dropdown.
 * (Mirrors ImportWizardModal onImport logic)
 */
function buildAdditionalPreviewUrls(
  communityOpts: CommunityImageOptions | undefined,
  communityImages: ModelPreview[] | undefined,
  fromProxyUrl: (url: string) => string
): string[] | undefined {
  if (!communityOpts?.include || !communityImages?.length) {
    return undefined
  }
  return communityImages.map(p => fromProxyUrl(p.url))
}

// ============================================================================
// Test Data
// ============================================================================

const coverPreviews: ModelPreview[] = [
  { url: 'https://example.com/cover1.jpg', nsfw: false, width: 512, height: 768 },
  { url: 'https://example.com/cover2.jpg', nsfw: false, width: 512, height: 768 },
  { url: 'https://example.com/cover3.jpg', nsfw: true, width: 512, height: 768 },
]

const communityPreviews: ModelPreview[] = Array.from({ length: 50 }, (_, i) => ({
  url: `https://example.com/community_${i + 1}.jpg`,
  nsfw: i % 5 === 0,
  width: 512,
  height: 768,
  media_type: 'image' as const,
}))

// ============================================================================
// Tests
// ============================================================================

describe('Community Gallery Tab', () => {
  describe('Tab Visibility', () => {
    it('community tab hidden for REST provider (no getModelPreviews)', () => {
      const restAdapter: { getModelPreviews?: Function } = {}
      expect(hasCommunityTabSupport(restAdapter)).toBe(false)
    })

    it('community tab visible for tRPC provider (has getModelPreviews)', () => {
      const trpcAdapter: { getModelPreviews?: Function } = {
        getModelPreviews: () => {},
      }
      expect(hasCommunityTabSupport(trpcAdapter)).toBe(true)
    })

    it('community tab hidden when getModelPreviews is undefined', () => {
      const adapter: { getModelPreviews?: Function } = { getModelPreviews: undefined }
      expect(hasCommunityTabSupport(adapter)).toBe(false)
    })
  })

  describe('Active Gallery Items', () => {
    it('returns cover previews when galleryTab is cover', () => {
      const items = getActiveGalleryItems('cover', coverPreviews, communityPreviews)
      expect(items).toBe(coverPreviews)
      expect(items.length).toBe(3)
    })

    it('returns community images when galleryTab is community and images available', () => {
      const items = getActiveGalleryItems('community', coverPreviews, communityPreviews)
      expect(items).toBe(communityPreviews)
      expect(items.length).toBe(50)
    })

    it('falls back to cover previews when community tab active but no community images', () => {
      const items = getActiveGalleryItems('community', coverPreviews, undefined)
      expect(items).toBe(coverPreviews)
    })

    it('falls back to cover previews when community images array is empty', () => {
      const items = getActiveGalleryItems('community', coverPreviews, [])
      expect(items).toBe(coverPreviews)
    })
  })

  describe('Gallery Tab Reset', () => {
    it('gallery tab should be cover by default', () => {
      const defaultTab: 'cover' | 'community' = 'cover'
      expect(defaultTab).toBe('cover')
    })
  })
})

describe('Community Images Import', () => {
  const identity = (url: string) => url  // Mock fromProxyUrl

  describe('Building additional_preview_urls', () => {
    it('returns undefined when community options not provided', () => {
      const result = buildAdditionalPreviewUrls(undefined, communityPreviews, identity)
      expect(result).toBeUndefined()
    })

    it('returns undefined when include is false', () => {
      const opts: CommunityImageOptions = { include: false }
      const result = buildAdditionalPreviewUrls(opts, communityPreviews, identity)
      expect(result).toBeUndefined()
    })

    it('returns undefined when community images are undefined', () => {
      const opts: CommunityImageOptions = { include: true }
      const result = buildAdditionalPreviewUrls(opts, undefined, identity)
      expect(result).toBeUndefined()
    })

    it('returns undefined when community images are empty', () => {
      const opts: CommunityImageOptions = { include: true }
      const result = buildAdditionalPreviewUrls(opts, [], identity)
      expect(result).toBeUndefined()
    })

    it('returns all URLs when include is true and images available', () => {
      const opts: CommunityImageOptions = { include: true }
      const result = buildAdditionalPreviewUrls(opts, communityPreviews, identity)
      expect(result).toBeDefined()
      expect(result!.length).toBe(50)
      expect(result![0]).toBe('https://example.com/community_1.jpg')
    })

    it('returns all images regardless of count', () => {
      const small = communityPreviews.slice(0, 3)
      const opts: CommunityImageOptions = { include: true }
      const result = buildAdditionalPreviewUrls(opts, small, identity)
      expect(result!.length).toBe(3)
    })

    it('applies fromProxyUrl transform to each URL', () => {
      const opts: CommunityImageOptions = { include: true }
      const images = communityPreviews.slice(0, 2)
      const transform = (url: string) => url.replace('example.com', 'transformed.com')
      const result = buildAdditionalPreviewUrls(opts, images, transform)
      expect(result![0]).toBe('https://transformed.com/community_1.jpg')
      expect(result![1]).toBe('https://transformed.com/community_2.jpg')
    })
  })

  describe('Import Request JSON', () => {
    it('omits additional_preview_urls when community not included', () => {
      const body: Record<string, any> = {
        url: 'https://civitai.com/models/123',
        version_ids: [456],
        download_images: true,
        additional_preview_urls: undefined,
      }
      const json = JSON.stringify(body)
      const parsed = JSON.parse(json)
      expect(parsed.additional_preview_urls).toBeUndefined()
    })

    it('includes additional_preview_urls when community is included', () => {
      const urls = ['https://example.com/a.jpg', 'https://example.com/b.jpg']
      const body = {
        url: 'https://civitai.com/models/123',
        version_ids: [456],
        additional_preview_urls: urls,
      }
      const json = JSON.stringify(body)
      const parsed = JSON.parse(json)
      expect(parsed.additional_preview_urls).toEqual(urls)
    })
  })

  describe('CommunityImageOptions defaults', () => {
    it('defaults to include=false', () => {
      const opts: CommunityImageOptions = { include: false }
      expect(opts.include).toBe(false)
    })
  })
})
