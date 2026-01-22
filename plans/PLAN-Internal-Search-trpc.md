# 🔍 Phase 5: Internal Civitai Search (tRPC)

**Branch:** `feature/internal-search-trpc`
**Verze:** v2.7.0
**Datum zahájení:** 2026-01-22
**Status:** ✅ DOKONČENO - Všechny subfáze kompletní

---

## 📊 Přehled

### Motivace
Aktuálně BrowsePage volá Civitai API přímo z frontendu nebo přes backend proxy. To má několik nevýhod:
1. **CORS problémy** - některé endpointy vyžadují proxy
2. **Rate limiting** - Civitai může omezit požadavky z různých IP
3. **API klíč exposure** - klíč musí být ve frontendu nebo backendu
4. **Nedostatečná kontrola** - nemůžeme cachovat ani transformovat odpovědi
5. **CivArchive limit** - aktuálně pouze 3 stránky (hardcoded `pages_to_fetch = [1, 2, 3]`)
6. **Chybějící filtry** - Sort, Period, BaseModel nejsou dostupné v UI

### Cíle
1. **Unified Search Adapters** - 3 zdroje dat za jednotným rozhraním
2. **Tampermonkey tRPC Bridge** - Přímé volání Civitai tRPC API z browseru
3. **CivArchive vylepšení** - Podpora více stránek s Load More
4. **Nové filtry** - Sort, Period, BaseModel dropdowny
5. **Zachování NSFW** - Stávající blur systém musí fungovat perfektně!
6. **Kvalitní UI** - Moderní filtry s animacemi

---

## 🚨 KRITICKÉ - CO SE NESMÍ ROZBÍT

### Video Support (Phase 4)
- ❌ NEDOTÝKAT SE: `MediaPreview` komponenty (BrowsePage lines 607-615, 741-751)
- ❌ NEDOTÝKAT SE: `FullscreenMediaViewer` (lines 404-421)
- ❌ NEDOTÝKAT SE: Video autoPlay, thumbnail_url, media_type handling
- ✅ Transformer MUSÍ správně detekovat video a generovat thumbnail_url

### NSFW Systém
- ❌ NEDOTÝKAT SE: `useSettingsStore.nsfwBlurEnabled` (stores/settingsStore.ts)
- ❌ NEDOTÝKAT SE: Header NSFW toggle (components/layout/Header.tsx)
- ❌ NEDOTÝKAT SE: `getPreviewNsfw()` helper (BrowsePage line 371)
- ✅ Všechny adaptery MUSÍ správně předávat `nsfw` flag na preview i model úrovni

### Zobrazení (BrowsePage.tsx - 942 řádků)
- ❌ NEDOTÝKAT SE: Karty grid (lines 593-651)
- ❌ NEDOTÝKAT SE: Model detail modal (lines 681-938)
- ❌ NEDOTÝKAT SE: ImportWizardModal (lines 423-484)
- ❌ NEDOTÝKAT SE: Toast systém (lines 375-403)
- ❌ NEDOTÝKAT SE: Pagination useEffect (lines 261-275)

---

## 📁 Struktura změn

```
synapse/
├── apps/
│   ├── api/src/routers/
│   │   └── browse.py                    # UPRAVIT - CivArchive pagination
│   └── web/src/
│       ├── lib/
│       │   ├── api/
│       │   │   ├── searchTypes.ts       # NOVÉ - TypeScript typy
│       │   │   ├── searchAdapters.ts    # NOVÉ - Adapter registry
│       │   │   └── adapters/
│       │   │       ├── restAdapter.ts   # NOVÉ - REST API adapter
│       │   │       ├── archiveAdapter.ts# NOVÉ - CivArchive adapter
│       │   │       └── trpcBridgeAdapter.ts # NOVÉ - tRPC bridge
│       │   └── utils/
│       │       └── civitaiTransformers.ts # NOVÉ - Data transformers
│       ├── components/
│       │   └── modules/
│       │       └── BrowsePage.tsx       # UPRAVIT - Nové filtry, adapter volání
│       └── __tests__/
│           ├── search-adapters.test.ts  # NOVÉ
│           ├── trpc-transformer.test.ts # NOVÉ
│           └── browse-filters.test.ts   # NOVÉ
├── scripts/
│   └── tampermonkey/
│       └── synapse-civitai-bridge.user.js # NOVÉ - Finální skript
└── tests/
    └── unit/
        └── test_civarchive_pagination.py # NOVÉ
```

---

## 🔧 Subfáze 5.1: CivArchive Pagination Fix

### 5.1.1 Backend - Vylepšit CivArchive pagination

**Status:** ✅ DONE (2026-01-22)
**Implementováno v:** `apps/api/src/routers/browse.py`

**Soubor:** `apps/api/src/routers/browse.py`

**Problém (line 1113):**
```python
# HARDCODED pouze 3 stránky!
pages_to_fetch = [1, 2, 3]
```

**Řešení - Přidat pagination parametry:**

```python
class CivArchiveSearchResponse(BaseModel):
    """Response from CivArchive search."""
    model_config = ConfigDict(protected_namespaces=())

    results: List[CivArchiveResult]
    total_found: int
    query: str
    has_more: bool = False          # NOVÉ - indikace dalších výsledků
    current_page: int = 1           # NOVÉ - aktuální stránka


@router.get("/search-civarchive", response_model=CivArchiveSearchResponse)
async def search_via_civarchive(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=30, description="Max results"),
    page: int = Query(1, ge=1, le=20, description="Page number"),  # NOVÉ
    pages_per_request: int = Query(3, ge=1, le=5, description="CivArchive pages to fetch"),  # NOVÉ
):
    """Search models via CivArchive.com with pagination support."""

    # Calculate which CivArchive pages to fetch
    start_page = (page - 1) * pages_per_request + 1
    pages_to_fetch = list(range(start_page, start_page + pages_per_request))

    # ... rest of existing implementation ...

    # Determine if there are more results
    has_more = len(all_links) > len(unique_items)

    return CivArchiveSearchResponse(
        results=results,
        total_found=len(results),
        query=query,
        has_more=has_more,
        current_page=page,
    )
```

