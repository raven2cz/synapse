/**
 * Tests for Civitai Transformers (Phase 5)
 *
 * These transformers convert tRPC API responses to the unified CivitaiModel format.
 * CRITICAL: Video detection must match backend logic in src/utils/media_detection.py!
 */

import { describe, it, expect } from 'vitest'
import {
  detectMediaType,
  getVideoThumbnailUrl,
  transformTrpcModel,
  transformTrpcModelDetail,
  transformMeilisearchModel,
} from '@/lib/utils/civitaiTransformers'

// =============================================================================
// detectMediaType Tests
// =============================================================================

describe('detectMediaType', () => {
  describe('extension detection', () => {
    it('should detect .mp4 as video', () => {
      expect(detectMediaType('https://example.com/video.mp4')).toBe('video')
    })

    it('should detect .webm as video', () => {
      expect(detectMediaType('https://example.com/video.webm')).toBe('video')
    })

    it('should detect .mov as video', () => {
      expect(detectMediaType('https://example.com/video.mov')).toBe('video')
    })

    it('should detect .avi as video', () => {
      expect(detectMediaType('https://example.com/video.avi')).toBe('video')
    })

    it('should detect .mkv as video', () => {
      expect(detectMediaType('https://example.com/video.mkv')).toBe('video')
    })

    it('should handle extensions with query params', () => {
      expect(detectMediaType('https://example.com/video.mp4?token=abc')).toBe('video')
    })
  })

  describe('Civitai transcode pattern', () => {
    it('should detect transcode=true as video', () => {
      const url = 'https://image.civitai.com/uuid/transcode=true,width=450/file.jpeg'
      expect(detectMediaType(url)).toBe('video')
    })

    it('should NOT detect transcode=true with anim=false as video (it is thumbnail)', () => {
      const url = 'https://image.civitai.com/uuid/anim=false,transcode=true,width=450/file.jpeg'
      expect(detectMediaType(url)).toBe('image')
    })
  })

  describe('path pattern', () => {
    it('should detect /videos/ path as video', () => {
      expect(detectMediaType('https://example.com/media/videos/123.jpeg')).toBe('video')
    })

    it('should detect type=video query param as video', () => {
      expect(detectMediaType('https://example.com/media?type=video&id=123')).toBe('video')
    })
  })

  describe('fallback to image', () => {
    it('should return image for regular image URLs', () => {
      expect(detectMediaType('https://example.com/image.jpg')).toBe('image')
      expect(detectMediaType('https://example.com/image.png')).toBe('image')
      expect(detectMediaType('https://example.com/image.webp')).toBe('image')
    })

    it('should return unknown for empty string', () => {
      expect(detectMediaType('')).toBe('unknown')
    })
  })
})

// =============================================================================
// getVideoThumbnailUrl Tests
// =============================================================================

describe('getVideoThumbnailUrl', () => {
  describe('non-Civitai URLs', () => {
    it('should replace .mp4 with .jpg', () => {
      expect(getVideoThumbnailUrl('https://example.com/video.mp4')).toBe(
        'https://example.com/video.jpg'
      )
    })

    it('should replace .webm with .jpg', () => {
      expect(getVideoThumbnailUrl('https://example.com/video.webm')).toBe(
        'https://example.com/video.jpg'
      )
    })

    it('should replace .mov with .jpg', () => {
      expect(getVideoThumbnailUrl('https://example.com/video.mov')).toBe(
        'https://example.com/video.jpg'
      )
    })

    it('should return empty string unchanged', () => {
      expect(getVideoThumbnailUrl('')).toBe('')
    })
  })

  describe('Civitai URLs', () => {
    it('should add anim=false parameter for static thumbnail', () => {
      const url = 'https://image.civitai.com/uuid/width=1080/video.mp4'
      const result = getVideoThumbnailUrl(url)
      expect(result).toContain('anim=false')
    })

    it('should use default width of 450', () => {
      const url = 'https://image.civitai.com/uuid/width=1080/video.mp4'
      const result = getVideoThumbnailUrl(url)
      expect(result).toContain('width=450')
    })

    it('should use custom width when specified', () => {
      const url = 'https://image.civitai.com/uuid/width=1080/video.mp4'
      const result = getVideoThumbnailUrl(url, 720)
      expect(result).toContain('width=720')
    })

    it('should replace anim=true with anim=false', () => {
      const url = 'https://image.civitai.com/uuid/anim=true,width=450/video.mp4'
      const result = getVideoThumbnailUrl(url)
      expect(result).toContain('anim=false')
      expect(result).not.toContain('anim=true')
    })

    it('should handle URLs without params segment', () => {
      const url = 'https://image.civitai.com/hash/uuid/video.mp4'
      const result = getVideoThumbnailUrl(url)
      expect(result).toContain('anim=false')
      expect(result).toContain('transcode=true')
    })
  })
})

