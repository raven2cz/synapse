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

// Complete list from Civitai (screenshot: base-model-filter.png)
export const BASE_MODEL_OPTIONS = [
  { value: '', label: 'All Base Models' },
  // Popular
  { value: 'SDXL 1.0', label: 'SDXL 1.0' },
  { value: 'SD 1.5', label: 'SD 1.5' },
  { value: 'Pony', label: 'Pony' },
  { value: 'Illustrious', label: 'Illustrious' },
  // Flux
  { value: 'Flux.1 D', label: 'Flux.1 Dev' },
  { value: 'Flux.1 S', label: 'Flux.1 Schnell' },
  { value: 'Flux.1 Kontext', label: 'Flux.1 Kontext' },
  { value: 'Flux.1 Krea', label: 'Flux.1 Krea' },
  { value: 'Flux.2 D', label: 'Flux.2 D' },
  { value: 'Flux.2 Klein 4B', label: 'Flux.2 Klein 4B' },
  { value: 'Flux.2 Klein 4B-Base', label: 'Flux.2 Klein 4B-Base' },
  { value: 'Flux.2 Klein 9B', label: 'Flux.2 Klein 9B' },
  { value: 'Flux.2 Klein 9B-Base', label: 'Flux.2 Klein 9B-Base' },
  // SD versions
  { value: 'SD 1.4', label: 'SD 1.4' },
  { value: 'SD 1.5 Hyper', label: 'SD 1.5 Hyper' },
  { value: 'SD 1.5 LCM', label: 'SD 1.5 LCM' },
  { value: 'SD 2.0', label: 'SD 2.0' },
  { value: 'SD 2.0 768', label: 'SD 2.0 768' },
  { value: 'SD 2.1', label: 'SD 2.1' },
  { value: 'SD 2.1 768', label: 'SD 2.1 768' },
  { value: 'SD 2.1 Unclip', label: 'SD 2.1 Unclip' },
  { value: 'SD 3', label: 'SD 3' },
  { value: 'SD 3.5', label: 'SD 3.5' },
  // SDXL variants
  { value: 'SDXL 0.9', label: 'SDXL 0.9' },
  { value: 'SDXL 1.0 LCM', label: 'SDXL 1.0 LCM' },
  { value: 'SDXL Distilled', label: 'SDXL Distilled' },
  { value: 'SDXL Hyper', label: 'SDXL Hyper' },
  { value: 'SDXL Lightning', label: 'SDXL Lightning' },
  // Pony variants
  { value: 'Pony V7', label: 'Pony V7' },
  { value: 'Playground V2', label: 'Playground V2' },
  // Video models
  { value: 'SVD XT', label: 'SVD XT' },
  { value: 'Hunyuan 1', label: 'Hunyuan 1' },
  { value: 'Hunyuan Video', label: 'Hunyuan Video' },
  { value: 'CogVideoX', label: 'CogVideoX' },
  { value: 'Wan Video', label: 'Wan Video' },
  { value: 'Wan Video 1.3B T2v', label: 'Wan Video 1.3B T2v' },
  { value: 'Wan Video 14B I2v 480p', label: 'Wan Video 14B I2v 480p' },
  { value: 'Wan Video 14B I2v 720p', label: 'Wan Video 14B I2v 720p' },
  { value: 'Wan Video 14B T2v', label: 'Wan Video 14B T2v' },
  // Image models
  { value: 'LTXV', label: 'LTXV' },
  { value: 'LTXV2', label: 'LTXV2' },
  { value: 'Lumina', label: 'Lumina' },
  { value: 'Mochi', label: 'Mochi' },
  { value: 'Nano Banana', label: 'Nano Banana' },
  { value: 'NoobAI', label: 'NoobAI' },
  { value: 'ODOR', label: 'ODOR' },
  { value: 'Open AI', label: 'Open AI' },
  { value: 'PixArt Σ', label: 'PixArt Σ' },
  { value: 'PixArt A', label: 'PixArt A' },
  { value: 'Qwen', label: 'Qwen' },
  { value: 'Seedream', label: 'Seedream' },
  { value: 'Sora 2', label: 'Sora 2' },
  { value: 'Stable Cascade', label: 'Stable Cascade' },
  { value: 'Veo 3', label: 'Veo 3' },
  { value: 'Imagen 4', label: 'Imagen 4' },
  { value: 'Kolors', label: 'Kolors' },
  { value: 'HiDream', label: 'HiDream' },
  { value: 'Aura Flow', label: 'Aura Flow' },
  { value: 'Chroma', label: 'Chroma' },
  { value: 'Z Image Turbo', label: 'Z Image Turbo' },
  { value: 'Other', label: 'Other' },
] as const