### 5.1.2 Test pro CivArchive pagination

**Status:** ✅ DONE (2026-01-22)
**Implementováno v:** `tests/unit/test_civarchive_pagination.py`
**Výsledek:** 10 passed, 1 skipped

**Soubor:** `tests/unit/test_civarchive_pagination.py`

```python
"""Tests for CivArchive pagination support."""

import pytest


class TestCivArchivePagination:
    """Tests for CivArchive search pagination."""

    def test_page_1_fetches_civarchive_pages_1_to_3(self):
        """Page 1 should fetch CivArchive pages 1, 2, 3."""
        # Given page=1, pages_per_request=3
        # Expected: pages_to_fetch = [1, 2, 3]
        pass

    def test_page_2_fetches_civarchive_pages_4_to_6(self):
        """Page 2 should fetch CivArchive pages 4, 5, 6."""
        # Given page=2, pages_per_request=3
        # Expected: pages_to_fetch = [4, 5, 6]
        pass

    def test_has_more_true_when_more_links_available(self):
        """has_more should be True when more results exist."""
        pass

    def test_has_more_false_on_last_page(self):
        """has_more should be False when no more results."""
        pass

    def test_response_includes_current_page(self):
        """Response should include current_page field."""
        pass
```

---

## 🔧 Subfáze 5.2: Frontend Search Adapters

### 5.2.1 TypeScript typy

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/api/searchTypes.ts`

```typescript
// Search provider types
export type SearchProvider = 'rest' | 'archive' | 'trpc'

// Sort options (match Civitai exactly)
export type SortOption =
  | 'Most Downloaded'
  | 'Highest Rated'
  | 'Newest'
  | 'Most Discussed'
  | 'Most Collected'
  | 'Most Buzz'

// Period options
export type PeriodOption =
  | 'AllTime'
  | 'Year'
  | 'Month'
  | 'Week'
  | 'Day'

// Base model options (common ones)
export const BASE_MODEL_OPTIONS = [
  { value: '', label: 'All Base Models' },
  { value: 'SDXL 1.0', label: 'SDXL 1.0' },
  { value: 'SD 1.5', label: 'SD 1.5' },
  { value: 'Pony', label: 'Pony' },
  { value: 'Flux.1 D', label: 'Flux.1 Dev' },
  { value: 'Flux.1 S', label: 'Flux.1 Schnell' },
  { value: 'Illustrious', label: 'Illustrious' },
  { value: 'SD 3', label: 'SD 3' },
  { value: 'SD 3.5', label: 'SD 3.5' },
] as const

export const SORT_OPTIONS = [
  { value: 'Most Downloaded', label: 'Most Downloaded' },
  { value: 'Highest Rated', label: 'Highest Rated' },
  { value: 'Newest', label: 'Newest' },
  { value: 'Most Discussed', label: 'Most Discussed' },
  { value: 'Most Collected', label: 'Most Collected' },
] as const

export const PERIOD_OPTIONS = [
  { value: 'AllTime', label: 'All Time' },
  { value: 'Year', label: 'This Year' },
  { value: 'Month', label: 'This Month' },
  { value: 'Week', label: 'This Week' },
  { value: 'Day', label: 'Today' },
] as const

// Search parameters
export interface SearchParams {
  query?: string
  types?: string[]
  baseModels?: string[]
  sort?: SortOption
  period?: PeriodOption
  nsfw?: boolean
  limit?: number
  cursor?: string
  // CivArchive specific
  page?: number
}

// Unified search result
export interface SearchResult {
  items: CivitaiModel[]
  nextCursor?: string
  hasMore?: boolean
  metadata?: {
    totalItems?: number
    cached?: boolean
    source: SearchProvider
    responseTime?: number
  }
}

// Adapter interface
export interface SearchAdapter {
  readonly provider: SearchProvider
  readonly displayName: string
  readonly description: string
  readonly icon: string  // Lucide icon name

  isAvailable(): boolean
  search(params: SearchParams, signal?: AbortSignal): Promise<SearchResult>
  getModelDetail?(modelId: number): Promise<ModelDetail>
}

// Re-export existing types from BrowsePage for consistency
export type { CivitaiModel, ModelDetail, ModelPreview, ModelVersion } from './browseTypes'
```

### 5.2.2 REST Adapter

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/api/adapters/restAdapter.ts`

```typescript
import type { SearchAdapter, SearchParams, SearchResult, ModelDetail } from '../searchTypes'

export class RestSearchAdapter implements SearchAdapter {
  readonly provider = 'rest' as const
  readonly displayName = 'Civitai REST API'
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
      }
    }
  }

  async getModelDetail(modelId: number): Promise<ModelDetail> {
    const res = await fetch(`/api/browse/model/${modelId}`)
    if (!res.ok) throw new Error('Failed to fetch model')
    return res.json()
  }
}
```

### 5.2.3 Archive Adapter (s pagination)

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/api/adapters/archiveAdapter.ts`

```typescript
import type { SearchAdapter, SearchParams, SearchResult, CivitaiModel } from '../searchTypes'

export class ArchiveSearchAdapter implements SearchAdapter {
  readonly provider = 'archive' as const
  readonly displayName = 'CivArchive'
  readonly description = 'Searches descriptions, finds deleted models'
  readonly icon = 'Archive'

  private currentPage = 1

  isAvailable(): boolean {
    return true
  }