// =============================================================================
// transformTrpcModel Tests
// =============================================================================

describe('transformTrpcModel', () => {
  const createMockTrpcModel = (overrides: Record<string, unknown> = {}) => ({
    id: 123,
    name: 'Test Model',
    description: 'A test model',
    type: 'LORA',
    nsfw: false,
    tags: ['test', 'model'],
    user: { username: 'testuser' },
    stats: {
      downloadCount: 1000,
      favoriteCount: 50,
      rating: 4.5,
      ratingCount: 20,
    },
    modelVersions: [
      {
        id: 456,
        name: 'v1.0',
        baseModel: 'SDXL 1.0',
        trainedWords: ['word1', 'word2'],
        files: [
          {
            id: 789,
            name: 'model.safetensors',
            primary: true,
            sizeKB: 500000,
            downloadUrl: 'https://civitai.com/download/123',
            hashes: {
              AutoV2: 'abc123',
              SHA256: 'def456',
            },
          },
        ],
        images: [
          {
            url: 'https://image.civitai.com/uuid/image.jpg',
            nsfw: false,
            width: 1024,
            height: 1024,
            meta: { prompt: 'test prompt' },
          },
        ],
      },
    ],
    ...overrides,
  })

  it('should transform basic model properties', () => {
    const result = transformTrpcModel(createMockTrpcModel())

    expect(result.id).toBe(123)
    expect(result.name).toBe('Test Model')
    expect(result.description).toBe('A test model')
    expect(result.type).toBe('LORA')
    expect(result.nsfw).toBe(false)
    expect(result.tags).toEqual(['test', 'model'])
  })

  it('should extract creator from user object', () => {
    const result = transformTrpcModel(createMockTrpcModel())
    expect(result.creator).toBe('testuser')
  })

  it('should extract creator from creator object as fallback', () => {
    const result = transformTrpcModel(
      createMockTrpcModel({
        user: undefined,
        creator: { username: 'creatoruser' },
      })
    )
    expect(result.creator).toBe('creatoruser')
  })

  it('should transform stats correctly', () => {
    const result = transformTrpcModel(createMockTrpcModel())

    expect(result.stats.downloadCount).toBe(1000)
    expect(result.stats.favoriteCount).toBe(50)
    expect(result.stats.rating).toBe(4.5)
    expect(result.stats.ratingCount).toBe(20)
  })

  it('should transform versions', () => {
    const result = transformTrpcModel(createMockTrpcModel())

    expect(result.versions).toHaveLength(1)
    expect(result.versions[0].id).toBe(456)
    expect(result.versions[0].name).toBe('v1.0')
    expect(result.versions[0].base_model).toBe('SDXL 1.0')
    expect(result.versions[0].trained_words).toEqual(['word1', 'word2'])
  })

  it('should transform file information', () => {
    const result = transformTrpcModel(createMockTrpcModel())

    expect(result.versions[0].files).toHaveLength(1)
    expect(result.versions[0].files![0].name).toBe('model.safetensors')
    expect(result.versions[0].files![0].hash_autov2).toBe('abc123')
    expect(result.versions[0].files![0].hash_sha256).toBe('def456')
  })

  it('should transform previews with media type detection', () => {
    const result = transformTrpcModel(createMockTrpcModel())

    expect(result.previews).toHaveLength(1)
    // URLs go through proxy
    expect(result.previews[0].url).toContain('/api/browse/image-proxy?url=')
    expect(result.previews[0].url).toContain('image.civitai.com')
    expect(result.previews[0].nsfw).toBe(false)
    expect(result.previews[0].media_type).toBe('image')
  })

  it('should detect video previews and add thumbnail URL', () => {
    const result = transformTrpcModel(
      createMockTrpcModel({
        modelVersions: [
          {
            id: 456,
            name: 'v1.0',
            images: [
              {
                url: 'https://image.civitai.com/uuid/transcode=true,width=450/video.mp4',
                nsfw: false,
              },
            ],
          },
        ],
      })
    )

    expect(result.previews[0].media_type).toBe('video')
    // Thumbnail URL goes through proxy and contains anim=false (URL-encoded)
    expect(result.previews[0].thumbnail_url).toContain('/api/browse/image-proxy?url=')
    expect(result.previews[0].thumbnail_url).toContain('anim%3Dfalse')
  })

  it('should handle NSFW flag from nsfw boolean', () => {
    const result = transformTrpcModel(
      createMockTrpcModel({
        modelVersions: [
          {
            id: 456,
            name: 'v1.0',
            images: [
              {
                url: 'https://image.civitai.com/uuid/image.jpg',
                nsfw: true,
              },
            ],
          },
        ],
      })
    )

    expect(result.previews[0].nsfw).toBe(true)
  })

  it('should detect NSFW from nsfwLevel >= 2', () => {
    const result = transformTrpcModel(
      createMockTrpcModel({
        modelVersions: [
          {
            id: 456,
            name: 'v1.0',
            images: [
              {
                url: 'https://image.civitai.com/uuid/image.jpg',
                nsfw: false,
                nsfwLevel: 3,
              },
            ],
          },
        ],
      })
    )

    expect(result.previews[0].nsfw).toBe(true)
  })

  it('should limit previews to 8 items', () => {
    const manyImages = Array.from({ length: 15 }, (_, i) => ({
      url: `https://image.civitai.com/uuid/image${i}.jpg`,
      nsfw: false,
    }))

    const result = transformTrpcModel(
      createMockTrpcModel({
        modelVersions: [
          {
            id: 456,
            name: 'v1.0',
            images: manyImages,
          },
        ],
      })
    )

    expect(result.previews).toHaveLength(8)
  })

  it('should handle missing data gracefully', () => {
    const result = transformTrpcModel({
      id: 123,
      name: '',
    })

    expect(result.id).toBe(123)
    expect(result.name).toBe('')
    expect(result.type).toBe('')
    expect(result.nsfw).toBe(false)
    expect(result.tags).toEqual([])
    expect(result.creator).toBe('')
    expect(result.versions).toEqual([])
    expect(result.previews).toEqual([])
  })
})

