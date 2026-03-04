/**
 * Integration Tests: Browse Filter Propagation
 *
 * Tests that filter parameters propagate correctly from SearchParams
 * through the adapter to the bridge call.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// =============================================================================
// TrpcBridgeAdapter Filter Propagation
// =============================================================================

describe('TrpcBridgeAdapter — filter propagation', () => {
  let searchSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    searchSpy = vi.fn().mockResolvedValue({
      ok: true,
      data: { items: [], hasMore: false },
      meta: { cached: false, durationMs: 10, source: 'trpc' },
    })

    // Mock bridge on window
    ;(globalThis as any).window = {
      SynapseSearchBridge: {
        version: '10.0.0',
        isEnabled: () => true,
        getStatus: () => ({ enabled: true, nsfw: true, version: '10.0.0', cacheSize: 0, features: ['meilisearch', 'trpc'] }),
        search: searchSpy,
      },
    }
  })

  it('should pass baseModels as array (not single element)', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      baseModels: ['SDXL 1.0', 'Pony', 'SD 1.5'],
      limit: 20,
    })

    expect(searchSpy).toHaveBeenCalledOnce()
    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.baseModel).toEqual(['SDXL 1.0', 'Pony', 'SD 1.5'])
  })

  it('should pass undefined baseModel when no baseModels selected', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      baseModels: [],
      limit: 20,
    })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.baseModel).toBeUndefined()
  })

  it('should pass types as flat array', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      types: ['LORA', 'Checkpoint'],
      limit: 20,
    })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.types).toEqual(['LORA', 'Checkpoint'])
    // NOT nested: [['LORA', 'Checkpoint']]
    expect(Array.isArray(callArgs.filters.types[0])).toBe(false)
  })

  it('should pass fileFormat wrapped in array as fileFormats', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      fileFormat: 'SafeTensor',
      limit: 20,
    })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.fileFormats).toEqual(['SafeTensor'])
  })

  it('should pass undefined fileFormats when no fileFormat', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({ limit: 20 })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.fileFormats).toBeUndefined()
  })

  it('should pass category directly', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      category: 'character',
      limit: 20,
    })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.category).toBe('character')
  })

  it('should pass checkpointType directly', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      types: ['Checkpoint'],
      checkpointType: 'Trained',
      limit: 20,
    })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.filters.checkpointType).toBe('Trained')
  })

  it('should pass all filters together', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await adapter.search({
      query: 'anime',
      types: ['LORA', 'Checkpoint'],
      baseModels: ['SDXL 1.0', 'Pony'],
      fileFormat: 'SafeTensor',
      category: 'character',
      checkpointType: 'Trained',
      sort: 'Newest',
      period: 'Month',
      limit: 20,
    })

    const callArgs = searchSpy.mock.calls[0][0]
    expect(callArgs.q).toBe('anime')
    expect(callArgs.sort).toBe('Newest')
    expect(callArgs.period).toBe('Month')
    expect(callArgs.filters).toEqual({
      types: ['LORA', 'Checkpoint'],
      baseModel: ['SDXL 1.0', 'Pony'],
      fileFormats: ['SafeTensor'],
      category: 'character',
      checkpointType: 'Trained',
    })
  })
})

// =============================================================================
// SearchParams interface completeness
// =============================================================================

describe('SearchParams — new fields', () => {
  it('should accept all new filter fields', async () => {
    const params: import('@/lib/api/searchTypes').SearchParams = {
      query: 'test',
      types: ['LORA'],
      baseModels: ['SDXL 1.0'],
      sort: 'Most Liked',
      period: 'Month',
      nsfw: true,
      limit: 20,
      cursor: 'abc',
      fileFormat: 'SafeTensor',
      category: 'character',
      checkpointType: 'Trained',
    }

    expect(params.fileFormat).toBe('SafeTensor')
    expect(params.category).toBe('character')
    expect(params.checkpointType).toBe('Trained')
    expect(params.sort).toBe('Most Liked')
  })

  it('should accept new sort options in SortOption type', async () => {
    const sortValues: import('@/lib/api/searchTypes').SortOption[] = [
      'Most Downloaded',
      'Highest Rated',
      'Newest',
      'Most Discussed',
      'Most Collected',
      'Most Liked',
      'Most Images',
      'Oldest',
    ]

    expect(sortValues).toHaveLength(8)
  })
})