  async search(params: SearchParams, signal?: AbortSignal): Promise<SearchResult> {
    if (!params.query) {
      return { items: [], hasMore: false, metadata: { source: 'archive' } }
    }

    // Reset page on new search (no cursor = new search)
    if (!params.cursor) {
      this.currentPage = 1
    }

    const urlParams = new URLSearchParams()
    urlParams.append('query', params.query)
    urlParams.append('limit', String(params.limit || 20))
    urlParams.append('page', String(this.currentPage))

    const startTime = Date.now()

    const res = await fetch(`/api/browse/search-civarchive?${urlParams}`, { signal })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'CivArchive search failed')
    }

    const data = await res.json()

    // Transform CivArchiveResult → CivitaiModel
    // (Same transformation as currently in BrowsePage queryFn)
    const items: CivitaiModel[] = (data.results || []).map((r: any) => ({
      id: r.model_id,
      name: r.model_name,
      type: r.model_type || 'Unknown',
      nsfw: r.nsfw || false,
      tags: [],
      creator: r.creator,
      stats: {
        downloadCount: r.download_count,
        rating: r.rating,
      },
      versions: [{
        id: r.version_id,
        name: r.version_name || 'Default',
        base_model: r.base_model,
        download_url: r.download_url,
        file_size: r.file_size,
        trained_words: [],
        files: r.file_name ? [{
          id: 0,
          name: r.file_name,
          size_kb: r.file_size ? r.file_size / 1024 : undefined,
          download_url: r.download_url,
        }] : [],
      }],
      // Backend already transforms previews with video detection
      previews: r.previews || [],
    }))

    // Increment page for next Load More
    if (data.has_more) {
      this.currentPage++
    }

    return {
      items,
      hasMore: data.has_more || false,
      nextCursor: data.has_more ? String(this.currentPage) : undefined,
      metadata: {
        source: 'archive',
        totalItems: data.total_found,
        responseTime: Date.now() - startTime,
      }
    }
  }
}
```

### 5.2.4 tRPC Bridge Adapter

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts`

```typescript
import type { SearchAdapter, SearchParams, SearchResult, ModelDetail } from '../searchTypes'
import { transformTrpcModel } from '../../utils/civitaiTransformers'

// Bridge type declaration
declare global {
  interface Window {
    SynapseSearchBridge?: {
      version: string
      isEnabled(): boolean
      getStatus(): { enabled: boolean; nsfw: boolean; version: string }
      search(request: any, opts?: any): Promise<{
        ok: boolean
        data?: any
        error?: { code: string; message: string }
        meta?: { durationMs: number; cached: boolean }
      }>
      getModel?(modelId: number, opts?: any): Promise<any>
    }
  }
}

export class TrpcBridgeAdapter implements SearchAdapter {
  readonly provider = 'trpc' as const
  readonly displayName = 'Internal tRPC'
  readonly description = 'Fast, direct API via browser extension'
  readonly icon = 'Zap'

  isAvailable(): boolean {
    if (typeof window === 'undefined') return false
    return !!window.SynapseSearchBridge?.isEnabled?.()
  }

  async search(params: SearchParams, signal?: AbortSignal): Promise<SearchResult> {
    const bridge = window.SynapseSearchBridge
    if (!bridge) {
      throw new Error('Bridge not available. Install Tampermonkey extension.')
    }

    const startTime = Date.now()

    const result = await bridge.search({
      q: params.query || '',
      limit: params.limit || 20,
      sort: params.sort || 'Most Downloaded',
      period: params.period || 'AllTime',
      cursor: params.cursor,
      filters: {
        types: params.types?.[0],
        baseModel: params.baseModels?.[0],
      }
    }, { signal })

    if (!result.ok) {
      throw new Error(result.error?.message || 'Search failed')
    }

    // CRITICAL: Transform with video detection!
    const items = (result.data?.items || []).map(transformTrpcModel)

    return {
      items,
      nextCursor: result.data?.nextCursor,
      hasMore: !!result.data?.nextCursor,
      metadata: {
        source: 'trpc',
        cached: result.meta?.cached || false,
        responseTime: result.meta?.durationMs || (Date.now() - startTime),
      }
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
    return transformTrpcModelDetail(result.data)
  }
}

function transformTrpcModelDetail(data: any): ModelDetail {
  // Similar to transformTrpcModel but with full detail fields
  const base = transformTrpcModel(data)

  return {
    ...base,
    trained_words: data.modelVersions?.[0]?.trainedWords || [],
    base_model: data.modelVersions?.[0]?.baseModel,
    download_count: data.stats?.downloadCount,
    rating: data.stats?.rating,
    rating_count: data.stats?.ratingCount,
    published_at: data.publishedAt,
    example_params: extractExampleParams(data),
  }
}

function extractExampleParams(data: any): Record<string, any> | undefined {
  const images = data.modelVersions?.[0]?.images || []
  for (const img of images) {
    if (img.meta) {
      return {
        sampler: img.meta.sampler,
        steps: img.meta.steps,
        cfg_scale: img.meta.cfgScale,
        clip_skip: img.meta.clipSkip,
        seed: img.meta.seed,
      }
    }
  }
  return undefined
}
```

### 5.2.5 Data Transformers (KRITICKÉ pro video!)

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/utils/civitaiTransformers.ts`

```typescript
import type { CivitaiModel, ModelPreview, ModelVersion } from '../api/searchTypes'

/**
 * Detect media type from URL.
 * MUST match backend logic in src/utils/media_detection.py!
 */
function detectMediaType(url: string): 'image' | 'video' | 'unknown' {
  if (!url) return 'unknown'

  const lowerUrl = url.toLowerCase()

  // Extension check
  if (lowerUrl.match(/\.(mp4|webm|mov|avi|mkv)(\?|$)/)) {
    return 'video'
  }

  // Civitai transcode pattern indicates video
  if (lowerUrl.includes('transcode=true') && !lowerUrl.includes('anim=false')) {
    return 'video'
  }

  // Path pattern
  if (lowerUrl.includes('/videos/')) {
    return 'video'
  }

  // Default to image (same as backend)
  return 'image'
}

/**
 * Get video thumbnail URL (static frame).
 * MUST match backend logic in src/utils/media_detection.py!
 */