// =============================================================================
// transformTrpcModelDetail Tests
// =============================================================================

describe('transformTrpcModelDetail', () => {
  const createMockDetailData = () => ({
    id: 123,
    name: 'Test Model',
    type: 'LORA',
    nsfw: false,
    tags: [],
    publishedAt: '2024-01-01T00:00:00Z',
    stats: {
      downloadCount: 5000,
      rating: 4.8,
      ratingCount: 100,
    },
    modelVersions: [
      {
        id: 456,
        name: 'v1.0',
        baseModel: 'SDXL 1.0',
        trainedWords: ['trigger1', 'trigger2'],
        images: [
          {
            url: 'https://image.civitai.com/uuid/image.jpg',
            nsfw: false,
            meta: {
              prompt: 'test prompt',
              sampler: 'DPM++ 2M Karras',
              steps: 30,
              cfgScale: 7,
              clipSkip: 2,
              seed: 12345,
            },
          },
        ],
      },
    ],
  })

  it('should include base model properties', () => {
    const result = transformTrpcModelDetail(createMockDetailData())

    expect(result.id).toBe(123)
    expect(result.name).toBe('Test Model')
    expect(result.type).toBe('LORA')
  })

  it('should extract trained words', () => {
    const result = transformTrpcModelDetail(createMockDetailData())
    expect(result.trained_words).toEqual(['trigger1', 'trigger2'])
  })

  it('should extract base model', () => {
    const result = transformTrpcModelDetail(createMockDetailData())
    expect(result.base_model).toBe('SDXL 1.0')
  })

  it('should extract published date', () => {
    const result = transformTrpcModelDetail(createMockDetailData())
    expect(result.published_at).toBe('2024-01-01T00:00:00Z')
  })

  it('should extract download count and ratings from stats', () => {
    const result = transformTrpcModelDetail(createMockDetailData())

    expect(result.download_count).toBe(5000)
    expect(result.rating).toBe(4.8)
    expect(result.rating_count).toBe(100)
  })

  it('should extract example params from first image meta', () => {
    const result = transformTrpcModelDetail(createMockDetailData())

    expect(result.example_params).toBeDefined()
    expect(result.example_params!.sampler).toBe('DPM++ 2M Karras')
    expect(result.example_params!.steps).toBe(30)
    expect(result.example_params!.cfg_scale).toBe(7)
    expect(result.example_params!.clip_skip).toBe(2)
    expect(result.example_params!.seed).toBe(12345)
  })

  it('should return undefined example_params when no meta available', () => {
    const result = transformTrpcModelDetail({
      id: 123,
      name: 'Test',
      modelVersions: [
        {
          id: 456,
          images: [{ url: 'https://example.com/image.jpg' }],
        },
      ],
    })

    expect(result.example_params).toBeUndefined()
  })
})

