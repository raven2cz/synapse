/**
 * REST API Search Adapter
 *
 * Uses the existing backend /api/browse endpoints.
 * Always available, stable and reliable.
 */

import type {
  SearchAdapter,
  SearchParams,
  SearchResult,
  ModelDetail,
} from '../searchTypes'

export class RestSearchAdapter implements SearchAdapter {
  readonly provider = 'rest' as const
  readonly displayName = 'REST API'
  readonly description = 'Standard API, stable and reliable'
  readonly icon = 'Globe'

  isAvailable(): boolean {
    return true // Always available
  }

  async search(params: SearchParams, signal?: AbortSignal): Promise<SearchResult> {
    const urlParams = new URLSearchParams()

    if (params.query) urlParams.append('query', params.query)
    if (params.types?.length) urlParams.append('types', params.types.join(','))
    if (params.sort) urlParams.append('sort', params.sort)
    if (params.nsfw !== undefined) urlParams.append('nsfw', String(params.nsfw))
    if (params.cursor) urlParams.append('cursor', params.cursor)
    urlParams.append('limit', String(params.limit || 20))

    const startTime = Date.now()

    const res = await fetch(`/api/browse/search?${urlParams}`, { signal })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Search failed')
    }

    const data = await res.json()

    return {
      items: data.items || [],
      nextCursor: data.next_cursor,
      hasMore: !!data.next_cursor,
      metadata: {
        source: 'rest',
        totalItems: data.total,
        responseTime: Date.now() - startTime,
      },
    }
  }

  async getModelDetail(modelId: number): Promise<ModelDetail> {
    const res = await fetch(`/api/browse/model/${modelId}`)

    if (!res.ok) {
      throw new Error('Failed to fetch model')
    }

    return res.json()
  }
}
