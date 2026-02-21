/**
 * tRPC Bridge Search Adapter
 *
 * Uses Tampermonkey bridge with HYBRID search strategy:
 * - Meilisearch for full-text search (fast, when query provided)
 * - tRPC model.getAll for browse without query (better sorting)
 *
 * Bypasses CORS via GM_xmlhttpRequest.
 *
 * Requires: Synapse Civitai Bridge v10+ userscript installed in Tampermonkey.
 */

import type {
  SearchAdapter,
  SearchParams,
  SearchResult,
  ModelDetail,
  ModelPreview,
} from '../searchTypes'
import { transformTrpcModel, transformMeilisearchModel, transformTrpcModelDetail, transformPreview } from '@/lib/utils/civitaiTransformers'

// Timeout for image.getInfinite which is inherently slow
const IMAGE_FETCH_TIMEOUT = 60000

// =============================================================================
// Bridge Type Declaration
// =============================================================================

interface BridgeSearchResult {
  ok: boolean
  data?: {
    items?: Record<string, unknown>[]
    nextCursor?: string
    hasMore?: boolean
    totalHits?: number
  }
  error?: {
    code: string
    message: string
  }
  meta?: {
    durationMs: number
    cached: boolean
    source: 'meilisearch' | 'trpc'
    query?: string
  }
}

interface SynapseSearchBridge {
  version: string
  isEnabled(): boolean
  getStatus(): {
    enabled: boolean
    nsfw: boolean
    version: string
    cacheSize: number
    features?: string[]
  }
  configure?(updates: { enabled?: boolean; nsfw?: boolean }): void
  // Hybrid search (auto-selects Meilisearch or tRPC)
  search(
    request: {
      q?: string
      limit?: number
      sort?: string
      period?: string
      cursor?: string
      offset?: number
      filters?: {
        types?: string | string[]
        baseModel?: string | string[]
      }
    },
    opts?: { signal?: AbortSignal; noCache?: boolean; forceTrpc?: boolean }
  ): Promise<BridgeSearchResult>
  // Direct Meilisearch search
  searchMeilisearch?(
    request: {
      q?: string
      limit?: number
      offset?: number
      filters?: {
        types?: string | string[]
        baseModel?: string | string[]
      }
    },
    opts?: { signal?: AbortSignal; noCache?: boolean }
  ): Promise<BridgeSearchResult>
  // Direct tRPC search
  searchTrpc?(
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
  getModel?(modelId: number, opts?: Record<string, unknown>): Promise<BridgeSearchResult>
  getModelImages?(modelId: number, opts?: Record<string, unknown>): Promise<BridgeSearchResult>
  test?(): Promise<{ ok: boolean; results: { meilisearch: unknown; trpc: unknown } }>
}

declare global {
  interface Window {
    SynapseSearchBridge?: SynapseSearchBridge
  }
}

// =============================================================================
// tRPC Bridge Adapter (Hybrid: Meilisearch + tRPC)
// =============================================================================

export class TrpcBridgeAdapter implements SearchAdapter {
  readonly provider = 'trpc' as const
  readonly displayName = 'Internal tRPC'
  readonly description = 'Fast, direct API via browser extension'
  readonly icon = 'Zap'

  // Track current offset for Meilisearch pagination
  private meilisearchOffset = 0

  isAvailable(): boolean {
    if (typeof window === 'undefined') return false
    return !!window.SynapseSearchBridge?.isEnabled?.()
  }

  /**
   * Get bridge version info
   */
  getVersion(): string {
    return window.SynapseSearchBridge?.version || 'unknown'
  }

  /**
   * Check if bridge supports Meilisearch (v10+)
   */
  supportsMeilisearch(): boolean {
    const status = window.SynapseSearchBridge?.getStatus?.()
    return status?.features?.includes('meilisearch') ?? false
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

    // Reset offset on new search (no cursor = new search)
    if (!params.cursor) {
      this.meilisearchOffset = 0
    }

    const result = await bridge.search(
      {
        q: params.query || '',
        limit: params.limit || 20,
        sort: params.sort || 'Most Downloaded',
        period: params.period || 'AllTime',
        cursor: params.cursor,
        offset: this.meilisearchOffset,
        filters: {
          // Support multiple types
          types: params.types?.length ? params.types : undefined,
          baseModel: params.baseModels?.length ? params.baseModels[0] : undefined,
        },
      },
      { signal }
    )

    if (!result.ok) {
      throw new Error(result.error?.message || 'Search failed')
    }

    // Determine which transformer to use based on source
    const isMeilisearch = result.meta?.source === 'meilisearch'
    const rawItems = result.data?.items || []

    // Transform items based on source
    const items = rawItems.map((item) =>
      isMeilisearch ? transformMeilisearchModel(item) : transformTrpcModel(item)
    )

    // Update offset for next Meilisearch request
    if (isMeilisearch && result.data?.hasMore) {
      this.meilisearchOffset += items.length
    }

    // For Meilisearch, we use offset-based pagination
    // For tRPC, we use cursor-based pagination
    const nextCursor = isMeilisearch
      ? result.data?.hasMore
        ? String(this.meilisearchOffset)
        : undefined
      : result.data?.nextCursor

    return {
      items,
      nextCursor,
      hasMore: result.data?.hasMore ?? !!nextCursor,
      metadata: {
        source: 'trpc',
        cached: result.meta?.cached || false,
        responseTime: result.meta?.durationMs || Date.now() - startTime,
        totalItems: result.data?.totalHits,
      },
    }
  }

  /**
   * Get model info FAST (no image fetching).
   *
   * For tRPC: calls bridge.getModel() which returns in ~1s (model data only, images empty).
   * For REST fallback: calls /api/browse/model/{id} which includes images.
   *
   * Images are loaded separately via getModelPreviews() for progressive loading.
   */
  async getModelDetail(modelId: number): Promise<ModelDetail> {
    const bridge = window.SynapseSearchBridge

    // Use bridge's direct tRPC call if available (fast — model data only, no images)
    if (bridge?.getModel) {
      try {
        const modelResult = await bridge.getModel(modelId)
        if (modelResult.ok) {
          return transformTrpcModelDetail(modelResult.data as Record<string, unknown>)
        }
        throw new Error(modelResult.error?.message || 'Model fetch failed')
      } catch (err) {
        console.warn('[Synapse] Bridge model fetch failed, using REST fallback:', err)
      }
    }

    // Fallback to REST (includes images — no need for separate getModelPreviews)
    const res = await fetch(`/api/browse/model/${modelId}`)
    if (!res.ok) {
      throw new Error('Failed to fetch model')
    }
    return res.json()
  }

  /**
   * Fetch preview images separately via bridge (progressive loading).
   *
   * Called by BrowsePage as Query 2, only when getModelDetail returned 0 previews.
   * Uses image.getInfinite which requires modelVersionId (NOT modelId!).
   * 15s timeout protects against Civitai hangs.
   */
  async getModelPreviews(modelId: number, versionId: number): Promise<ModelPreview[]> {
    const bridge = window.SynapseSearchBridge
    if (!bridge?.getModelImages) {
      throw new Error('Bridge getModelImages not available')
    }

    const result = await Promise.race([
      bridge.getModelImages(versionId, { limit: 50, timeout: IMAGE_FETCH_TIMEOUT }),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('getModelImages timeout')), 15_000)
      ),
    ])

    if (!result.ok) {
      throw new Error(result.error?.message || 'Image fetch failed')
    }

    return (result.data?.items || []).map((item) =>
      transformPreview(item as Record<string, unknown>)
    )
  }
}