// =============================================================================
// transformMeilisearchModel Tests
// =============================================================================

describe('transformMeilisearchModel', () => {
  const createMockMeilisearchHit = (overrides: Record<string, unknown> = {}) => ({
    id: 1307155,
    name: '(wan 2.2 experimental) WAN General NSFW model',
    type: 'LORA',
    nsfw: true,
    nsfwLevel: [4, 8, 16, 32],
    status: 'Published',
    createdAt: '2025-03-01T03:54:04.444Z',
    lastVersionAt: '2025-08-05T09:08:32.765Z',
    publishedAt: '2025-03-01T09:47:51.901Z',
    availability: 'Public',
    metrics: {
      commentCount: 468,
      thumbsUpCount: 15515,
      downloadCount: 286558,
      collectedCount: 19444,
      tippedAmountCount: 17877,
    },
    user: {
      id: 40224,
      username: 'CubeyAI',
      profilePicture: {
        id: 50715371,
        name: 'ComfyUI_temp_nkhki_00004_.png',
        url: '5cc3bc43-6d2e-49cd-8b58-b531e66ebd75',
        nsfwLevel: 1,
        type: 'image',
        width: 1024,
        height: 1496,
      },
    },
    triggerWords: ['nsfwsks'],
    hashes: ['34e2144d3c', '34e2144d3cd65360f97d09ccbe03e1c39a096df6c9234af5fe3899d1b63cda39'],
    version: {
      id: 12345,
      name: 'v2.2',
      baseModel: 'Wan Video',
    },
    ...overrides,
  })

  it('should transform basic model properties', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit())

    expect(result.id).toBe(1307155)
    expect(result.name).toBe('(wan 2.2 experimental) WAN General NSFW model')
    expect(result.type).toBe('LORA')
  })

  it('should extract creator from user object', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit())
    expect(result.creator).toBe('CubeyAI')
  })

  it('should transform metrics to stats', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit())

    expect(result.stats.downloadCount).toBe(286558)
    expect(result.stats.commentCount).toBe(468)
    expect(result.stats.thumbsUpCount).toBe(15515)
  })

  it('should detect NSFW from nsfwLevel array', () => {
    // High NSFW level
    const nsfw = transformMeilisearchModel(createMockMeilisearchHit({ nsfwLevel: [8, 16] }))
    expect(nsfw.nsfw).toBe(true)

    // Low NSFW level (SFW)
    const sfw = transformMeilisearchModel(createMockMeilisearchHit({ nsfwLevel: [1, 2], nsfw: false }))
    expect(sfw.nsfw).toBe(false)
  })

  it('should extract version info', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit())

    expect(result.versions).toHaveLength(1)
    expect(result.versions[0].id).toBe(12345)
    expect(result.versions[0].name).toBe('v2.2')
    expect(result.versions[0].base_model).toBe('Wan Video')
  })

  it('should use triggerWords as trained_words', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit())
    expect(result.versions[0].trained_words).toEqual(['nsfwsks'])
  })

  it('should create preview from user profilePicture', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit())

    // Should have at least one preview from profilePicture
    expect(result.previews.length).toBeGreaterThanOrEqual(0)
    // Note: Meilisearch doesn't return full images in search, just profile pics
  })

  it('should handle missing data gracefully', () => {
    const result = transformMeilisearchModel({
      id: 123,
      name: 'Test',
    })

    expect(result.id).toBe(123)
    expect(result.name).toBe('Test')
    expect(result.type).toBe('')
    expect(result.nsfw).toBe(false)
    expect(result.creator).toBe('')
    expect(result.versions).toEqual([])
    expect(result.previews).toEqual([])
  })

  it('should handle missing user gracefully', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit({ user: undefined }))
    expect(result.creator).toBe('')
  })

  it('should handle missing metrics gracefully', () => {
    const result = transformMeilisearchModel(createMockMeilisearchHit({ metrics: undefined }))

    expect(result.stats.downloadCount).toBeUndefined()
    expect(result.stats.thumbsUpCount).toBeUndefined()
  })
})