function getVideoThumbnailUrl(url: string, width = 450): string {
  if (!url) return url

  // Non-Civitai: simple extension replacement
  if (!url.includes('civitai.com')) {
    return url.replace(/\.(mp4|webm|mov)$/i, '.jpg')
  }

  // Civitai uses path-based params like /anim=false,width=450/
  // Find the params segment or create one
  const parts = url.split('/')
  const filename = parts.pop() || ''

  // Look for existing params segment (contains '=')
  let paramsIdx = parts.findIndex(p => p.includes('=') && !p.includes('://'))

  if (paramsIdx === -1) {
    // No params yet, add before filename
    parts.push(`anim=false,transcode=true,width=${width}`)
  } else {
    // Modify existing params
    let params = parts[paramsIdx]
    // Ensure anim=false
    if (params.includes('anim=true')) {
      params = params.replace('anim=true', 'anim=false')
    } else if (!params.includes('anim=')) {
      params = `anim=false,${params}`
    }
    // Update width
    params = params.replace(/width=\d+/, `width=${width}`)
    if (!params.includes('width=')) {
      params += `,width=${width}`
    }
    parts[paramsIdx] = params
  }

  parts.push(filename)
  return parts.join('/')
}

/**
 * Transform tRPC model item to CivitaiModel.
 * Handles video detection for previews - CRITICAL!
 */
export function transformTrpcModel(item: any): CivitaiModel {
  const versions = (item.modelVersions || []).map(transformVersion)

  // Get previews from first version images
  const images = item.modelVersions?.[0]?.images || []
  const previews: ModelPreview[] = images.slice(0, 8).map((img: any) => {
    const url = img.url || ''
    const mediaType = detectMediaType(url)

    return {
      url,
      // CRITICAL: NSFW detection - both flag and level
      nsfw: img.nsfw === true || (img.nsfwLevel || 0) >= 2,
      width: img.width,
      height: img.height,
      meta: img.meta,
      media_type: mediaType,
      // CRITICAL: Video thumbnail
      thumbnail_url: mediaType === 'video' ? getVideoThumbnailUrl(url) : undefined,
    }
  })

  return {
    id: item.id,
    name: item.name || '',
    description: item.description,
    type: item.type || '',
    // CRITICAL: Model-level NSFW
    nsfw: item.nsfw || false,
    tags: item.tags || [],
    creator: item.user?.username || item.creator?.username,
    stats: {
      downloadCount: item.stats?.downloadCount,
      favoriteCount: item.stats?.favoriteCount,
      rating: item.stats?.rating,
      thumbsUpCount: item.stats?.thumbsUpCount,
    },
    versions,
    previews,
  }
}

function transformVersion(ver: any): ModelVersion {
  const files = ver.files || []
  const primaryFile = files.find((f: any) => f.primary) || files[0] || {}

  return {
    id: ver.id,
    name: ver.name || '',
    base_model: ver.baseModel,
    download_url: primaryFile.downloadUrl || ver.downloadUrl,
    file_size: primaryFile.sizeKB ? Math.round(primaryFile.sizeKB * 1024) : undefined,
    trained_words: ver.trainedWords || [],
    files: files.map((f: any) => ({
      id: f.id,
      name: f.name,
      size_kb: f.sizeKB,
      download_url: f.downloadUrl,
      hash_autov2: f.hashes?.AutoV2,
      hash_sha256: f.hashes?.SHA256,
    })),
    published_at: ver.publishedAt,
  }
}
```

### 5.2.6 Adapter Registry

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/api/searchAdapters.ts`

```typescript
import type { SearchAdapter, SearchProvider } from './searchTypes'
import { RestSearchAdapter } from './adapters/restAdapter'
import { ArchiveSearchAdapter } from './adapters/archiveAdapter'
import { TrpcBridgeAdapter } from './adapters/trpcBridgeAdapter'

// Singleton instances
const adapters: Record<SearchProvider, SearchAdapter> = {
  rest: new RestSearchAdapter(),
  archive: new ArchiveSearchAdapter(),
  trpc: new TrpcBridgeAdapter(),
}

/**
 * Get adapter by provider name.
 */
export function getAdapter(provider: SearchProvider): SearchAdapter {
  return adapters[provider]
}

/**
 * Get all available adapters (for UI dropdown).
 */
export function getAvailableAdapters(): SearchAdapter[] {
  return Object.values(adapters).filter(a => a.isAvailable())
}

/**
 * Check if a specific provider is available.
 */
export function isProviderAvailable(provider: SearchProvider): boolean {
  return adapters[provider]?.isAvailable() ?? false
}

/**
 * Get default provider (prefers tRPC if available, otherwise REST).
 */
export function getDefaultProvider(): SearchProvider {
  if (adapters.trpc.isAvailable()) return 'trpc'
  return 'rest'
}
```

---

## 🔧 Subfáze 5.3: Tampermonkey Bridge Script

### 5.3.1 Finální Tampermonkey skript

**Status:** ❌ TODO

**Soubor:** `scripts/tampermonkey/synapse-civitai-bridge.user.js`

**Vylepšení oproti původnímu:**
- ✅ `period` parametr (konfigurovatelný, ne hardcoded "AllTime")
- ✅ `model.getById` endpoint pro detail
- ✅ Cursor pagination (ne page number)
- ✅ Lepší error handling s retry
- ✅ BaseModel filter
- ✅ NSFW browsingLevel handling (31 = all, 1 = SFW)

