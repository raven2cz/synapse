/**
 * Test for tRPC model detail transformation.
 *
 * IMPORTANT: tRPC model.getById returns posts with only IDs, NOT images!
 * Images must be fetched separately via image.getInfinite endpoint.
 */

import { describe, it, expect } from 'vitest'
import { transformTrpcModelDetail } from '@/lib/utils/civitaiTransformers'

// Real tRPC model.getById structure - posts only have IDs!
const REAL_TRPC_MODEL_RESPONSE = {
  id: 43331,
  name: 'majicMIX realistic',
  type: 'Checkpoint',
  nsfw: false,
  user: { username: 'Merjic' },
  stats: {
    downloadCount: 1157157,
    favoriteCount: 62014,
    rating: 4.8,
    ratingCount: 520,
  },
  modelVersions: [
    {
      id: 176425,
      name: 'v7',
      baseModel: 'SD 1.5',
      trainedWords: [],
      files: [
        {
          id: 134792,
          name: 'majicmix7.safetensors',
          sizeKB: 2082642,
          primary: true,
        },
      ],
      // CRITICAL: tRPC returns posts with ONLY IDs, no images!
      posts: [
        { id: 658592 },
        { id: 892300 },
        { id: 953847 },
      ],
      // images array is NOT present in tRPC response!
    },
  ],
}

// Mock response from image.getInfinite endpoint
const MOCK_IMAGES_RESPONSE = {
  items: [
    {
      id: 5001,
      url: 'abc123-uuid',
      name: 'image1.jpeg',
      type: 'image',
      width: 512,
      height: 768,
      nsfw: false,
      nsfwLevel: 1,
      meta: {
        prompt: 'test prompt',
        seed: 12345,
        sampler: 'Euler a',
        steps: 20,
        cfgScale: 7,
      },
    },
    {
      id: 5002,
      url: 'def456-uuid',
      name: 'video1.mp4',
      type: 'video',
      width: 512,
      height: 768,
      nsfw: false,
      nsfwLevel: 1,
    },
    {
      id: 5003,
      url: 'ghi789-uuid',
      name: 'image2.jpeg',
      type: 'image',
      width: 1024,
      height: 1024,
      nsfw: true,
      nsfwLevel: 4,
    },
  ],
}

describe('tRPC Model Detail Transformation', () => {
  it('should handle model response without images (posts only have IDs)', () => {
    // Without injecting images, should return empty previews
    const result = transformTrpcModelDetail(
      JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    )

    expect(result.id).toBe(43331)
    expect(result.name).toBe('majicMIX realistic')
    expect(result.previews.length).toBe(0) // No images without separate fetch!
  })

  it('should work when images are injected from separate API call', () => {
    // Simulate what trpcBridgeAdapter does: inject images from getModelImages
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    data.modelVersions[0].images = MOCK_IMAGES_RESPONSE.items

    const result = transformTrpcModelDetail(data)

    expect(result.previews.length).toBe(3)
  })

  it('should correctly identify video type from injected images', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    data.modelVersions[0].images = MOCK_IMAGES_RESPONSE.items

    const result = transformTrpcModelDetail(data)

    // Second preview should be video
    expect(result.previews[1].media_type).toBe('video')
    expect(result.previews[1].thumbnail_url).toBeDefined()
  })

  it('should detect video by filename extension even without type field', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    // Simulate image without explicit type field but with .mp4 filename
    data.modelVersions[0].images = [
      {
        id: 6001,
        url: 'xyz-uuid-no-type',
        name: 'animation.mp4', // Video filename
        // NO type field!
        width: 512,
        height: 512,
        nsfw: false,
        nsfwLevel: 1,
      },
      {
        id: 6002,
        url: 'abc-uuid-no-type',
        name: 'preview.webm', // Also video
        width: 512,
        height: 512,
        nsfw: false,
        nsfwLevel: 1,
      },
      {
        id: 6003,
        url: 'def-uuid-no-type',
        name: 'image.jpeg', // Image
        width: 512,
        height: 512,
        nsfw: false,
        nsfwLevel: 1,
      },
    ]

    const result = transformTrpcModelDetail(data)

    // First two should be detected as video by filename
    expect(result.previews[0].media_type).toBe('video')
    expect(result.previews[0].thumbnail_url).toBeDefined()
    expect(result.previews[1].media_type).toBe('video')
    expect(result.previews[1].thumbnail_url).toBeDefined()
    // Third should be image
    expect(result.previews[2].media_type).toBe('image')
    expect(result.previews[2].thumbnail_url).toBeUndefined()
  })

  it('should correctly detect NSFW from nsfwLevel', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    data.modelVersions[0].images = MOCK_IMAGES_RESPONSE.items

    const result = transformTrpcModelDetail(data)

    // First two should be SFW (nsfwLevel 1)
    expect(result.previews[0].nsfw).toBe(false)
    expect(result.previews[1].nsfw).toBe(false)
    // Third should be NSFW (nsfwLevel 4)
    expect(result.previews[2].nsfw).toBe(true)
  })

  it('should use proxy URLs for Civitai CDN', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    data.modelVersions[0].images = MOCK_IMAGES_RESPONSE.items

    const result = transformTrpcModelDetail(data)

    // All URLs should go through proxy
    for (const preview of result.previews) {
      expect(preview.url).toContain('/api/browse/image-proxy')
    }
  })

  it('should preserve generation metadata', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))
    data.modelVersions[0].images = MOCK_IMAGES_RESPONSE.items

    const result = transformTrpcModelDetail(data)

    // First preview should have meta
    expect(result.previews[0].meta).toBeDefined()
    expect(result.previews[0].meta?.prompt).toBe('test prompt')
    expect(result.previews[0].meta?.seed).toBe(12345)
  })

  it('should extract model stats correctly', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))

    const result = transformTrpcModelDetail(data)

    expect(result.download_count).toBe(1157157)
    expect(result.rating).toBe(4.8)
    expect(result.rating_count).toBe(520)
  })

  it('should extract base model and version info', () => {
    const data = JSON.parse(JSON.stringify(REAL_TRPC_MODEL_RESPONSE))

    const result = transformTrpcModelDetail(data)

    expect(result.base_model).toBe('SD 1.5')
    expect(result.versions.length).toBe(1)
    expect(result.versions[0].name).toBe('v7')
  })
})
