/**
 * Pack Plugin Type Definitions
 *
 * Plugin system enables type-specific behavior for different pack sources:
 * - CivitaiPlugin: Update checking, View on Civitai, Civitai metadata
 * - CustomPlugin: Full editability, pack dependencies management
 * - InstallPlugin: Script management, console output, start/stop
 *
 * Each plugin can:
 * - Add extra actions to the header
 * - Render additional sections
 * - Validate changes before save
 * - Hook into pack lifecycle events
 */

import type { ReactNode } from 'react'
import type { PackDetail, PackDependencyRef, ValidationResult } from '../types'

// =============================================================================
// Core Plugin Interface
// =============================================================================

/**
 * Base plugin interface that all plugins must implement
 */
export interface PackPlugin {
  /**
   * Unique plugin identifier
   */
  id: string

  /**
   * Human-readable plugin name
   */
  name: string

  /**
   * Determines if this plugin applies to a given pack
   * Only one plugin should match per pack (first match wins)
   */
  appliesTo: (pack: PackDetail) => boolean

  /**
   * Priority for plugin matching (higher = checked first)
   * Default: 0
   */
  priority?: number

  // ===========================================================================
  // UI Extensions
  // ===========================================================================

  /**
   * Render extra action buttons in the pack header
   * These appear alongside Edit, Use, Delete buttons
   */
  renderHeaderActions?: (context: PluginContext) => ReactNode

  /**
   * Render additional sections after the main content
   * Can be used for plugin-specific features
   */
  renderExtraSections?: (context: PluginContext) => ReactNode

  /**
   * Render plugin-specific modals
   * Return null when no modal should be shown
   */
  renderModals?: (context: PluginContext) => ReactNode

  /**
   * Custom badge to show next to pack name
   * e.g., "Civitai", "Custom", "Install"
   */
  getBadge?: (pack: PackDetail) => PluginBadge | null

  // ===========================================================================
  // Behavior Hooks
  // ===========================================================================

  /**
   * Called when pack is loaded
   * Can be used for initialization, prefetching, etc.
   */
  onPackLoad?: (pack: PackDetail) => void

  /**
   * Called before saving changes
   * Can modify the changes or return validation errors
   */
  onBeforeSave?: (
    pack: PackDetail,
    changes: Partial<PackDetail>
  ) => {
    changes: Partial<PackDetail>
    errors?: Record<string, string>
  }

  /**
   * Validate changes before save
   * Return validation result with errors if invalid
   */
  validateChanges?: (
    pack: PackDetail,
    changes: Partial<PackDetail>
  ) => ValidationResult

  // ===========================================================================
  // Feature Flags
  // ===========================================================================

  /**
   * What features are enabled for this plugin?
   */
  features?: PluginFeatures
}

// =============================================================================
// Plugin Context
// =============================================================================

/**
 * Context passed to plugin render methods
 * Contains pack data and common actions
 */
export interface PluginContext {
  /**
   * Current pack data
   */
  pack: PackDetail

  /**
   * Whether edit mode is active
   */
  isEditing: boolean

  /**
   * Whether the pack has unsaved changes
   */
  hasUnsavedChanges: boolean

  /**
   * Open a modal by key
   */
  openModal: (key: string) => void

  /**
   * Close a modal by key
   */
  closeModal: (key: string) => void

  /**
   * Current modal state
   */
  modals: Record<string, boolean>

  /**
   * Trigger a pack refetch
   */
  refetch: () => void

  /**
   * Show a toast notification
   */
  toast: {
    success: (message: string) => void
    error: (message: string) => void
    info: (message: string) => void
  }
}

// =============================================================================
// Plugin Badge
// =============================================================================

/**
 * Badge configuration for plugin identification
 */
export interface PluginBadge {
  /**
   * Badge text (short)
   */
  label: string

  /**
   * Badge variant for styling
   */
  variant: 'primary' | 'secondary' | 'warning' | 'info' | 'success'

  /**
   * Optional icon (Lucide icon name)
   */
  icon?: string

  /**
   * Tooltip text
   */
  tooltip?: string
}

// =============================================================================
// Plugin Features
// =============================================================================

/**
 * Feature flags for plugins
 */
