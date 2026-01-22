/**
 * CivArchive Search Adapter
 *
 * Searches via CivArchive.com for better full-text search.
 * Can find deleted models and searches descriptions.
 *
 * Phase 5: Now supports pagination with page parameter.
 */

import type {
  SearchAdapter,
  SearchParams,
  SearchResult,
  CivitaiModel,
} from '../searchTypes'

export class ArchiveSearchAdapter implements SearchAdapter {
  readonly provider = 'archive' as const
  readonly displayName = 'CivArchive'
  readonly description = 'Searches descriptions, finds deleted models'
  readonly icon = 'Archive'

  private currentPage = 1

  isAvailable(): boolean {
    return true // Always available via backend
  }

  async search(params: SearchParams, signal?: AbortSignal): Promise<SearchResult> {
    if (!params.query) {
      return {
        items: [],
        hasMore: false,
        metadata: { source: 'archive' },
      }
    }

    // Reset page on new search (no cursor = new search)
    if (!params.cursor) {
      this.currentPage = 1
    }

    const urlParams = new URLSearchParams()
    urlParams.append('query', params.query)
    urlParams.append('limit', String(params.limit || 20))
    // One page per request - user clicks "Load More" for next page
    urlParams.append('page', String(this.currentPage))

    const startTime = Date.now()

    const res = await fetch(`/api/browse/search-civarchive?${urlParams}`, {
      signal,
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'CivArchive search failed')
    }

    const data = await res.json()

    // Transform CivArchiveResult → CivitaiModel
    const items: CivitaiModel[] = (data.results || []).map(
      (r: Record<string, unknown>) => ({
        id: r.model_id as number,
        name: (r.model_name as string) || '',
        type: (r.model_type as string) || 'Unknown',
        nsfw: (r.nsfw as boolean) || false,
        tags: [],
        creator: r.creator as string | undefined,
        stats: {
          downloadCount: r.download_count as number | undefined,
          rating: r.rating as number | undefined,
        },
        versions: [
          {
            id: r.version_id as number,
            name: (r.version_name as string) || 'Default',
            base_model: r.base_model as string | undefined,
            download_url: r.download_url as string | undefined,
            file_size: r.file_size as number | undefined,
            trained_words: [],
            files: r.file_name
              ? [
                  {
                    id: 0,
                    name: r.file_name as string,
                    size_kb: r.file_size
                      ? (r.file_size as number) / 1024
                      : undefined,
                    download_url: r.download_url as string | undefined,
                  },
                ]
              : [],
          },
        ],
        // Backend already transforms previews with video detection
        previews: (r.previews as CivitaiModel['previews']) || [],
      })
    )

    // Phase 5: Increment page for next Load More
    if (data.has_more) {
      this.currentPage++
    }

    return {
      items,
      hasMore: data.has_more || false,
      nextCursor: data.has_more ? String(this.currentPage) : undefined,
      metadata: {
        source: 'archive',
        totalItems: data.total_found as number,
        responseTime: Date.now() - startTime,
      },
    }
  }

  // CivArchive doesn't support direct model fetch - would need to go through REST
}