```javascript
// ==UserScript==
// @name         Synapse Civitai Bridge
// @namespace    synapse.civitai.bridge
// @version      8.0.0
// @description  Bridge for Synapse - direct Civitai tRPC API access
// @author       SynapseTeam
// @match        http://localhost:*/*
// @match        http://127.0.0.1:*/*
// @connect      civitai.com
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        unsafeWindow
// ==/UserScript==

(function() {
    'use strict';

    const VERSION = '8.0.0';
    const TRPC_BASE = 'https://civitai.com/api/trpc';
    const CACHE_TTL = 30000;  // 30 seconds
    const CACHE_MAX_SIZE = 200;

    const target = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;
    const cache = new Map();

    // --- CONFIG ---
    function getConfig() {
        return {
            enabled: GM_getValue('synapse_bridge_enabled', true),
            nsfw: GM_getValue('synapse_bridge_nsfw', true),
        };
    }

    function saveConfig(updates) {
        if (updates.enabled !== undefined) GM_setValue('synapse_bridge_enabled', updates.enabled);
        if (updates.nsfw !== undefined) GM_setValue('synapse_bridge_nsfw', updates.nsfw);
    }

    // --- CACHE (LRU) ---
    function cacheGet(key) {
        const item = cache.get(key);
        if (!item) return null;
        if (Date.now() - item.ts > CACHE_TTL) {
            cache.delete(key);
            return null;
        }
        // LRU: move to end
        cache.delete(key);
        cache.set(key, item);
        return item.data;
    }

    function cacheSet(key, data) {
        if (cache.size >= CACHE_MAX_SIZE) {
            const oldest = cache.keys().next().value;
            cache.delete(oldest);
        }
        cache.set(key, { ts: Date.now(), data });
    }

    // --- TRPC URL BUILDERS ---
    function buildSearchUrl(params, config) {
        const input = {
            json: {
                query: params.q || undefined,
                limit: params.limit || 20,
                cursor: params.cursor || undefined,
                sort: params.sort || 'Most Downloaded',
                period: params.period || 'AllTime',
                // browsingLevel: 31 = all content, 1 = SFW only
                browsingLevel: config.nsfw ? 31 : 1,
                types: params.filters?.types ? [params.filters.types] : undefined,
                baseModels: params.filters?.baseModel ? [params.filters.baseModel] : undefined,
            }
        };

        // Clean undefined values
        Object.keys(input.json).forEach(k => {
            if (input.json[k] === undefined) delete input.json[k];
        });

        return `${TRPC_BASE}/model.getAll?input=${encodeURIComponent(JSON.stringify(input))}`;
    }

    function buildModelUrl(modelId) {
        const input = { json: { id: modelId } };
        return `${TRPC_BASE}/model.getById?input=${encodeURIComponent(JSON.stringify(input))}`;
    }

    // --- TRPC REQUEST ---
    async function trpcRequest(url, opts = {}) {
        const cacheKey = url;

        // Check cache first (unless noCache)
        if (!opts.noCache) {
            const cached = cacheGet(cacheKey);
            if (cached) {
                return { ok: true, data: cached, meta: { cached: true, durationMs: 0 } };
            }
        }

        const startTime = Date.now();

        return new Promise((resolve) => {
            let resolved = false;
            const finish = (result) => {
                if (!resolved) {
                    resolved = true;
                    resolve(result);
                }
            };

            const request = GM_xmlhttpRequest({
                method: 'GET',
                url,
                headers: { 'Content-Type': 'application/json' },
                timeout: opts.timeout || 20000,
                responseType: 'json',

                onload: (response) => {
                    if (response.status >= 200 && response.status < 300) {
                        try {
                            let data = response.response;
                            if (!data && response.responseText) {
                                data = JSON.parse(response.responseText);
                            }

                            // tRPC wraps response in result.data.json
                            const result = data?.result?.data?.json || data;

                            cacheSet(cacheKey, result);

                            finish({
                                ok: true,
                                data: result,
                                meta: { cached: false, durationMs: Date.now() - startTime }
                            });
                        } catch (e) {
                            finish({ ok: false, error: { code: 'PARSE_ERROR', message: e.message } });
                        }
                    } else {
                        const isRetryable = response.status === 429 || response.status >= 500;
                        finish({
                            ok: false,
                            error: {
                                code: response.status === 429 ? 'RATE_LIMIT' : 'HTTP_ERROR',
                                message: `HTTP ${response.status}`,
                                httpStatus: response.status,
                                retryable: isRetryable,
                            }
                        });
                    }
                },
                onerror: () => finish({ ok: false, error: { code: 'NETWORK', message: 'Network error' } }),
                ontimeout: () => finish({ ok: false, error: { code: 'TIMEOUT', message: 'Request timed out', retryable: true } }),
            });

            // Abort signal support
            if (opts.signal) {
                opts.signal.addEventListener('abort', () => {
                    try { request.abort?.(); } catch(e) {}
                    finish({ ok: false, error: { code: 'ABORTED', message: 'Request cancelled' } });
                });
            }
        });
    }

    // --- BRIDGE API ---
    const bridge = {
        version: VERSION,

        isEnabled: () => getConfig().enabled,

        getStatus: () => {
            const config = getConfig();
            return {
                enabled: config.enabled,
                nsfw: config.nsfw,
                version: VERSION,
            };
        },

        configure: (updates) => {
            saveConfig(updates);
            return bridge.getStatus();
        },

        search: async (params, opts = {}) => {
            const config = getConfig();
            if (!config.enabled) {
                return { ok: false, error: { code: 'DISABLED', message: 'Bridge is disabled' } };
            }

            const url = buildSearchUrl(params, config);
            return trpcRequest(url, opts);
        },

        getModel: async (modelId, opts = {}) => {
            const config = getConfig();
            if (!config.enabled) {
                return { ok: false, error: { code: 'DISABLED', message: 'Bridge is disabled' } };
            }

            const url = buildModelUrl(modelId);
            return trpcRequest(url, opts);
        },

        // Test connection
        test: () => bridge.search({ q: '', limit: 1 }, { noCache: true }),
    };

    // --- EXPORT TO WINDOW ---
    if (typeof cloneInto === 'function') {
        // Firefox requires cloneInto for security
        target.SynapseSearchBridge = cloneInto(bridge, target, { cloneFunctions: true });
    } else {
        target.SynapseSearchBridge = bridge;
    }

    // Dispatch ready event
    target.dispatchEvent(new Event('synapse-bridge-ready'));
    setTimeout(() => target.dispatchEvent(new Event('synapse-bridge-ready')), 100);

    console.log(`[Synapse] Bridge v${VERSION} loaded`);
})();
```

