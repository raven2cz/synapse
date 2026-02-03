/**
 * Pack Detail Types
 *
 * Centralized type definitions for the pack-detail module.
 * Extracted from PackDetailPage.tsx for modularity.
 */

import type { MediaType } from '@/lib/media'

// =============================================================================
// Pack Types
// =============================================================================

/**
 * Pack source provider (matches backend ProviderName enum)
 */
export type PackSourceProvider = 'civitai' | 'huggingface' | 'local' | 'url'

/**
 * Pack type (primary asset type, matches backend AssetKind enum)
 */
export type PackType = 'checkpoint' | 'lora' | 'vae' | 'embedding' | 'controlnet' | 'upscaler' | 'other'

/**
 * Pack category - determines origin and editability (matches backend PackCategory enum)
 * - EXTERNAL: Imported from Civitai, HuggingFace, etc. (metadata read-only)
 * - CUSTOM: Created locally from scratch (fully editable)
 * - INSTALL: Installation pack for UI environments (script-based management)
 */
export type PackCategory = 'external' | 'custom' | 'install'

/**
 * Pack source info from backend (matches PackSource model)
 */
export interface PackSourceInfo {
  provider: PackSourceProvider
  model_id?: number
  version_id?: number
  url?: string
}

/**
 * Reference to another pack this pack depends on (matches backend PackDependencyRef model)
 * Enables pack dependency trees (e.g., LoRA depends on Checkpoint pack)
 */
export interface PackDependencyRef {
  pack_name: string
  required?: boolean
  version_constraint?: string
}

/**
 * Asset/dependency type
 */
export type AssetType = 'checkpoint' | 'lora' | 'vae' | 'embedding' | 'controlnet' | 'upscaler' | 'other'

/**
 * Download status for assets
 */
export type AssetStatus = 'installed' | 'pending' | 'downloading' | 'error' | 'unresolved'

// =============================================================================
// Asset & Preview
// =============================================================================

/**
 * Source information for external assets
 */
export interface AssetSourceInfo {
  model_id?: number
  version_id?: number
  model_name?: string
  version_name?: string
  creator?: string
  repo_id?: string
  filename?: string
}

/**
 * Asset information (dependency)
 */
export interface AssetInfo {
  name: string
  asset_type: AssetType | string
  source: string
  source_info?: AssetSourceInfo
  size?: number
  installed: boolean
  status: string
  base_model_hint?: string
  url?: string
  filename?: string
  local_path?: string
  version_name?: string
  sha256?: string
  provider_name?: string
  description?: string
}

/**
 * Preview media information
 */
export interface PreviewInfo {
  filename: string
  url?: string
  nsfw: boolean
  width?: number
  height?: number
  meta?: Record<string, unknown>
  media_type?: MediaType
  duration?: number
  thumbnail_url?: string
  has_audio?: boolean
}

/**
 * Workflow attached to pack
 */
export interface WorkflowInfo {
  name: string
  filename: string
  description?: string
  is_default: boolean
  local_path?: string
  has_symlink: boolean
  symlink_valid: boolean
  symlink_path?: string
}

/**
 * Custom node requirement
 */
export interface CustomNodeInfo {
  name: string
  git_url?: string
  installed: boolean
}

// =============================================================================
// Parameters & Model Info
// =============================================================================

/**
 * Generation parameters
 */
export interface ParametersInfo {
  sampler?: string
  scheduler?: string
  steps?: number
  cfg_scale?: number
  clip_skip?: number
  denoise?: number
  width?: number
  height?: number
  seed?: number
  hires_fix?: boolean
  hires_upscaler?: string
  hires_steps?: number
  hires_denoise?: number
  /** AI provider that extracted these parameters */
  _extracted_by?: string
  [key: string]: unknown // Allow custom parameters
}

/**
 * Source of parameters - where they were extracted from
 */
export type ParameterSourceType = 'manual' | 'description' | 'image' | 'aggregated'

/**
 * Parameter source info for tracking origin
 */
export interface ParameterSource {
  type: ParameterSourceType
  /** Index of preview image (for type='image') */
  imageIndex?: number
  /** URL/thumbnail of source image */
  imageUrl?: string
  /** Confidence score for aggregated (0-1) */
  confidence?: number
}

/**
 * Model metadata from Civitai/other sources
 */
export interface ModelInfoResponse {
  model_type?: string
  base_model?: string
  trigger_words: string[]
  usage_tips?: string
  hash_autov2?: string
  civitai_air?: string
  download_count?: number
  rating?: number
  published_at?: string
  strength_recommended?: number
}

// =============================================================================
// Pack Detail (Full Response)
// =============================================================================

/**
 * Full pack detail response from API
 */
export interface PackDetail {
  name: string
  version: string
  description?: string
  author?: string
  tags: string[]
  user_tags: string[]
  source_url?: string
  created_at?: string
  installed: boolean
  has_unresolved: boolean
  all_installed: boolean
  can_generate: boolean
  assets: AssetInfo[]
  previews: PreviewInfo[]
  workflows: WorkflowInfo[]
  custom_nodes: CustomNodeInfo[]
  docs: Record<string, string>
  parameters?: ParametersInfo
  model_info?: ModelInfoResponse

