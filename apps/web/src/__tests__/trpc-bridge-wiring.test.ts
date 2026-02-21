/**
 * Tests for tRPC Bridge Adapter model detail (REST path).
 *
 * getModelDetail uses REST because bridge's getModelImages (image.getInfinite)
 * hangs indefinitely in some environments.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'

describe('TrpcBridgeAdapter.getModelDetail', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should fetch model detail via REST', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          id: 123,
          name: 'Test Model',
          type: 'LORA',
          previews: [{ url: '/img.jpg', type: 'image' }],
          versions: [],
        }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const { TrpcBridgeAdapter } = await import(
      '@/lib/api/adapters/trpcBridgeAdapter'
    )
    const adapter = new TrpcBridgeAdapter()
    const result = await adapter.getModelDetail(123)

    expect(mockFetch).toHaveBeenCalledWith('/api/browse/model/123')
    expect(result.id).toBe(123)
    expect(result.name).toBe('Test Model')
    expect(result.previews.length).toBe(1)
  })

  it('should throw on HTTP error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 404 })
    )

    const { TrpcBridgeAdapter } = await import(
      '@/lib/api/adapters/trpcBridgeAdapter'
    )
    const adapter = new TrpcBridgeAdapter()

    await expect(adapter.getModelDetail(999)).rejects.toThrow(
      'Failed to fetch model'
    )
  })
})