/**
 * Model types - VERIFIED from Civitai Prisma schema
 * Source: https://github.com/civitai/civitai/blob/main/prisma/schema.prisma
 * These values are the exact enum values used in the Civitai database.
 */
export const MODEL_TYPE_OPTIONS = [
  { value: '', label: 'All Types' },
  { value: 'LORA', label: 'LoRA' },
  { value: 'LoCon', label: 'LyCORIS' },
  { value: 'DoRA', label: 'DoRA' },
  { value: 'Checkpoint', label: 'Checkpoint' },
  { value: 'TextualInversion', label: 'Embedding' },
  { value: 'Hypernetwork', label: 'Hypernetwork' },
  { value: 'AestheticGradient', label: 'Aesthetic Gradient' },
  { value: 'Controlnet', label: 'ControlNet' },
  { value: 'Upscaler', label: 'Upscaler' },
  { value: 'VAE', label: 'VAE' },
  { value: 'Poses', label: 'Poses' },
  { value: 'Wildcards', label: 'Wildcards' },
  { value: 'Workflows', label: 'Workflows' },
  { value: 'MotionModule', label: 'Motion' },
  { value: 'Detection', label: 'Detection' },
  { value: 'Other', label: 'Other' },
] as const

/**
 * File formats from Civitai (screenshot: file-format-filter.png)
 *
 * STATUS: NEEDS VERIFICATION - API values may differ from display labels
 *
 * Public API only documents: SafeTensor, PickleTensor, Other
 * Source: https://github.com/civitai/civitai/wiki/REST-API-Reference
 *
 * The internal tRPC API likely has more formats. Values below are GUESSED
 * based on display labels - need to capture actual API requests to verify.
 *
 * TODO: Capture network requests from Civitai website to get exact enum values
 */
export const FILE_FORMAT_OPTIONS = [
  { value: '', label: 'All Formats' },
  // VERIFIED in public API:
  { value: 'SafeTensor', label: 'Safe Tensor' },
  { value: 'PickleTensor', label: 'Pickle Tensor' },
  // UNVERIFIED - guessed from display, may need different API values:
  { value: 'Diffusers', label: 'Diffusers' },      // TODO: verify API value
  { value: 'GGUF', label: 'GGUF' },                // TODO: verify API value
  { value: 'Core ML', label: 'Core ML' },          // TODO: verify API value (might be "CoreML")
  { value: 'ONNX', label: 'ONNX' },                // TODO: verify API value
  { value: 'Pt', label: 'Pt' },                    // TODO: verify API value
  { value: 'Other', label: 'Other' },
] as const

/**
 * Categories from Civitai (screenshot: category-filter.png)
 *
 * STATUS: NEEDS VERIFICATION - these are internal tags, not a public API parameter
 *
 * Categories in Civitai are implemented as tags with special handling.
 * The public REST API doesn't have a 'category' parameter - it uses 'tag'.
 *
 * The internal tRPC API likely uses tag IDs or slugs.
 * Values below are GUESSED as lowercase slugs - need verification.
 *
 * TODO: Capture network requests from Civitai website to get exact tag format
 */
export const CATEGORY_OPTIONS = [
  { value: '', label: 'All Categories' },
  // Values are guessed as lowercase slugs - may need different format (IDs, etc.)
  { value: 'character', label: 'Character' },
  { value: 'style', label: 'Style' },
  { value: 'celebrity', label: 'Celebrity' },
  { value: 'concept', label: 'Concept' },
  { value: 'clothing', label: 'Clothing' },
  { value: 'base model', label: 'Base Model' },    // TODO: might be "base-model" or ID
  { value: 'poses', label: 'Poses' },
  { value: 'background', label: 'Background' },
  { value: 'tool', label: 'Tool' },
  { value: 'buildings', label: 'Buildings' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'objects', label: 'Objects' },
  { value: 'animal', label: 'Animal' },
  { value: 'action', label: 'Action' },
  { value: 'assets', label: 'Assets' },
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
  // Additional filters (Phase 5)
  fileFormat?: string     // TODO: Not yet integrated - needs API verification
  category?: string       // TODO: Not yet integrated - needs API verification (uses tag system)
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

  /**
   * Fetch preview images separately (optional — enables progressive loading).
   * Adapters that return images in getModelDetail don't need this.
   * Used by tRPC bridge where model.getById returns 0 images
   * and image.getInfinite must be called separately with modelVersionId.
   */
  getModelPreviews?(modelId: number, versionId: number): Promise<ModelPreview[]>
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
