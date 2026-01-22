/**
 * Search Types for Phase 5 - Internal Civitai Search
 *
 * These types define the unified interface for all search providers
 * (REST API, CivArchive, tRPC Bridge).
 */

import type { MediaType } from '@/lib/media'

// =============================================================================
// Search Provider Types
// =============================================================================

export type SearchProvider = 'rest' | 'archive' | 'trpc'

// =============================================================================
// Filter Options
// =============================================================================

export type SortOption =
  | 'Most Downloaded'
  | 'Highest Rated'
  | 'Newest'
  | 'Most Discussed'
  | 'Most Collected'
  | 'Most Buzz'

export type PeriodOption = 'AllTime' | 'Year' | 'Month' | 'Week' | 'Day'

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
  { value: 'Wan', label: 'Wan' },
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

// =============================================================================
// Model Types (matching BrowsePage.tsx)
// =============================================================================

export interface ModelPreview {
  url: string
  nsfw: boolean
  width?: number
  height?: number
  meta?: Record<string, unknown>
  media_type?: MediaType
  duration?: number
  thumbnail_url?: string
}

export interface ModelFile {
  id: number
  name: string
  size_kb?: number
  download_url?: string
  hash_autov2?: string
  hash_sha256?: string
}

export interface ModelVersion {
  id: number
  name: string
  base_model?: string
  download_url?: string
  file_size?: number
  trained_words: string[]
  files?: ModelFile[]
  published_at?: string
}

export interface CivitaiModel {
  id: number
  name: string
  description?: string
  type: string
  nsfw: boolean
  tags: string[]
  creator?: string
  stats: {
    downloadCount?: number
    favoriteCount?: number
    commentCount?: number
    ratingCount?: number
    rating?: number
    thumbsUpCount?: number
  }
  versions: ModelVersion[]
  previews: ModelPreview[]
}

export interface ModelDetail extends CivitaiModel {
  trained_words: string[]
  base_model?: string
  download_count?: number
  rating?: number
  rating_count?: number
  published_at?: string
  hash_autov2?: string
  civitai_air?: string
  example_params?: Record<string, unknown>
}

// =============================================================================
// Search Parameters
// =============================================================================

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

// =============================================================================
// Search Results
// =============================================================================

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

// =============================================================================
// Search Adapter Interface
// =============================================================================

export interface SearchAdapter {
  readonly provider: SearchProvider
  readonly displayName: string
  readonly description: string
  readonly icon: string // Lucide icon name

  /**
   * Check if this adapter is available (e.g., tRPC needs bridge extension)
   */
  isAvailable(): boolean

  /**
   * Search for models
   */
  search(params: SearchParams, signal?: AbortSignal): Promise<SearchResult>

  /**
   * Get detailed model information (optional - some adapters may not support this)
   */
  getModelDetail?(modelId: number): Promise<ModelDetail>
}

// =============================================================================
// Provider Config for UI
// =============================================================================

export interface ProviderConfig {
  provider: SearchProvider
  displayName: string
  shortName: string
  description: string
  icon: string
  color: string // Tailwind color class
  glowColor: string // For active state
  statusLabel: string
}

export const PROVIDER_CONFIGS: Record<SearchProvider, ProviderConfig> = {
  trpc: {
    provider: 'trpc',
    displayName: 'Internal tRPC',
    shortName: 'tRPC',
    description: 'Fast, direct API via browser extension',
    icon: 'Zap',
    color: 'synapse',
    glowColor: 'rgba(139, 92, 246, 0.4)',
    statusLabel: 'Live',
  },
  rest: {
    provider: 'rest',
    displayName: 'REST API',
    shortName: 'REST',
    description: 'Standard API, stable and reliable',
    icon: 'Globe',
    color: 'blue-500',
    glowColor: 'rgba(59, 130, 246, 0.4)',
    statusLabel: 'Stable',
  },
  archive: {
    provider: 'archive',
    displayName: 'CivArchive',
    shortName: 'Archive',
    description: 'Searches descriptions, finds deleted models',
    icon: 'Archive',
    color: 'amber-500',
    glowColor: 'rgba(245, 158, 11, 0.4)',
    statusLabel: 'External',
  },
}
