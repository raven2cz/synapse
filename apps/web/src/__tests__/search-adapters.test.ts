/**
 * Tests for Search Adapters (Phase 5)
 *
 * Tests the adapter registry and individual adapters.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock fetch for REST and Archive adapters
const mockFetch = vi.fn()
;(globalThis as unknown as { fetch: typeof fetch }).fetch = mockFetch

// =============================================================================
// Search Types Tests
// =============================================================================

describe('Search Types', () => {
  it('should have correct PROVIDER_CONFIGS', async () => {
    const { PROVIDER_CONFIGS } = await import('@/lib/api/searchTypes')

    expect(PROVIDER_CONFIGS.trpc.provider).toBe('trpc')
    expect(PROVIDER_CONFIGS.rest.provider).toBe('rest')
    expect(PROVIDER_CONFIGS.archive.provider).toBe('archive')

    // Check display names
    expect(PROVIDER_CONFIGS.trpc.shortName).toBe('tRPC')
    expect(PROVIDER_CONFIGS.rest.shortName).toBe('REST')
    expect(PROVIDER_CONFIGS.archive.shortName).toBe('Archive')
  })

  it('should have sort options', async () => {
    const { SORT_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(SORT_OPTIONS).toContainEqual({ value: 'Most Downloaded', label: 'Most Downloaded' })
    expect(SORT_OPTIONS).toContainEqual({ value: 'Newest', label: 'Newest' })
    expect(SORT_OPTIONS).toContainEqual({ value: 'Highest Rated', label: 'Highest Rated' })
  })

  it('should have period options', async () => {
    const { PERIOD_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(PERIOD_OPTIONS).toContainEqual({ value: 'AllTime', label: 'All Time' })
    expect(PERIOD_OPTIONS).toContainEqual({ value: 'Month', label: 'This Month' })
    expect(PERIOD_OPTIONS).toContainEqual({ value: 'Week', label: 'This Week' })
  })

  it('should have base model options', async () => {
    const { BASE_MODEL_OPTIONS } = await import('@/lib/api/searchTypes')

    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SDXL 1.0', label: 'SDXL 1.0' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'SD 1.5', label: 'SD 1.5' })
    expect(BASE_MODEL_OPTIONS).toContainEqual({ value: 'Pony', label: 'Pony' })
  })
})

// =============================================================================
// REST Adapter Tests
// =============================================================================

describe('RestSearchAdapter', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('should have correct metadata', async () => {
    const { RestSearchAdapter } = await import('@/lib/api/adapters/restAdapter')
    const adapter = new RestSearchAdapter()

    expect(adapter.provider).toBe('rest')
    expect(adapter.displayName).toBe('REST API')
    expect(adapter.description).toContain('Standard')
  })

  it('should always be available', async () => {
    const { RestSearchAdapter } = await import('@/lib/api/adapters/restAdapter')
    const adapter = new RestSearchAdapter()

    expect(adapter.isAvailable()).toBe(true)
  })

  it('should call backend API with correct params', async () => {
    const { RestSearchAdapter } = await import('@/lib/api/adapters/restAdapter')
    const adapter = new RestSearchAdapter()

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          items: [{ id: 1, name: 'Test Model' }],
          next_cursor: 'abc',
        }),
    })

    await adapter.search({
      query: 'test',
      sort: 'Most Downloaded',
      limit: 20,
    })

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const callUrl = mockFetch.mock.calls[0][0] as string
    expect(callUrl).toContain('/api/browse/search')
    expect(callUrl).toContain('query=test')
    expect(callUrl).toContain('sort=Most+Downloaded')
  })

  it('should return transformed results', async () => {
    const { RestSearchAdapter } = await import('@/lib/api/adapters/restAdapter')
    const adapter = new RestSearchAdapter()

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          items: [
            {
              id: 123,
              name: 'Test Model',
              type: 'LORA',
              nsfw: false,
              modelVersions: [
                {
                  id: 456,
                  name: 'v1.0',
                  images: [{ url: 'https://example.com/img.jpg', nsfw: false }],
                },
              ],
            },
          ],
          next_cursor: 'xyz',
        }),
    })

    const result = await adapter.search({ query: 'test' })

    expect(result.items).toHaveLength(1)
    expect(result.items[0].id).toBe(123)
    expect(result.items[0].name).toBe('Test Model')
    expect(result.nextCursor).toBe('xyz')
    expect(result.metadata?.source).toBe('rest')
  })

  it('should handle API errors', async () => {
    const { RestSearchAdapter } = await import('@/lib/api/adapters/restAdapter')
    const adapter = new RestSearchAdapter()

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    })

    await expect(adapter.search({ query: 'test' })).rejects.toThrow()
  })
})

// =============================================================================
// Archive Adapter Tests
// =============================================================================

describe('ArchiveSearchAdapter', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('should have correct metadata', async () => {
    const { ArchiveSearchAdapter } = await import('@/lib/api/adapters/archiveAdapter')
    const adapter = new ArchiveSearchAdapter()

    expect(adapter.provider).toBe('archive')
    expect(adapter.displayName).toBe('CivArchive')
    expect(adapter.description).toContain('description')
  })

  it('should always be available', async () => {
    const { ArchiveSearchAdapter } = await import('@/lib/api/adapters/archiveAdapter')
    const adapter = new ArchiveSearchAdapter()

    expect(adapter.isAvailable()).toBe(true)
  })

  it('should call archive endpoint with pagination', async () => {
    const { ArchiveSearchAdapter } = await import('@/lib/api/adapters/archiveAdapter')
    const adapter = new ArchiveSearchAdapter()

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          results: [],
          has_more: true,
        }),
    })

    await adapter.search({
      query: 'test',
      limit: 20,
    })

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const callUrl = mockFetch.mock.calls[0][0] as string
    expect(callUrl).toContain('/api/browse/search-civarchive')
    expect(callUrl).toContain('query=test')
    expect(callUrl).toContain('page=1')
  })

  it('should map has_more to hasMore in result', async () => {
    const { ArchiveSearchAdapter } = await import('@/lib/api/adapters/archiveAdapter')
    const adapter = new ArchiveSearchAdapter()

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          results: [],
          has_more: true,
        }),
    })

    const result = await adapter.search({ query: 'test' })

    expect(result.hasMore).toBe(true)
    expect(result.metadata?.source).toBe('archive')
  })
})

// =============================================================================
// tRPC Bridge Adapter Tests
// =============================================================================

describe('TrpcBridgeAdapter', () => {
  const mockBridge = {
    isEnabled: vi.fn(),
    search: vi.fn(),
    getModel: vi.fn(),
    getStatus: vi.fn(),
  }

  beforeEach(() => {
    vi.resetModules()
    mockFetch.mockReset()
    mockBridge.isEnabled.mockReset()
    mockBridge.search.mockReset()
    mockBridge.getModel.mockReset()
    mockBridge.getStatus.mockReset()

    // Setup window.SynapseSearchBridge
    ;(globalThis as unknown as Record<string, unknown>).SynapseSearchBridge = mockBridge
  })

  afterEach(() => {
    delete (globalThis as unknown as Record<string, unknown>).SynapseSearchBridge
  })

  it('should have correct metadata', async () => {
    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    expect(adapter.provider).toBe('trpc')
    expect(adapter.displayName).toBe('Internal tRPC')
    expect(adapter.description).toContain('browser extension')
  })

  it('should be available when bridge exists and is enabled', async () => {
    mockBridge.isEnabled.mockReturnValue(true)

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    expect(adapter.isAvailable()).toBe(true)
  })

  it('should not be available when bridge is missing', async () => {
    delete (globalThis as unknown as Record<string, unknown>).SynapseSearchBridge

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    expect(adapter.isAvailable()).toBe(false)
  })

  it('should not be available when bridge is disabled', async () => {
    mockBridge.isEnabled.mockReturnValue(false)

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    expect(adapter.isAvailable()).toBe(false)
  })

  it('should call bridge.search with transformed params', async () => {
    mockBridge.isEnabled.mockReturnValue(true)
    mockBridge.search.mockResolvedValue({
      ok: true,
      data: {
        items: [
          {
            id: 123,
            name: 'Test',
            type: 'LORA',
            modelVersions: [{ id: 1, images: [] }],
          },
        ],
        nextCursor: 'cursor123',
      },
      meta: { cached: false, durationMs: 100 },
    })

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    const result = await adapter.search({
      query: 'test',
      sort: 'Most Downloaded',
      period: 'Month',
      limit: 20,
    })

    expect(mockBridge.search).toHaveBeenCalledWith(
      expect.objectContaining({
        q: 'test',
        sort: 'Most Downloaded',
        period: 'Month',
        limit: 20,
      }),
      expect.any(Object)
    )

    expect(result.items).toHaveLength(1)
    expect(result.nextCursor).toBe('cursor123')
    expect(result.metadata?.source).toBe('trpc')
    expect(result.metadata?.responseTime).toBe(100)
  })

  it('should handle bridge errors', async () => {
    mockBridge.isEnabled.mockReturnValue(true)
    mockBridge.search.mockResolvedValue({
      ok: false,
      error: {
        code: 'NETWORK',
        message: 'Connection failed',
      },
    })

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await expect(adapter.search({ query: 'test' })).rejects.toThrow('Connection failed')
  })

  it('should throw when bridge is unavailable during search', async () => {
    delete (globalThis as unknown as Record<string, unknown>).SynapseSearchBridge

    const { TrpcBridgeAdapter } = await import('@/lib/api/adapters/trpcBridgeAdapter')
    const adapter = new TrpcBridgeAdapter()

    await expect(adapter.search({ query: 'test' })).rejects.toThrow('not available')
  })
})

// =============================================================================
// Adapter Registry Tests
// =============================================================================

describe('Search Adapter Registry', () => {
  beforeEach(() => {
    vi.resetModules()
    mockFetch.mockReset()
  })

  it('should return adapter by provider name', async () => {
    const { getAdapter } = await import('@/lib/api/searchAdapters')

    const restAdapter = getAdapter('rest')
    expect(restAdapter.provider).toBe('rest')

    const archiveAdapter = getAdapter('archive')
    expect(archiveAdapter.provider).toBe('archive')

    const trpcAdapter = getAdapter('trpc')
    expect(trpcAdapter.provider).toBe('trpc')
  })

  it('should return all adapters', async () => {
    const { getAllAdapters } = await import('@/lib/api/searchAdapters')

    const adapters = getAllAdapters()
    expect(adapters).toHaveLength(3)

    const providers = adapters.map((a) => a.provider)
    expect(providers).toContain('rest')
    expect(providers).toContain('archive')
    expect(providers).toContain('trpc')
  })

  it('should check provider availability', async () => {
    const { isProviderAvailable } = await import('@/lib/api/searchAdapters')

    // REST and Archive should always be available
    expect(isProviderAvailable('rest')).toBe(true)
    expect(isProviderAvailable('archive')).toBe(true)

    // tRPC depends on bridge (not available in test env by default)
    expect(isProviderAvailable('trpc')).toBe(false)
  })

  it('should return default provider', async () => {
    const { getDefaultProvider } = await import('@/lib/api/searchAdapters')

    // Without bridge, should default to REST
    const defaultProvider = getDefaultProvider()
    expect(defaultProvider).toBe('rest')
  })

  it('should handle provider fallback', async () => {
    const { getProviderWithFallback } = await import('@/lib/api/searchAdapters')

    // REST should return REST
    expect(getProviderWithFallback('rest')).toBe('rest')

    // Archive should return archive
    expect(getProviderWithFallback('archive')).toBe('archive')

    // tRPC should fallback to REST when unavailable
    expect(getProviderWithFallback('trpc')).toBe('rest')
  })
})