  /**
   * Cover URL in same format as preview URLs (for frontend comparison)
   * Transformed by API to use /previews/ format
   */
  cover_url?: string

  /**
   * Raw pack data from backend (Pack.model_dump())
   * Contains full source info, pack_type, pack_category, etc.
   */
  pack?: {
    schema?: string
    name: string
    pack_type: PackType
    pack_category?: PackCategory  // EXTERNAL, CUSTOM, INSTALL
    source: PackSourceInfo
    pack_dependencies?: PackDependencyRef[]  // Dependencies on other packs
    base_model?: string
    trigger_words?: string[]
    /** AI provider that extracted parameters during import */
    parameters_source?: string
    // Other fields available but not commonly needed in UI
    [key: string]: unknown
  }

  /**
   * Raw lock data from backend
   */
  lock?: Record<string, unknown>
}

// =============================================================================
// Download Progress
// =============================================================================

/**
 * Single download progress tracking
 */
export interface DownloadProgress {
  download_id: string
  pack_name: string
  asset_name: string
  filename: string
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'error' | 'cancelled'
  progress: number
  downloaded_bytes: number
  total_bytes: number
  speed_bps: number
  eta_seconds: number | null
  error: string | null
}

// =============================================================================
// Base Model Search
// =============================================================================

/**
 * Local model from ComfyUI
 */
export interface LocalModel {
  name: string
  path: string
  type: string
  size?: number
}

/**
 * Base model search result - unified format for all sources
 */
export interface BaseModelResult {
  model_id: string
  model_name: string
  creator?: string
  download_count: number
  version_id?: string
  version_name?: string
  file_name: string
  size_kb: number
  size_gb?: number
  download_url: string
  base_model?: string
  source: 'civitai' | 'huggingface' | string
  source_url?: string
}

/**
 * Base model search response
 */
export interface BaseModelSearchResponse {
  results: BaseModelResult[]
  total_found: number
  source: string
  search_query: string
  search_method?: string
}

// =============================================================================
// HuggingFace
// =============================================================================

/**
 * HuggingFace file info
 */
export interface HuggingFaceFile {
  filename: string
  size_bytes: number
  size_gb?: number
  download_url: string
  is_recommended: boolean
  file_type: string
}

// =============================================================================
// Edit Mode Types
// =============================================================================

/**
 * Pack edit state
 */
export interface PackEditState {
  isEditing: boolean
  editingSection: string | null
  hasUnsavedChanges: boolean
  pendingChanges: Partial<PackDetail>
  errors: Record<string, string>
}

/**
 * Section identifiers for granular editing
 */
export type PackSection =
  | 'header'
  | 'gallery'
  | 'info'
  | 'dependencies'
  | 'workflows'
  | 'parameters'
  | 'storage'
  | 'scripts'

/**
 * Validation result for pack changes
 */
export interface ValidationResult {
  valid: boolean
  errors: Record<string, string>
}

// =============================================================================
// UI State Types
// =============================================================================

/**
 * Card size for gallery grid
 */
export type CardSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

/**
 * Tab for base model resolver
 */
export type ResolverTab = 'local' | 'civitai' | 'huggingface'

/**
 * Modal state for centralized modal management
 */
export interface ModalState {
  editPack: boolean
  editParameters: boolean
  editPreviews: boolean
  editDependencies: boolean
  editWorkflows: boolean
  uploadWorkflow: boolean
  baseModelResolver: boolean
  importModel: boolean
  markdownEditor: boolean
  scriptConsole: boolean
  confirmDelete: boolean
  pullConfirm: boolean
  pushConfirm: boolean
  // Allow dynamic plugin modals
  [key: string]: boolean
}

// =============================================================================
// Section Props (Shared Interface)
// =============================================================================

/**
 * Base props for all section components
 */
export interface BaseSectionProps {
  pack: PackDetail
  isEditing?: boolean
  onEdit?: () => void
}

/**
 * Props for editable sections
 */
export interface EditableSectionProps extends BaseSectionProps {
  onSave?: (changes: Partial<PackDetail>) => Promise<void>
  onCancel?: () => void
}

// =============================================================================
// Actions & Events
// =============================================================================

/**
 * Pack action types for header buttons
 */
export type PackAction =
  | 'use'
  | 'edit'
  | 'delete'
  | 'download-all'
  | 'check-updates'
  | 'view-source'

/**
 * Gallery action types
 */
export type GalleryAction =
  | 'add-preview'
  | 'remove-preview'
  | 'reorder-previews'
  | 'set-cover'
  | 'open-fullscreen'

/**
 * Dependency action types
 */
export type DependencyAction =
  | 'add'
  | 'remove'
  | 'download'
  | 'update'
  | 'edit-constraints'

// =============================================================================
// Re-exports from inventory types
// =============================================================================

export type {
  PackBackupStatusResponse,
  PackPullPushResponse,
  PackBlobStatus,
  PackBackupSummary,
} from '../inventory/types'