export interface PluginFeatures {
  /**
   * Can edit pack metadata (name, description, etc.)
   */
  canEditMetadata?: boolean

  /**
   * Can edit previews (add, remove, reorder)
   */
  canEditPreviews?: boolean

  /**
   * Can edit dependencies (add, remove)
   */
  canEditDependencies?: boolean

  /**
   * Can edit workflows
   */
  canEditWorkflows?: boolean

  /**
   * Can edit parameters
   */
  canEditParameters?: boolean

  /**
   * Can check for updates (Civitai only)
   */
  canCheckUpdates?: boolean

  /**
   * Can manage pack dependencies (pack-to-pack)
   */
  canManagePackDependencies?: boolean

  /**
   * Can run scripts (Install pack only)
   */
  canRunScripts?: boolean

  /**
   * Can be deleted
   */
  canDelete?: boolean
}

// =============================================================================
// Update Types (for CivitaiPlugin)
// =============================================================================

/**
 * Update check response from backend
 */
export interface UpdateCheckResponse {
  pack: string
  has_updates: boolean
  changes_count: number
  ambiguous_count: number
  plan?: UpdatePlan
}

/**
 * Update plan from backend
 */
export interface UpdatePlan {
  pack: string
  already_up_to_date: boolean
  changes: UpdateChange[]
  ambiguous: AmbiguousUpdate[]
  impacted_packs: string[]
}

/**
 * Single change in an update plan
 */
export interface UpdateChange {
  dependency_id: string
  old: Record<string, unknown>
  new: Record<string, unknown>
}

/**
 * Candidate for ambiguous update selection
 */
export interface UpdateCandidate {
  provider: string
  provider_model_id?: number
  provider_version_id?: number
  provider_file_id?: number
  sha256?: string
}

/**
 * Ambiguous update requiring user selection
 */
export interface AmbiguousUpdate {
  dependency_id: string
  candidates: UpdateCandidate[]
}

/**
 * Result of applying an update
 */
export interface UpdateResult {
  pack: string
  applied: boolean
  lock_updated: boolean
  synced: boolean
  ui_targets: string[]
  already_up_to_date: boolean
}

// =============================================================================
// Pack Dependency Types (for CustomPlugin)
// =============================================================================

/**
 * Status of a pack dependency
 */
export interface PackDependencyStatus extends PackDependencyRef {
  /**
   * Is the dependent pack installed?
   */
  installed: boolean

  /**
   * Current version of the dependent pack (if installed)
   */
  current_version?: string

  /**
   * Does the version match the constraint?
   */
  version_match: boolean

  /**
   * Error message if any
   */
  error?: string

  /**
   * Pack type (checkpoint, lora, etc.)
   */
  pack_type?: string

  /**
   * Pack description (truncated to 200 chars)
   */
  description?: string

  /**
   * Number of asset dependencies in the pack
   */
  asset_count?: number

  /**
   * Aggregated trigger words from pack's LoRA/embedding deps
   */
  trigger_words?: string[]

  /**
   * Base model of the pack
   */
  base_model?: string

  /**
   * Whether the pack has unresolved dependencies
   */
  has_unresolved?: boolean

  /**
   * Whether all blobs are installed locally
   */
  all_installed?: boolean
}

// =============================================================================
// Plugin Registry Types
// =============================================================================

/**
 * Plugin registration info
 */
export interface PluginRegistration {
  plugin: PackPlugin
  enabled: boolean
}

/**
 * Plugin registry configuration
 */
export interface PluginRegistryConfig {
  /**
   * Enable plugin debug logging
   */
  debug?: boolean

  /**
   * Custom plugin order (by id)
   */
  order?: string[]
}

// =============================================================================
// Hook Return Type
// =============================================================================

/**
 * Return type of usePackPlugin hook
 */
export interface UsePackPluginReturn {
  /**
   * The active plugin for the current pack (or null)
   */
  plugin: PackPlugin | null

  /**
   * Plugin context for rendering
   */
  context: PluginContext | null

  /**
   * Whether plugin is loading
   */
  isLoading: boolean

  /**
   * All registered plugins
   */
  allPlugins: PackPlugin[]

  /**
   * Get plugin by ID
   */
  getPlugin: (id: string) => PackPlugin | undefined
}
