/**
 * REST API Search Adapter
 *
 * Uses the existing backend /api/browse endpoints.
 * Always available, stable and reliable.
 *
 * REST backend returns raw Civitai CDN URLs which need proxying
 * (Civitai CDN blocks direct browser requests without proper Referer).
 */

import type {
  SearchAdapter,
  SearchParams,
  SearchResult,
  ModelDetail,
  CivitaiModel,
} from '../searchTypes'
import { toProxyUrl } from '@/lib/utils/civitaiTransformers'

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
    const items = (data.items || []).map(proxyModelUrls)

    return {
      items,
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

    const data: ModelDetail = await res.json()
    return proxyModelUrls(data)
  }
}

/**
 * Proxy all Civitai CDN URLs in a model's previews.
 * REST backend returns raw CDN URLs which browsers can't load
 * (Civitai CDN requires proper Referer header).
 */
function proxyModelUrls<T extends CivitaiModel>(model: T): T {
  if (!model.previews?.length) return model
  return {
    ...model,
    previews: model.previews.map((p) => ({
      ...p,
      url: toProxyUrl(p.url),
      thumbnail_url: p.thumbnail_url ? toProxyUrl(p.thumbnail_url) : p.thumbnail_url,
    })),
  }
}