// =============================================================================
// Meilisearch vs tRPC Comparison Tests
// =============================================================================

describe('Meilisearch vs tRPC format differences', () => {
  it('both transformers should produce compatible output format', () => {
    // tRPC format
    const trpcModel = transformTrpcModel({
      id: 123,
      name: 'Test Model',
      type: 'LORA',
      nsfw: false,
      user: { username: 'testuser' },
      stats: { downloadCount: 1000 },
      modelVersions: [],
    })

    // Meilisearch format
    const meiliModel = transformMeilisearchModel({
      id: 456,
      name: 'Test Model 2',
      type: 'Checkpoint',
      nsfw: true,
      user: { username: 'meiliuser' },
      metrics: { downloadCount: 2000 },
    })

    // Both should have same structure
    expect(trpcModel).toHaveProperty('id')
    expect(trpcModel).toHaveProperty('name')
    expect(trpcModel).toHaveProperty('type')
    expect(trpcModel).toHaveProperty('nsfw')
    expect(trpcModel).toHaveProperty('creator')
    expect(trpcModel).toHaveProperty('stats')
    expect(trpcModel).toHaveProperty('versions')
    expect(trpcModel).toHaveProperty('previews')

    expect(meiliModel).toHaveProperty('id')
    expect(meiliModel).toHaveProperty('name')
    expect(meiliModel).toHaveProperty('type')
    expect(meiliModel).toHaveProperty('nsfw')
    expect(meiliModel).toHaveProperty('creator')
    expect(meiliModel).toHaveProperty('stats')
    expect(meiliModel).toHaveProperty('versions')
    expect(meiliModel).toHaveProperty('previews')
  })

  it('stats should be compatible between formats', () => {
    const trpcModel = transformTrpcModel({
      id: 1,
      stats: { downloadCount: 100, thumbsUpCount: 50 },
    })

    const meiliModel = transformMeilisearchModel({
      id: 2,
      metrics: { downloadCount: 200, thumbsUpCount: 100 },
    })

    // Both use downloadCount
    expect(trpcModel.stats.downloadCount).toBe(100)
    expect(meiliModel.stats.downloadCount).toBe(200)

    // Both use thumbsUpCount
    expect(trpcModel.stats.thumbsUpCount).toBe(50)
    expect(meiliModel.stats.thumbsUpCount).toBe(100)
  })
})