---

## 🔧 Subfáze 5.4: BrowsePage UI Updates

### 5.4.1 Nové state proměnné

**Status:** ❌ TODO

**Soubor:** `apps/web/src/components/modules/BrowsePage.tsx`

**Změny v state (kolem line 119-124):**

```typescript
// SMAZAT:
// const [useCivArchive, setUseCivArchive] = useState(false)

// PŘIDAT:
import { getAdapter, getDefaultProvider, isProviderAvailable } from '@/lib/api/searchAdapters'
import type { SearchProvider, SortOption, PeriodOption } from '@/lib/api/searchTypes'
import { SORT_OPTIONS, PERIOD_OPTIONS, BASE_MODEL_OPTIONS } from '@/lib/api/searchTypes'

// State
const [searchProvider, setSearchProvider] = useState<SearchProvider>(() => {
  const saved = localStorage.getItem('synapse-search-provider')
  if (saved && ['rest', 'archive', 'trpc'].includes(saved)) {
    // Verify it's still available
    if (isProviderAvailable(saved as SearchProvider)) {
      return saved as SearchProvider
    }
  }
  return getDefaultProvider()
})
const [sortBy, setSortBy] = useState<SortOption>('Most Downloaded')
const [period, setPeriod] = useState<PeriodOption>('AllTime')
const [baseModel, setBaseModel] = useState<string>('')

// Persist provider choice
useEffect(() => {
  localStorage.setItem('synapse-search-provider', searchProvider)
}, [searchProvider])
```

### 5.4.2 Změny v queryFn

**Status:** ❌ TODO

**Nahradit celou queryFn (lines 158-259) za:**

```typescript
const { data: searchResults, isLoading, error, isFetching } = useQuery({
  queryKey: [
    'civitai-search',
    activeSearch,
    selectedType,
    searchProvider,
    sortBy,
    period,
    baseModel,
    currentCursor
  ],
  queryFn: async ({ signal }) => {
    let adapter = getAdapter(searchProvider)

    // Fallback if tRPC not available
    if (!adapter.isAvailable() && searchProvider === 'trpc') {
      console.warn('[BrowsePage] tRPC bridge not available, falling back to REST')
      adapter = getAdapter('rest')
    }

    const result = await adapter.search({
      query: activeSearch || undefined,
      types: selectedType ? [selectedType] : undefined,
      baseModels: baseModel ? [baseModel] : undefined,
      sort: sortBy,
      period,
      nsfw: includeNsfw,
      limit: 20,
      cursor: currentCursor,
    }, signal)

    // Log for debugging
    console.log(`[BrowsePage] Search via ${result.metadata?.source}:`, {
      items: result.items.length,
      hasMore: result.hasMore,
      cached: result.metadata?.cached,
      time: result.metadata?.responseTime,
    })

    // Transform to expected format
    return {
      items: result.items,
      next_cursor: result.nextCursor,
    }
  },
  enabled: true,
  staleTime: 5 * 60 * 1000,
  retry: 2,
})
```

### 5.4.3 UI Filtry

**Status:** ❌ TODO

**Nahradit checkbox (lines 551-573) za filtry:**

*(Viz vizuální návrhy níže - uživatel vybere variantu)*

---

## 🎨 VIZUÁLNÍ NÁVRHY - ~~VYBER SI!~~ ✅ VYBRÁNO: VARIANTA C

> **ROZHODNUTÍ (2026-01-22):** Uživatel vybral **Variantu C - Floating Chips**
> - Premium design s animacemi
> - Mockup: `plans/ui-mockups-phase5-final.html`
> - Klíčové features: glow pulse, staggered entrance, hover lift, dropdown slide

### Varianta A: Kompaktní řada

Jednoduchá, horizontální řada filtrů. Provider je zvýrazněný gradientem.

```html
<div class="flex flex-wrap items-center gap-3 p-3 bg-slate-dark/50 rounded-xl border border-slate-mid/30">
  <!-- Provider - zvýrazněný -->
  <div class="flex items-center gap-2">
    <span class="text-xs text-text-muted uppercase tracking-wider">Via</span>
    <select class="appearance-none bg-gradient-to-r from-synapse/20 to-pulse/20 border border-synapse/30 rounded-lg px-3 py-1.5 pr-8 text-sm text-synapse font-medium cursor-pointer hover:border-synapse/50 transition-all">
      <option>⚡ Internal tRPC</option>
      <option>🌐 REST API</option>
      <option>📦 CivArchive</option>
    </select>
  </div>

  <div class="w-px h-6 bg-slate-mid/50"></div>

  <!-- Sort -->
  <select class="bg-slate-dark border border-slate-mid rounded-lg px-3 py-1.5 text-sm text-text-primary">
    <option>Most Downloaded</option>
    <option>Highest Rated</option>
    <option>Newest</option>
  </select>

  <!-- Period -->
  <select class="bg-slate-dark border border-slate-mid rounded-lg px-3 py-1.5 text-sm text-text-primary">
    <option>All Time</option>
    <option>This Month</option>
    <option>This Week</option>
  </select>

  <!-- Base Model -->
  <select class="bg-slate-dark border border-slate-mid rounded-lg px-3 py-1.5 text-sm text-text-primary">
    <option>All Models</option>
    <option>SDXL 1.0</option>
    <option>Pony</option>
    <option>Flux.1</option>
  </select>

  <!-- Status -->
  <div class="ml-auto flex items-center gap-2 text-xs">
    <div class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
    <span class="text-text-muted">Ready</span>
  </div>
</div>
```

---

### Varianta B: Tab-style provider + expandable panel

