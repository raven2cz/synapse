/**
 * usePackPlugin Hook
 *
 * Loads and manages the appropriate plugin for a pack based on its source/category.
 *
 * Plugin matching priority:
 * 1. InstallPlugin - user_tags includes 'install-pack'
 * 2. CivitaiPlugin - source.provider === 'civitai'
 * 3. CustomPlugin - pack_category === 'custom' or fallback
 */

import { useMemo, useCallback, useEffect } from 'react'
import { toast } from '@/stores/toastStore'
import type { PackDetail } from '../types'
import type {
  PackPlugin,
  PluginContext,
  UsePackPluginReturn,
} from './types'

// Import plugins
import { CivitaiPlugin } from './CivitaiPlugin'
import { CustomPlugin } from './CustomPlugin'
import { InstallPlugin } from './InstallPlugin'

// =============================================================================
// Plugin Registry
// =============================================================================

/**
 * All available plugins, sorted by priority (highest first)
 */
const PLUGIN_REGISTRY: PackPlugin[] = [
  InstallPlugin,  // Priority: 100 - Most specific
  CivitaiPlugin,  // Priority: 50 - Source-based
  CustomPlugin,   // Priority: 0 - Fallback
].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))

// =============================================================================
// Hook Options
// =============================================================================

export interface UsePackPluginOptions {
  /**
   * Current pack data
   */
  pack?: PackDetail

  /**
   * Whether edit mode is active
   */
  isEditing?: boolean

  /**
   * Whether pack has unsaved changes
   */
  hasUnsavedChanges?: boolean

  /**
   * Modal state
   */
  modals?: Record<string, boolean>

  /**
   * Open modal handler
   */
  openModal?: (key: string) => void

  /**
   * Close modal handler
   */
  closeModal?: (key: string) => void

  /**
   * Refetch pack data
   */
  refetch?: () => void
}

// =============================================================================
// Hook Implementation
// =============================================================================

export function usePackPlugin(options: UsePackPluginOptions): UsePackPluginReturn {
  const {
    pack,
    isEditing = false,
    hasUnsavedChanges = false,
    modals = {},
    openModal = () => {},
    closeModal = () => {},
    refetch = () => {},
  } = options

  // Find matching plugin
  const plugin = useMemo(() => {
    if (!pack) return null

    for (const p of PLUGIN_REGISTRY) {
      if (p.appliesTo(pack)) {
        return p
      }
    }

    // Should never happen - CustomPlugin is fallback
    console.warn('[usePackPlugin] No plugin matched for pack:', pack.name)
    return CustomPlugin
  }, [pack])

  // Build plugin context
  const context: PluginContext | null = useMemo(() => {
    if (!pack || !plugin) return null

    return {
      pack,
      isEditing,
      hasUnsavedChanges,
      modals,
      openModal,
      closeModal,
      refetch,
      toast: {
        success: (message: string) => toast.success(message),
        error: (message: string) => toast.error(message),
        info: (message: string) => toast.info(message),
      },
    }
  }, [pack, plugin, isEditing, hasUnsavedChanges, modals, openModal, closeModal, refetch])

  // Call onPackLoad when pack changes
  useEffect(() => {
    if (pack && plugin?.onPackLoad) {
      plugin.onPackLoad(pack)
    }
  }, [pack?.name, plugin])

  // Get plugin by ID
  const getPlugin = useCallback((id: string): PackPlugin | undefined => {
    return PLUGIN_REGISTRY.find(p => p.id === id)
  }, [])

  return {
    plugin,
    context,
    isLoading: false,
    allPlugins: PLUGIN_REGISTRY,
    getPlugin,
  }
}

// =============================================================================
// Exports
// =============================================================================

export { PLUGIN_REGISTRY }
export default usePackPlugin
