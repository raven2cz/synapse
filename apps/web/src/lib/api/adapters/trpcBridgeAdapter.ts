/**
 * tRPC Bridge Search Adapter
 *
 * Uses Tampermonkey bridge to call Civitai's internal tRPC API directly.
 * Bypasses CORS via GM_xmlhttpRequest.
 *
 * Requires: Synapse Civitai Bridge userscript installed in Tampermonkey.
 */

import type {
  SearchAdapter,
  SearchParams,
  SearchResult,
  ModelDetail,
} from '../searchTypes'
import {
  transformTrpcModel,
  transformTrpcModelDetail,
} from '@/lib/utils/civitaiTransformers'

// =============================================================================
// Bridge Type Declaration
// =============================================================================

interface BridgeSearchResult {
  ok: boolean
  data?: {
    items?: Record<string, unknown>[]
    nextCursor?: string
  }
  error?: {
    code: string
    message: string
  }
  meta?: {
    durationMs: number
    cached: boolean
  }
}

interface BridgeModelResult {
  ok: boolean
  data?: Record<string, unknown>
  error?: {
    code: string
    message: string
  }
}

interface SynapseSearchBridge {
  version: string
  isEnabled(): boolean
  getStatus(): { enabled: boolean; nsfw: boolean; version: string }
  configure?(updates: { enabled?: boolean; nsfw?: boolean }): void
  search(
    request: {
      q?: string
      limit?: number
      sort?: string
      period?: string
      cursor?: string
      filters?: {
        types?: string
        baseModel?: string
      }
    },
    opts?: { signal?: AbortSignal; noCache?: boolean }
  ): Promise<BridgeSearchResult>
  getModel?(
    modelId: number,
    opts?: { signal?: AbortSignal }
  ): Promise<BridgeModelResult>
  test?(): Promise<BridgeSearchResult>
}

declare global {
  interface Window {
    SynapseSearchBridge?: SynapseSearchBridge
  }
}

// =============================================================================
// tRPC Bridge Adapter
// =============================================================================

export class TrpcBridgeAdapter implements SearchAdapter {
  readonly provider = 'trpc' as const
  readonly displayName = 'Internal tRPC'
  readonly description = 'Fast, direct API via browser extension'
  readonly icon = 'Zap'

  isAvailable(): boolean {
    if (typeof window === 'undefined') return false
    return !!window.SynapseSearchBridge?.isEnabled?.()
  }

  async search(
    params: SearchParams,
    signal?: AbortSignal
  ): Promise<SearchResult> {
    const bridge = window.SynapseSearchBridge

    if (!bridge) {
      throw new Error('Bridge not available. Install Tampermonkey extension.')
    }

    const startTime = Date.now()

    const result = await bridge.search(
      {
        q: params.query || '',
        limit: params.limit || 20,
        sort: params.sort || 'Most Downloaded',
        period: params.period || 'AllTime',
        cursor: params.cursor,
        filters: {
          types: params.types?.[0],
          baseModel: params.baseModels?.[0],
        },
      },
      { signal }
    )

    if (!result.ok) {
      throw new Error(result.error?.message || 'Search failed')
    }

    // Transform with video detection
    const rawItems = result.data?.items || []
    const items = rawItems.map((item) => transformTrpcModel(item))

    return {
      items,
      nextCursor: result.data?.nextCursor,
      hasMore: !!result.data?.nextCursor,
      metadata: {
        source: 'trpc',
        cached: result.meta?.cached || false,
        responseTime: result.meta?.durationMs || Date.now() - startTime,
      },
    }
  }

  async getModelDetail(modelId: number): Promise<ModelDetail> {
    const bridge = window.SynapseSearchBridge

    // If bridge doesn't support getModel, fallback to REST
    if (!bridge?.getModel) {
      const res = await fetch(`/api/browse/model/${modelId}`)
      if (!res.ok) throw new Error('Failed to fetch model')
      return res.json()
    }

    const result = await bridge.getModel(modelId)

    if (!result.ok) {
      throw new Error(result.error?.message || 'Failed to fetch model')
    }

    // Transform tRPC model detail response
    return transformTrpcModelDetail(result.data!)
  }
}
