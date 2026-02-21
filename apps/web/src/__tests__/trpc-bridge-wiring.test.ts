/**
 * Tests for tRPC Bridge Adapter — Split Query Pattern.
 *
 * Architecture:
 *   getModelDetail()   → bridge.getModel() → returns model WITHOUT images (fast ~1s)
 *   getModelPreviews() → bridge.getModelImages(versionId) → returns images separately
 *
 * Key insight: image.getInfinite requires modelVersionId, NOT modelId.
 * BrowsePage uses two React Queries: model info (opens panel) + images (progressive).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Helper: create a mock bridge with configurable methods
function makeBridge(overrides: Record<string, unknown> = {}) {
  return {
    version: '10.0.0',
    isEnabled: () => true,
    getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
    search: vi.fn(),
    ...overrides,
  }
}

// Helper: model data as returned by tRPC model.getById (images always empty)
function makeModelData(id: number, name: string, versions: { id: number; name: string }[]) {
  return {
    id,
    name,
    type: 'LORA',
    nsfw: false,
    user: { username: 'test' },
    stats: { downloadCount: 100 },
    modelVersions: versions.map(v => ({
      id: v.id,
      name: v.name,
      baseModel: 'SDXL 1.0',
      files: [],
      images: [], // tRPC model.getById always returns empty images
    })),
  }
}

describe('TrpcBridgeAdapter — Split Query Pattern', () => {
  let originalBridge: unknown

  beforeEach(() => {
    originalBridge = (window as unknown as Record<string, unknown>).SynapseSearchBridge
  })

  afterEach(() => {
    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = originalBridge
    vi.restoreAllMocks()
  })

  // ===========================================================================
  // getModelDetail — fast, returns model WITHOUT images
  // ===========================================================================

  describe('getModelDetail (fast model info)', () => {
    it('should return model data without waiting for images', async () => {
      const getModel = vi.fn().mockResolvedValue({
        ok: true,
        data: makeModelData(123, 'Test Model', [{ id: 456, name: 'v1' }]),
      })

      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel,
        getModelImages: vi.fn(), // exists but should NOT be called
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()
      const result = await adapter.getModelDetail(123)

      expect(getModel).toHaveBeenCalledWith(123)
      // getModelImages should NOT be called — images are loaded separately
      expect((window.SynapseSearchBridge as any).getModelImages).not.toHaveBeenCalled()

      expect(result.id).toBe(123)
      expect(result.name).toBe('Test Model')
      expect(result.previews.length).toBe(0) // No images in model.getById
    })

    it('should fall back to REST when bridge.getModel unavailable', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: 123, name: 'REST Model', type: 'LORA', previews: [{ url: 'img.jpg', nsfw: false }], versions: [],
        }),
      })
      vi.stubGlobal('fetch', mockFetch)

      // Bridge without getModel method
      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge()

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()
      const result = await adapter.getModelDetail(123)

      expect(mockFetch).toHaveBeenCalledWith('/api/browse/model/123')
      expect(result.name).toBe('REST Model')
      // REST includes images — Query 2 won't fire in BrowsePage
      expect(result.previews.length).toBe(1)
    })

    it('should fall back to REST when bridge.getModel fails', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 999, name: 'Fallback', type: 'LORA', previews: [], versions: [] }),
      })
      vi.stubGlobal('fetch', mockFetch)

      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel: vi.fn().mockResolvedValue({ ok: false, error: { code: 'NOT_FOUND', message: 'Not found' } }),
        getModelImages: vi.fn(),
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()
      const result = await adapter.getModelDetail(999)

      expect(mockFetch).toHaveBeenCalledWith('/api/browse/model/999')
      expect(result.name).toBe('Fallback')
    })
  })

  // ===========================================================================
  // getModelPreviews — separate image loading with correct modelVersionId
  // ===========================================================================

  describe('getModelPreviews (progressive image loading)', () => {
    it('should call getModelImages with modelVersionId (not modelId)', async () => {
      const getModelImages = vi.fn().mockResolvedValue({
        ok: true,
        data: {
          items: [
            { id: 1, url: 'uuid-1', type: 'image', width: 512, height: 768, nsfw: false, nsfwLevel: 1 },
            { id: 2, url: 'uuid-2', type: 'image', width: 512, height: 768, nsfw: false, nsfwLevel: 1 },
          ],
        },
      })

      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel: vi.fn(),
        getModelImages,
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()

      // Simulates BrowsePage calling getModelPreviews with versionId from Query 1
      const previews = await adapter.getModelPreviews(123, 456)

      // Must use modelVersionId (456), NOT modelId (123)
      expect(getModelImages).toHaveBeenCalledWith(456, expect.objectContaining({ limit: 50 }))
      expect(previews.length).toBe(2)
      expect(previews[0].url).toBeDefined()
    })

    it('should throw when getModelImages returns error', async () => {
      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel: vi.fn(),
        getModelImages: vi.fn().mockResolvedValue({
          ok: false, error: { code: 'TIMEOUT', message: 'Timed out' },
        }),
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()

      // Should throw — BrowsePage will catch this and fall back to REST
      await expect(adapter.getModelPreviews(123, 456)).rejects.toThrow('Timed out')
    })

    it('should timeout after 15s when getModelImages hangs', async () => {
      vi.useFakeTimers()

      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel: vi.fn(),
        getModelImages: vi.fn().mockReturnValue(new Promise(() => {})), // never resolves
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()

      let caughtError: Error | null = null
      const promise = adapter.getModelPreviews(123, 456).catch((err) => {
        caughtError = err
      })

      await vi.advanceTimersByTimeAsync(16_000)
      await promise

      expect(caughtError).not.toBeNull()
      expect(caughtError!.message).toContain('timeout')

      vi.useRealTimers()
    })

    it('should throw when bridge has no getModelImages', async () => {
      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge()

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()

      await expect(adapter.getModelPreviews(123, 456)).rejects.toThrow('not available')
    })
  })

  // ===========================================================================
  // Real-world model patterns
  // ===========================================================================

  describe('real-world patterns', () => {
    it('blindbox pattern: model.getById returns images:[] but getModelImages returns data', async () => {
      // Reproduces: blindbox/大概是盲盒 (model 25995)
      // model.getById returns versions with images: [] (images live in posts)
      // image.getInfinite with modelVersionId returns the actual images
      const getModel = vi.fn().mockResolvedValue({
        ok: true,
        data: {
          id: 25995,
          name: 'blindbox/大概是盲盒',
          type: 'LORA',
          nsfw: false,
          user: { username: 'samecorner' },
          stats: { downloadCount: 298319 },
          modelVersions: [
            { id: 32988, name: 'blindbox_v1_mix', baseModel: 'SD 1.5', files: [], images: [] },
            { id: 48150, name: 'blindbox_v3', baseModel: 'SD 1.5', files: [], images: [] },
          ],
        },
      })

      const getModelImages = vi.fn().mockResolvedValue({
        ok: true,
        data: {
          items: [
            { id: 101, url: 'uuid-blindbox-1', type: 'image', width: 512, height: 768, nsfw: false, nsfwLevel: 1 },
            { id: 102, url: 'uuid-blindbox-2', type: 'image', width: 512, height: 768, nsfw: false, nsfwLevel: 1 },
            { id: 103, url: 'uuid-blindbox-3', type: 'image', width: 512, height: 768, nsfw: false, nsfwLevel: 1 },
          ],
        },
      })

      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel,
        getModelImages,
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()

      // Step 1: getModelDetail returns fast with 0 previews
      const modelInfo = await adapter.getModelDetail(25995)
      expect(getModel).toHaveBeenCalledWith(25995)
      expect(modelInfo.id).toBe(25995)
      expect(modelInfo.previews.length).toBe(0) // No images from model.getById

      // Step 2: getModelPreviews loads images separately (using versionId from step 1)
      const firstVersionId = modelInfo.versions[0]?.id
      expect(firstVersionId).toBe(32988)

      const previews = await adapter.getModelPreviews(25995, firstVersionId!)
      expect(getModelImages).toHaveBeenCalledWith(32988, expect.objectContaining({ limit: 50 }))
      expect(previews.length).toBe(3)
    })

    it('model with no versions: getModelDetail returns 0 previews, getModelPreviews not needed', async () => {
      ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = makeBridge({
        getModel: vi.fn().mockResolvedValue({
          ok: true,
          data: {
            id: 777, name: 'Empty Model', type: 'LORA', nsfw: false,
            user: { username: 'test' }, stats: {},
            modelVersions: [],
          },
        }),
        getModelImages: vi.fn(),
      })

      const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
      const adapter = new TrpcBridgeAdapter()
      const result = await adapter.getModelDetail(777)

      expect(result.id).toBe(777)
      expect(result.previews.length).toBe(0)
      expect(result.versions.length).toBe(0)
      // No versionId → BrowsePage won't call getModelPreviews
    })
  })
})
