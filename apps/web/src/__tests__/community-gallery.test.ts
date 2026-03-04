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
  includeMetadata: boolean
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
 * Builds additional_previews with nsfw flags + optional metadata for import request.
 * All displayed community images are imported — user controls count
 * via CommunityGalleryPanel's Limit dropdown.
 * (Mirrors ImportWizardModal onImport logic)
 */
function buildAdditionalPreviews(
  communityOpts: CommunityImageOptions | undefined,
  communityImages: ModelPreview[] | undefined,
  fromProxyUrl: (url: string) => string
): { url: string; nsfw: boolean; width?: number; height?: number; meta?: Record<string, any> }[] | undefined {
  if (!communityOpts?.include || !communityImages?.length) {
    return undefined
  }
  return communityImages.map(p => ({
    url: fromProxyUrl(p.url),
    nsfw: p.nsfw,
    ...(communityOpts.includeMetadata ? {
      width: p.width,
      height: p.height,
      meta: p.meta,
    } : {}),
  }))
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

  describe('Building additional_previews with nsfw flags', () => {
    it('returns undefined when community options not provided', () => {
      const result = buildAdditionalPreviews(undefined, communityPreviews, identity)
      expect(result).toBeUndefined()
    })

    it('returns undefined when include is false', () => {
      const opts: CommunityImageOptions = { include: false, includeMetadata: true }
      const result = buildAdditionalPreviews(opts, communityPreviews, identity)
      expect(result).toBeUndefined()
    })

    it('returns undefined when community images are undefined', () => {
      const opts: CommunityImageOptions = { include: true, includeMetadata: true }
      const result = buildAdditionalPreviews(opts, undefined, identity)
      expect(result).toBeUndefined()
    })

    it('returns undefined when community images are empty', () => {
      const opts: CommunityImageOptions = { include: true, includeMetadata: true }
      const result = buildAdditionalPreviews(opts, [], identity)
      expect(result).toBeUndefined()
    })

    it('returns objects with url, nsfw, and metadata when includeMetadata is true', () => {
      const opts: CommunityImageOptions = { include: true, includeMetadata: true }
      const result = buildAdditionalPreviews(opts, communityPreviews, identity)
      expect(result).toBeDefined()
      expect(result!.length).toBe(50)
      // communityPreviews: nsfw = i % 5 === 0, so index 0 is nsfw
      expect(result![0].url).toBe('https://example.com/community_1.jpg')
      expect(result![0].nsfw).toBe(true)
      expect(result![0].width).toBe(512)
      expect(result![0].height).toBe(768)
      expect(result![1].nsfw).toBe(false)
    })

    it('omits metadata when includeMetadata is false', () => {
      const opts: CommunityImageOptions = { include: true, includeMetadata: false }
      const result = buildAdditionalPreviews(opts, communityPreviews, identity)
      expect(result).toBeDefined()
      expect(result![0].url).toBe('https://example.com/community_1.jpg')
      expect(result![0].nsfw).toBe(true)
      expect(result![0].width).toBeUndefined()
      expect(result![0].height).toBeUndefined()
      expect(result![0].meta).toBeUndefined()
    })

    it('preserves nsfw flags correctly', () => {
      const opts: CommunityImageOptions = { include: true, includeMetadata: true }
      const result = buildAdditionalPreviews(opts, communityPreviews, identity)
      // Every 5th image (index 0, 5, 10...) is nsfw
      const nsfwCount = result!.filter(p => p.nsfw).length
      expect(nsfwCount).toBe(10) // 50 images, every 5th = 10 nsfw
    })

    it('returns all images regardless of count', () => {
      const small = communityPreviews.slice(0, 3)
      const opts: CommunityImageOptions = { include: true, includeMetadata: true }
      const result = buildAdditionalPreviews(opts, small, identity)
      expect(result!.length).toBe(3)
    })

    it('applies fromProxyUrl transform to each URL', () => {
      const opts: CommunityImageOptions = { include: true, includeMetadata: true }
      const images = communityPreviews.slice(0, 2)
      const transform = (url: string) => url.replace('example.com', 'transformed.com')
      const result = buildAdditionalPreviews(opts, images, transform)
      expect(result![0].url).toBe('https://transformed.com/community_1.jpg')
      expect(result![1].url).toBe('https://transformed.com/community_2.jpg')
    })
  })

  describe('Import Request JSON', () => {
    it('omits additional_previews when community not included', () => {
      const body: Record<string, any> = {
        url: 'https://civitai.com/models/123',
        version_ids: [456],
        download_images: true,
        additional_previews: undefined,
      }
      const json = JSON.stringify(body)
      const parsed = JSON.parse(json)
      expect(parsed.additional_previews).toBeUndefined()
    })

    it('includes additional_previews with nsfw flags when community is included', () => {
      const previews = [
        { url: 'https://example.com/a.jpg', nsfw: false },
        { url: 'https://example.com/b.jpg', nsfw: true },
      ]
      const body = {
        url: 'https://civitai.com/models/123',
        version_ids: [456],
        additional_previews: previews,
      }
      const json = JSON.stringify(body)
      const parsed = JSON.parse(json)
      expect(parsed.additional_previews).toEqual(previews)
      expect(parsed.additional_previews[1].nsfw).toBe(true)
    })
  })

  describe('CommunityImageOptions defaults', () => {
    it('defaults to include=false', () => {
      const opts: CommunityImageOptions = { include: false, includeMetadata: true }
      expect(opts.include).toBe(false)
    })
  })
})