Provider jako vizuální tabs, filtry v rozbalovacím panelu.

```html
<div class="space-y-3">
  <!-- Provider Tabs -->
  <div class="flex items-center gap-1 p-1 bg-slate-dark rounded-xl border border-slate-mid/30">
    <button class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-synapse to-pulse rounded-lg text-white text-sm font-medium shadow-lg shadow-synapse/25">
      ⚡ Internal tRPC
    </button>
    <button class="px-4 py-2 text-text-secondary text-sm hover:text-text-primary hover:bg-slate-mid/50 rounded-lg transition-all">
      🌐 REST API
    </button>
    <button class="px-4 py-2 text-text-secondary text-sm hover:text-text-primary hover:bg-slate-mid/50 rounded-lg transition-all">
      📦 CivArchive
    </button>
    <div class="flex-1"></div>
    <button class="flex items-center gap-2 px-3 py-2 text-text-muted text-sm hover:text-text-primary">
      ⚙️ Filters
      <span class="px-1.5 py-0.5 bg-synapse/20 text-synapse text-xs rounded">3</span>
    </button>
  </div>

  <!-- Expandable filters -->
  <div class="grid grid-cols-3 gap-3 p-4 bg-slate-dark/30 rounded-xl border border-slate-mid/20">
    <div class="space-y-1.5">
      <label class="text-xs text-text-muted uppercase">Sort By</label>
      <select class="w-full bg-slate-dark border border-slate-mid rounded-lg px-3 py-2 text-sm">
        <option>Most Downloaded</option>
      </select>
    </div>
    <div class="space-y-1.5">
      <label class="text-xs text-text-muted uppercase">Period</label>
      <select class="w-full bg-slate-dark border border-slate-mid rounded-lg px-3 py-2 text-sm">
        <option>All Time</option>
      </select>
    </div>
    <div class="space-y-1.5">
      <label class="text-xs text-text-muted uppercase">Base Model</label>
      <select class="w-full bg-slate-dark border border-slate-mid rounded-lg px-3 py-2 text-sm">
        <option>All</option>
      </select>
    </div>
  </div>
</div>
```

---

### Varianta C: Floating chips

Minimalistické "chips" s aktivním stavem. Kliknutím otevřou dropdown.

```html
<div class="flex items-center gap-2 flex-wrap">
  <!-- Provider chip - special -->
  <button class="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-synapse/10 to-pulse/10 border border-synapse/30 rounded-full text-sm hover:border-synapse/50">
    <span class="w-2 h-2 rounded-full bg-synapse animate-pulse"></span>
    <span class="text-synapse font-medium">tRPC</span>
    <span class="text-synapse/50">▼</span>
  </button>

  <!-- Filter chips -->
  <button class="px-3 py-1.5 bg-slate-dark border border-slate-mid rounded-full text-sm text-text-secondary hover:border-slate-light">
    Most Downloaded ▼
  </button>

  <button class="px-3 py-1.5 bg-slate-dark border border-slate-mid rounded-full text-sm text-text-secondary hover:border-slate-light">
    All Time ▼
  </button>

  <!-- Active filter with X -->
  <button class="flex items-center gap-1.5 px-3 py-1.5 bg-synapse/10 border border-synapse/30 rounded-full text-sm text-synapse">
    SDXL 1.0
    <span class="hover:text-white">✕</span>
  </button>

  <!-- Add filter -->
  <button class="px-2 py-1.5 text-text-muted text-sm hover:text-text-primary">
    + Add filter
  </button>

  <!-- Status -->
  <div class="ml-auto px-3 py-1 rounded-full bg-green-500/10 border border-green-500/20">
    <span class="text-xs text-green-400">● Live</span>
  </div>
</div>
```

---

## 🔧 Subfáze 5.5: Testy

### 5.5.1 Frontend testy - Adaptery

**Status:** ❌ TODO

**Soubor:** `apps/web/src/__tests__/search-adapters.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { RestSearchAdapter } from '@/lib/api/adapters/restAdapter'
import { TrpcBridgeAdapter } from '@/lib/api/adapters/trpcBridgeAdapter'
import { getAdapter, getDefaultProvider } from '@/lib/api/searchAdapters'

describe('RestSearchAdapter', () => {
  it('should always be available', () => {
    const adapter = new RestSearchAdapter()
    expect(adapter.isAvailable()).toBe(true)
  })

  it('should return items from /api/browse/search', async () => {
    // Mock fetch...
  })
})

describe('TrpcBridgeAdapter', () => {
  it('should be unavailable when bridge not in window', () => {
    const adapter = new TrpcBridgeAdapter()
    expect(adapter.isAvailable()).toBe(false)
  })

  it('should be available when bridge is enabled', () => {
    window.SynapseSearchBridge = {
      version: '8.0.0',
      isEnabled: () => true,
      getStatus: () => ({ enabled: true, nsfw: true, version: '8.0.0' }),
      search: vi.fn(),
    }
    const adapter = new TrpcBridgeAdapter()
    expect(adapter.isAvailable()).toBe(true)
  })
})

describe('getDefaultProvider', () => {
  it('should return trpc when bridge available', () => {
    window.SynapseSearchBridge = { isEnabled: () => true, /* ... */ }
    expect(getDefaultProvider()).toBe('trpc')
  })

  it('should return rest when bridge not available', () => {
    delete window.SynapseSearchBridge
    expect(getDefaultProvider()).toBe('rest')
  })
})
```

### 5.5.2 Frontend testy - Transformer

**Status:** ❌ TODO

**Soubor:** `apps/web/src/__tests__/trpc-transformer.test.ts`

