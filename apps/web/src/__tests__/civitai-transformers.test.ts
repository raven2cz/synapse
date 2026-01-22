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
    expect(result.previews[0].url).toBe('https://image.civitai.com/uuid/image.jpg')
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
    expect(result.previews[0].thumbnail_url).toContain('anim=false')
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
