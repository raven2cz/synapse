/**
 * Smoke Tests: Browse Filter End-to-End Flow
 *
 * Tests the full pipeline: BrowsePage state → adapter.search() → bridge.search()
 * Verifies that selecting filters in the UI results in correct bridge calls.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// =============================================================================
// Full Pipeline: State → Adapter → Bridge
// =============================================================================

describe('Browse filter smoke — full pipeline', () => {
  let searchSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    searchSpy = vi.fn().mockResolvedValue({
      ok: true,
      data: {
        items: [
          { id: 1, name: 'Test Model', type: 'LORA', nsfw: false, images: [] },
          { id: 2, name: 'Test Model 2', type: 'Checkpoint', nsfw: false, images: [] },
        ],
        hasMore: false,
      },
      meta: { cached: false, durationMs: 10, source: 'trpc' },
    })

    ;(globalThis as any).window = {
      SynapseSearchBridge: {
        version: '10.0.0',
        isEnabled: () => true,
        getStatus: () => ({
          enabled: true,
          nsfw: true,
          version: '10.0.0',
          cacheSize: 0,
          features: ['meilisearch', 'trpc'],
        }),
        search: searchSpy,
      },
    }
  })

  afterEach(() => {
    vi.resetModules()
    delete (globalThis as any).window
  })

  it('full filter combination produces correct bridge call', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    // Simulate what BrowsePage does with all filters set
    await adapter.search({
      query: 'anime style',
      types: ['LORA', 'Checkpoint'],
      baseModels: ['SDXL 1.0', 'Pony'],
      sort: 'Most Liked',
      period: 'Month',
      nsfw: true,
      limit: 20,
      cursor: undefined,
      fileFormat: 'SafeTensor',
      category: 'character',
      checkpointType: 'Trained',
    })

    expect(searchSpy).toHaveBeenCalledOnce()
    const call = searchSpy.mock.calls[0][0]

    // Query and sort
    expect(call.q).toBe('anime style')
    expect(call.sort).toBe('Most Liked')
    expect(call.period).toBe('Month')

    // Filters — correct structure
    expect(call.filters.types).toEqual(['LORA', 'Checkpoint'])
    expect(call.filters.baseModel).toEqual(['SDXL 1.0', 'Pony'])
    expect(call.filters.fileFormats).toEqual(['SafeTensor'])
    expect(call.filters.category).toBe('character')
    expect(call.filters.checkpointType).toBe('Trained')

    // No nested arrays
    expect(Array.isArray(call.filters.types)).toBe(true)
    expect(Array.isArray(call.filters.types[0])).toBe(false)
    expect(Array.isArray(call.filters.baseModel)).toBe(true)
    expect(Array.isArray(call.filters.baseModel[0])).toBe(false)
  })

  it('empty filters produce clean bridge call (no undefined pollution)', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    // Simulate BrowsePage with no filters (fresh load)
    await adapter.search({
      query: undefined,
      types: undefined,
      baseModels: [],
      sort: 'Most Downloaded',
      period: 'AllTime',
      nsfw: false,
      limit: 20,
    })

    const call = searchSpy.mock.calls[0][0]

    // No types, no base models, no optional filters
    expect(call.filters.types).toBeUndefined()
    expect(call.filters.baseModel).toBeUndefined()
    expect(call.filters.fileFormats).toBeUndefined()
    expect(call.filters.category).toBeUndefined()
    expect(call.filters.checkpointType).toBeUndefined()
  })

  it('single type + single baseModel still produces arrays', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      types: ['LORA'],
      baseModels: ['SDXL 1.0'],
      limit: 20,
    })

    const call = searchSpy.mock.calls[0][0]
    expect(call.filters.types).toEqual(['LORA'])
    expect(call.filters.baseModel).toEqual(['SDXL 1.0'])
    // Must be arrays, not strings
    expect(Array.isArray(call.filters.types)).toBe(true)
    expect(Array.isArray(call.filters.baseModel)).toBe(true)
  })

  it('checkpointType without Checkpoint type still passes through', async () => {
    // The adapter doesn't enforce the invariant — BrowsePage does via auto-clear.
    // If somehow checkpointType is set without Checkpoint, adapter passes it.
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      types: ['LORA'],
      checkpointType: 'Trained',
      limit: 20,
    })

    const call = searchSpy.mock.calls[0][0]
    expect(call.filters.types).toEqual(['LORA'])
    expect(call.filters.checkpointType).toBe('Trained')
  })

  it('new sort options pass through correctly', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    const newSorts = ['Most Liked', 'Most Images', 'Oldest'] as const
    for (const sort of newSorts) {
      searchSpy.mockClear()
      await adapter.search({ sort, limit: 20 })
      expect(searchSpy.mock.calls[0][0].sort).toBe(sort)
    }
  })

  it('fileFormat wraps as single-element fileFormats array', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    const formats = ['SafeTensor', 'GGUF', 'Diffusers']
    for (const format of formats) {
      searchSpy.mockClear()
      await adapter.search({ fileFormat: format, limit: 20 })
      expect(searchSpy.mock.calls[0][0].filters.fileFormats).toEqual([format])
    }
  })

  it('multiple baseModels all pass through (not just first)', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    const models = ['SDXL 1.0', 'Pony', 'SD 1.5', 'Flux.1 D']
    await adapter.search({ baseModels: models, limit: 20 })

    const call = searchSpy.mock.calls[0][0]
    expect(call.filters.baseModel).toEqual(models)
    expect(call.filters.baseModel).toHaveLength(4)
  })
})

// =============================================================================
// SearchParams ↔ Adapter contract
// =============================================================================

describe('SearchParams → Adapter contract', () => {
  let searchSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    searchSpy = vi.fn().mockResolvedValue({
      ok: true,
      data: { items: [], hasMore: false },
      meta: { cached: false, durationMs: 5, source: 'trpc' },
    })

    ;(globalThis as any).window = {
      SynapseSearchBridge: {
        version: '10.0.0',
        isEnabled: () => true,
        getStatus: () => ({
          enabled: true,
          nsfw: true,
          version: '10.0.0',
          cacheSize: 0,
          features: ['meilisearch', 'trpc'],
        }),
        search: searchSpy,
      },
    }
  })

  afterEach(() => {
    vi.resetModules()
    delete (globalThis as any).window
  })

  it('adapter handles all SearchParams fields without error', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    // Every field from SearchParams
    const fullParams: import('@/lib/api/searchTypes').SearchParams = {
      query: 'full test',
      types: ['LORA', 'Checkpoint', 'TextualInversion'],
      baseModels: ['SDXL 1.0', 'Pony', 'SD 1.5'],
      sort: 'Oldest',
      period: 'Year',
      nsfw: true,
      limit: 40,
      cursor: 'cursor123',
      fileFormat: 'GGUF',
      category: 'poses',
      checkpointType: 'Merge',
    }

    // Should not throw
    const result = await adapter.search(fullParams)
    expect(result).toBeDefined()
    expect(searchSpy).toHaveBeenCalledOnce()

    const call = searchSpy.mock.calls[0][0]
    expect(call.filters.types).toEqual(['LORA', 'Checkpoint', 'TextualInversion'])
    expect(call.filters.baseModel).toEqual(['SDXL 1.0', 'Pony', 'SD 1.5'])
    expect(call.filters.fileFormats).toEqual(['GGUF'])
    expect(call.filters.category).toBe('poses')
    expect(call.filters.checkpointType).toBe('Merge')
  })

  it('adapter gracefully handles undefined optional fields', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    // Only required field
    const result = await adapter.search({ limit: 20 })
    expect(result).toBeDefined()
    expect(searchSpy).toHaveBeenCalledOnce()
  })
})
