/**
 * Tests for tRPC Bridge Adapter model detail wiring.
 *
 * Verifies the sequential flow: getModel() → extract modelVersionId → getModelImages(versionId)
 * Key insight: image.getInfinite requires modelVersionId, NOT modelId.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('TrpcBridgeAdapter.getModelDetail wiring', () => {
  let originalBridge: unknown

  beforeEach(() => {
    originalBridge = (window as unknown as Record<string, unknown>).SynapseSearchBridge
  })

  afterEach(() => {
    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = originalBridge
    vi.restoreAllMocks()
  })

  it('should pass modelVersionId (not modelId) to getModelImages', async () => {
    const getModel = vi.fn().mockResolvedValue({
      ok: true,
      data: {
        id: 123,
        name: 'Test Model',
        type: 'LORA',
        nsfw: false,
        user: { username: 'test' },
        stats: { downloadCount: 100 },
        modelVersions: [
          { id: 456, name: 'v1', baseModel: 'SDXL 1.0', files: [], images: [] },
        ],
      },
    })

    const getModelImages = vi.fn().mockResolvedValue({
      ok: true,
      data: {
        items: [
          { id: 1, url: 'uuid-1', type: 'image', width: 512, height: 768, nsfw: false, nsfwLevel: 1 },
        ],
      },
    })

    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
      getModel,
      getModelImages,
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(123)

    // getModel receives the modelId
    expect(getModel).toHaveBeenCalledWith(123)
    // getModelImages receives the modelVERSIONId (456), NOT modelId (123)
    expect(getModelImages).toHaveBeenCalledWith(456, expect.objectContaining({ limit: 50 }))

    expect(result.id).toBe(123)
    expect(result.previews.length).toBe(1)
  })

  it('should fall back to REST when bridge methods unavailable', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 123, name: 'REST Model', type: 'LORA', previews: [], versions: [] }),
    })
    vi.stubGlobal('fetch', mockFetch)

    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(123)

    expect(mockFetch).toHaveBeenCalledWith('/api/browse/model/123')
    expect(result.name).toBe('REST Model')
  })

  it('should fall back to REST when getModel fails', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 999, name: 'Fallback', type: 'LORA', previews: [], versions: [] }),
    })
    vi.stubGlobal('fetch', mockFetch)

    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
      getModel: vi.fn().mockResolvedValue({ ok: false, error: { code: 'NOT_FOUND', message: 'Not found' } }),
      getModelImages: vi.fn(),
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(999)

    expect(mockFetch).toHaveBeenCalledWith('/api/browse/model/999')
    expect(result.name).toBe('Fallback')
  })

  it('should return model without images when getModelImages fails', async () => {
    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
      getModel: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          id: 123, name: 'Test', type: 'LORA', nsfw: false,
          user: { username: 'test' }, stats: {},
          modelVersions: [{ id: 1, name: 'v1', baseModel: 'SDXL', files: [] }],
        },
      }),
      getModelImages: vi.fn().mockResolvedValue({ ok: false, error: { code: 'TIMEOUT', message: 'Timed out' } }),
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(123)

    expect(result.id).toBe(123)
    expect(result.previews.length).toBe(0)
  })

  it('should inject images into model with empty version images (blindbox pattern)', async () => {
    // Reproduces: blindbox/大概是盲盒 (model 25995)
    // model.getById returns versions with images: [] (images live in posts, not versions)
    // image.getInfinite with modelVersionId returns the actual images
    const getModel = vi.fn().mockResolvedValue({
      ok: true,
      data: {
        id: 25995,
        name: 'blindbox/大概是盲盒',
        type: 'LORA',
        nsfw: false,
        user: { username: 'samecorner' },
        stats: { downloadCount: 298319, thumbsUpCount: 14204 },
        modelVersions: [
          { id: 32988, name: 'blindbox_v1_mix', baseModel: 'SD 1.5', files: [], images: [], posts: [{ id: 81807 }] },
          { id: 48150, name: 'blindbox_v3', baseModel: 'SD 1.5', files: [], images: [], posts: [{ id: 149906 }] },
          { id: 32376, name: 'blindbox_v2', baseModel: 'SD 1.5', files: [], images: [], posts: [{ id: 82963 }] },
          { id: 31123, name: 'blindbox_v1', baseModel: 'SD 1.5', files: [], images: [], posts: [{ id: 78954 }] },
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

    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
      getModel,
      getModelImages,
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(25995)

    // Should call getModel with modelId
    expect(getModel).toHaveBeenCalledWith(25995)
    // Should call getModelImages with FIRST version's ID (32988), not modelId (25995)
    expect(getModelImages).toHaveBeenCalledWith(32988, expect.objectContaining({ limit: 50 }))

    // Images should be injected despite model.getById returning images: []
    expect(result.id).toBe(25995)
    expect(result.name).toBe('blindbox/大概是盲盒')
    expect(result.previews.length).toBe(3)
  })

  it('should handle model with no modelVersions gracefully', async () => {
    // Edge case: model exists but has no versions at all
    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
      getModel: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          id: 777, name: 'Empty Model', type: 'LORA', nsfw: false,
          user: { username: 'test' }, stats: {},
          modelVersions: [],
        },
      }),
      getModelImages: vi.fn(),
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(777)

    // Should NOT call getModelImages when there are no versions
    expect((window.SynapseSearchBridge as any).getModelImages).not.toHaveBeenCalled()
    expect(result.id).toBe(777)
    expect(result.previews.length).toBe(0)
  })

  it('should handle getModelImages hang with timeout', async () => {
    vi.useFakeTimers()

    ;(window as unknown as Record<string, unknown>).SynapseSearchBridge = {
      version: '10.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0 }),
      search: vi.fn(),
      getModel: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          id: 123, name: 'Timeout Test', type: 'LORA', nsfw: false,
          user: { username: 'test' }, stats: {},
          modelVersions: [{ id: 1, name: 'v1', baseModel: 'SDXL', files: [] }],
        },
      }),
      getModelImages: vi.fn().mockReturnValue(new Promise(() => {})), // never resolves
    }

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()
    const promise = adapter.getModelDetail(123)

    await vi.advanceTimersByTimeAsync(16_000)
    const result = await promise

    expect(result.id).toBe(123)
    expect(result.previews.length).toBe(0)

    vi.useRealTimers()
  })
})