```typescript
import { describe, it, expect } from 'vitest'
import { transformTrpcModel } from '@/lib/utils/civitaiTransformers'

describe('transformTrpcModel', () => {
  it('should transform basic model data', () => {
    const input = {
      id: 123,
      name: 'Test Model',
      type: 'LORA',
      nsfw: false,
      modelVersions: [{
        id: 456,
        name: 'v1.0',
        images: [{ url: 'https://example.com/image.jpg', nsfw: false }]
      }]
    }

    const result = transformTrpcModel(input)

    expect(result.id).toBe(123)
    expect(result.name).toBe('Test Model')
    expect(result.nsfw).toBe(false)
    expect(result.previews).toHaveLength(1)
  })

  it('should detect video from .mp4 extension', () => {
    const input = {
      id: 1,
      name: 'Video Model',
      modelVersions: [{
        images: [{ url: 'https://civitai.com/video.mp4', nsfw: false }]
      }]
    }

    const result = transformTrpcModel(input)

    expect(result.previews[0].media_type).toBe('video')
    expect(result.previews[0].thumbnail_url).toBeDefined()
    expect(result.previews[0].thumbnail_url).toContain('anim=false')
  })

  it('should detect video from transcode=true pattern', () => {
    const input = {
      id: 1,
      name: 'Transcode Video',
      modelVersions: [{
        images: [{ url: 'https://civitai.com/preview.jpeg?transcode=true', nsfw: false }]
      }]
    }

    const result = transformTrpcModel(input)

    expect(result.previews[0].media_type).toBe('video')
  })

  it('should preserve NSFW flag on model level', () => {
    const input = {
      id: 1,
      name: 'NSFW Model',
      nsfw: true,
      modelVersions: [{ images: [] }]
    }

    const result = transformTrpcModel(input)

    expect(result.nsfw).toBe(true)
  })

  it('should detect NSFW from nsfwLevel >= 2', () => {
    const input = {
      id: 1,
      name: 'Model',
      nsfw: false,
      modelVersions: [{
        images: [{ url: 'https://example.com/img.jpg', nsfw: false, nsfwLevel: 3 }]
      }]
    }

    const result = transformTrpcModel(input)

    expect(result.previews[0].nsfw).toBe(true)
  })
})
```

### 5.5.3 Backend testy

**Status:** ❌ TODO

**Soubor:** `tests/unit/test_civarchive_pagination.py`

*(Viz sekce 5.1.2)*

---

## 📋 Celkový checklist

### Fáze 5.1: CivArchive Fix ✅ DONE
- [x] 5.1.1 Backend pagination parametry (page, pages_per_request) ✅
- [x] 5.1.2 Response má has_more a current_page ✅
- [x] 5.1.3 Testy ✅

### Fáze 5.2: Frontend Adapters ✅ DONE
- [x] 5.2.1 searchTypes.ts - TypeScript typy ✅
- [x] 5.2.2 restAdapter.ts - REST API adapter ✅
- [x] 5.2.3 archiveAdapter.ts - CivArchive adapter s pagination ✅
- [x] 5.2.4 trpcBridgeAdapter.ts - tRPC bridge adapter ✅
- [x] 5.2.5 civitaiTransformers.ts - Data transformers s video detection! ✅
- [x] 5.2.6 searchAdapters.ts - Registry ✅

### Fáze 5.3: Tampermonkey Script ✅ DONE
- [x] 5.3.1 Finální skript v8.0.0 ✅ (`scripts/tampermonkey/synapse-civitai-bridge.user.js`)

### Fáze 5.4: BrowsePage UI ✅ DONE
- [x] 5.4.1 Nové state (provider, sort, period, baseModel) ✅
- [x] 5.4.2 queryFn s adapter pattern ✅
- [x] 5.4.3 UI filtry (vybraná varianta: **C - Floating Chips** ✅) - `SearchFilters.tsx`

### Fáze 5.5: Testy ✅ DONE
- [x] 5.5.1 search-adapters.test.ts ✅ (25 tests)
- [x] 5.5.2 civitai-transformers.test.ts ✅ (40 tests)
- [x] 5.5.3 test_civarchive_pagination.py ✅ (10 tests)

---

## 📝 Implementační log

| Datum | Co | Kdo |
|-------|-----|-----|
| 2026-01-22 | PLAN vytvořen, analýza BrowsePage, browse.py, testů | Claude |
| 2026-01-22 | UI mockupy vytvořeny (`plans/ui-mockups-phase5-final.html`) | Claude |
| 2026-01-22 | **ROZHODNUTÍ:** Varianta C - Floating Chips | User |
| 2026-01-22 | Začátek implementace - subfáze 5.1 | Claude |
| 2026-01-22 | 5.1 CivArchive pagination fix DONE | Claude |
| 2026-01-22 | 5.2 Frontend adapters DONE | Claude |
| 2026-01-22 | 5.3 Tampermonkey script v8.0.0 DONE | Claude |
| 2026-01-22 | 5.4 BrowsePage UI + SearchFilters DONE | Claude |
| 2026-01-22 | 5.5 Testy DONE (75 tests) | Claude |
| 2026-01-22 | **PHASE 5 KOMPLETNÍ** | Claude |

---

## 🚨 Známé problémy a rizika

1. **tRPC API změny** - Civitai může změnit tRPC strukturu bez varování
2. **Bridge nedostupný** - Fallback na REST musí fungovat bezchybně
3. **Video detection** - Transformer MUSÍ používat stejnou logiku jako backend
4. **NSFW handling** - Nesmí se rozbít globální blur toggle z Header
5. **CivArchive timeout** - Více stránek = delší čas, timeout 90s

---

## 📚 Reference

- `apps/api/src/routers/browse.py` - Backend browse router (1371 lines)
- `apps/web/src/components/modules/BrowsePage.tsx` - Frontend (942 lines)
- `apps/web/src/stores/settingsStore.ts` - NSFW blur state
- `src/utils/media_detection.py` - Video detection logic (backend)
- `apps/web/src/components/layout/Header.tsx` - NSFW toggle UI

---

*Vytvořeno: 2026-01-22*
*Poslední aktualizace: 2026-01-22*
*Status: ✅ DOKONČENO*
